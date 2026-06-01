# Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Design v0

Date: 2026-06-02

Status: complete

## Decision

The next hosted-readiness implementation slice should wire the local hosted admin gateway permission source to the internal hosted permission read model.

Recommended next implementation task:

```text
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Implementation v0
```

The implementation should remain local/dogfood-scoped. It should replace the gateway harness static hosted permission fixture with a read-model-backed permission source when a Postgres DSN is configured, while preserving the existing static fixture as a test fallback. It must not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, decision persistence, or Data Plane reads from mutable Control Plane tables.

## Why This Slice Now

The hosted admin path now has:

- trusted gateway authentication and header rewriting
- endpoint permission mapping for hosted admin routes
- gateway-local fail-closed permission decisions
- Control Plane endpoint checks as a second authorization gate
- tenant-partitioned project mutation
- durable hosted permission schema
- internal Go read model over hosted permission tables
- live Postgres dogfood proving the read model against real schema and seeded rows

The remaining gap is runtime wiring: the gateway still uses a local/static permission fixture. The next implementation should connect the proven read model to the gateway permission-source boundary without changing public identity, policy management, production deployment, or Control Plane authorization semantics.

## Current Baseline

The local gateway harness currently:

1. consumes public `Authorization`.
2. maps dogfood public bearer tokens to `PublicPrincipal`.
3. resolves permissions from a local hosted-permission-shaped fixture.
4. checks endpoint required permission before forwarding.
5. strips caller-supplied public/trusted identity headers.
6. injects gateway-issued trusted `X-API2Agent-*` headers.
7. forwards to the private Control Plane with trusted gateway authorization.

The internal read model currently:

1. opens a Postgres-backed `HostedPermissionReadModel`.
2. resolves subject, membership, roles, grants, active policy, and decision evidence.
3. fails closed for missing membership, suspended membership, revoked/missing permission, no active policy, and ambiguous active policy.
4. returns a gateway-compatible decision shape.
5. does not persist `hosted_permission_decisions` in v0.

## Goals

- define how the gateway runtime permission source calls the hosted permission read model
- preserve gateway-local public auth and route permission mapping
- preserve trusted header stripping and gateway-issued trusted header injection
- preserve Control Plane endpoint permission checks as the second gate
- fail closed when the read model or backing store is unavailable
- keep policy/source/fingerprint/decision evidence secret-safe
- keep decision persistence deferred
- keep public auth provider implementation and public role CRUD out of scope
- define implementation tests and dogfood for the next slice

## Non-Goals

Do not implement or design:

- OAuth/OIDC provider integration
- login/session/user lifecycle
- invitation management
- public project/user/role/permission CRUD
- hosted policy write APIs
- decision persistence
- provider onboarding
- marketplace/provider submission
- credential vault writes
- billing or settlement
- workflow runtime
- production gateway deployment
- automatic snapshot publish/reload
- Data Plane reads from mutable Control Plane tables

## Runtime Boundary

The gateway should own the read-model call:

```text
public request
  -> gateway public auth
  -> endpoint permission mapping
  -> hosted permission source
  -> HostedPermissionReadModel.Resolve
  -> gateway-local allow/deny decision
  -> trusted header injection
  -> private Control Plane request
  -> Control Plane trusted-gateway auth
  -> Control Plane endpoint permission check
```

The private Control Plane must not read hosted permission tables during endpoint authorization. It receives only gateway-issued trusted claims and optional non-secret decision evidence headers.

## Proposed Gateway Interface

Conceptual Go interface:

```go
type GatewayPermissionSource interface {
    Resolve(ctx context.Context, req GatewayPermissionLookupRequest) (GatewayPermissionDecision, error)
}
```

Request:

```go
type GatewayPermissionLookupRequest struct {
    PublicPrincipalID  string
    ExternalSubjectRef string
    ProjectID          string
    TokenID            string
    Method             string
    Path               string
    RequiredPermission string
    RequestID          string
    ResolvedAt         time.Time
}
```

Decision:

```go
type GatewayPermissionDecision struct {
    Allowed            bool
    Status             int
    ErrorType          string
    DenyReason         string
    SubjectID          string
    ActorID            string
    ProjectID          string
    OrganizationID     string
    TokenID            string
    Roles              []string
    Permissions        []string
    RequiredPermission string
    PolicySource       string
    PolicyVersion      string
    PolicyFingerprint  string
    DecisionID         string
    ResolvedAt         time.Time
}
```

The read-model-backed implementation should adapt this request into:

```go
registry.HostedPermissionLookupRequest
```

and return:

```go
registry.HostedPermissionDecision
```

converted to the gateway decision shape.

## Public Principal Input

For v0 runtime wiring, public auth remains dogfood/local:

- public bearer token parsing remains at the gateway.
- token-to-principal mapping remains a local dogfood map or fixture.
- the mapping produces `public_principal_id`, `external_subject_ref`, and non-secret `token_id`.
- raw public bearer tokens are never sent to the read model.
- raw public bearer tokens are never forwarded to the Control Plane.
- raw public bearer tokens are never written to dogfood artifacts or audit/idempotency evidence.

The implementation should use `external_subject_ref` as the primary read-model lookup key. `public_principal_id` can remain evidence/context and fallback only if explicitly required by code, but the hosted schema is anchored on `hosted_subjects.external_subject_ref`.

## Project Context

For the current hosted admin endpoints, project context should be derived from trusted gateway routing/config, not caller-controlled headers.

Current dogfood scope:

```text
gateway-harness-project
```

Future project routing can derive project context from:

- authenticated hosted project context
- path/routing metadata
- gateway tenancy middleware

Caller-supplied `X-Project-ID`, `X-Actor-ID`, `X-API2Agent-*`, cookies, or arbitrary query parameters must not select project authorization scope.

## Endpoint Permission Mapping

The gateway runtime wiring must keep the explicit route map:

| Method / Path | Required Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/registry/project-partition/replace` | `control_plane.registry.project_partition_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |

Unknown admin routes fail locally and must not reach the Control Plane.

## Configuration

Recommended local/dogfood configuration:

| Config | Purpose |
| --- | --- |
| `permission_source_mode=static` | Existing fixture behavior for tests. |
| `permission_source_mode=hosted_read_model` | Use `HostedPermissionReadModel` against Postgres. |
| `postgres_dsn` | Backing store DSN for read-model mode. |
| `permission_lookup_timeout` | Short timeout around read-model lookup. |
| `gateway_project_id` | Dogfood project context until real hosted tenancy exists. |

If `hosted_read_model` is selected without a DSN, startup should fail or the gateway should return `503 PERMISSION_SOURCE_UNAVAILABLE` before forwarding. It must never fall back to broad static allow.

## Failure Semantics

Gateway-local failures:

| Condition | HTTP | Error Type | Forward? |
| --- | --- | --- |
| missing public auth | `401` | `PUBLIC_AUTH_REQUIRED` | no |
| invalid public token/principal | `401` | `PUBLIC_AUTH_INVALID` | no |
| read model unavailable or DB error | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| lookup timeout | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| no active policy | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| ambiguous active policy | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| missing hosted subject | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| missing project membership | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| suspended membership | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| revoked/missing required permission | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| unknown admin route | `404` | `PUBLIC_ROUTE_NOT_FOUND` | no |
| unsupported method | `405` | `PUBLIC_METHOD_NOT_ALLOWED` | no |

Control Plane failures remain separate:

- `401 AUTH_ERROR` for invalid trusted gateway auth
- `403 AUTHZ_DENIED` for missing trusted permissions
- `503 AUTH_SERVICE_UNAVAILABLE` for Control Plane auth configuration failure

## Trusted Header Mapping

On allow, the gateway injects:

```text
X-API2Agent-Gateway-Authorization
X-API2Agent-Gateway-Key-ID
X-API2Agent-Principal-ID
X-API2Agent-Actor-ID
X-API2Agent-Project-ID
X-API2Agent-Organization-ID
X-API2Agent-Token-ID
X-API2Agent-Roles
X-API2Agent-Permissions
X-API2Agent-Permission-Source
X-API2Agent-Policy-Version
X-API2Agent-Policy-Fingerprint
X-API2Agent-Permission-Decision-ID
```

Mapping:

| Header | Source |
| --- | --- |
| `X-API2Agent-Principal-ID` | `decision.SubjectID` |
| `X-API2Agent-Actor-ID` | `decision.ActorID` |
| `X-API2Agent-Project-ID` | `decision.ProjectID` |
| `X-API2Agent-Organization-ID` | `decision.OrganizationID` |
| `X-API2Agent-Token-ID` | `decision.TokenID` |
| `X-API2Agent-Roles` | comma-joined `decision.Roles` |
| `X-API2Agent-Permissions` | comma-joined `decision.Permissions` |
| `X-API2Agent-Permission-Source` | `decision.PolicySource` |
| `X-API2Agent-Policy-Version` | `decision.PolicyVersion` |
| `X-API2Agent-Policy-Fingerprint` | `decision.PolicyFingerprint` |
| `X-API2Agent-Permission-Decision-ID` | `decision.DecisionID` |

The gateway must strip caller-supplied versions of all `X-API2Agent-*` headers before injecting its own.

The Control Plane may record policy evidence headers as metadata, but must not use them for authorization in this slice. Authorization remains based on trusted permissions and endpoint required-permission checks.

## Request Forwarding Rules

Forward only:

- gateway-issued trusted headers
- `X-Request-ID`
- `Idempotency-Key`
- safe content headers needed by the private endpoint
- request body

Do not forward:

- public `Authorization`
- cookies
- caller-supplied identity headers
- raw public tokens
- raw gateway secrets in artifact/audit metadata

## Timeout And Availability

The gateway should wrap read-model lookup with a short timeout.

Suggested v0 behavior:

- default timeout: small dogfood value such as 1-2 seconds
- timeout maps to `503 PERMISSION_SOURCE_UNAVAILABLE`
- DB open/ping failure maps to `503 PERMISSION_SOURCE_UNAVAILABLE`
- query error maps to `503 PERMISSION_SOURCE_UNAVAILABLE`
- no cache for v0 runtime wiring

If a future cache is introduced, it must be explicitly designed and bounded by policy version/fingerprint. This slice should not add cache behavior.

## Decision Persistence

Decision persistence remains out of scope.

The read model should continue returning decision evidence without inserting into `hosted_permission_decisions`. Runtime wiring tests should assert zero decision rows unless a later persistence slice explicitly changes that contract.

## Implementation Test Requirements

Add or update tests to prove:

- hosted read-model permission source allows admin validate/import paths.
- readonly principal can validate/read current but cannot import/replace.
- no membership fails locally and does not forward.
- suspended membership fails locally and does not forward.
- revoked/missing grant fails locally and does not forward.
- no active policy fails locally with `503`.
- ambiguous active policy fails locally with `503`.
- missing/invalid public auth remains `401`.
- unknown route/method still fails locally.
- caller-supplied trusted headers are stripped.
- forwarded trusted headers match read-model decision evidence.
- Control Plane second gate still rejects forced insufficient trusted permissions.
- no raw public token or gateway secret appears in dogfood artifacts, audit rows, or idempotency rows.
- `hosted_permission_decisions` remains empty.

## Dogfood Requirements

The implementation dogfood should:

1. start real local Postgres.
2. apply schema.
3. seed registry and hosted permission rows.
4. start private Control Plane in trusted-gateway mode.
5. start the local gateway harness in `hosted_read_model` permission-source mode.
6. exercise success and denial cases over the gateway HTTP boundary.
7. inspect Postgres audit/idempotency rows to prove denied gateway-local requests did not reach the Control Plane.
8. assert secret-safe artifacts.

Minimum observed cases:

- admin validate succeeds.
- admin project partition replace succeeds when permission is present.
- readonly validate succeeds.
- readonly import/replace fails locally.
- missing membership fails locally.
- suspended membership fails locally.
- revoked grant fails locally.
- no active policy fails locally with `503`.
- ambiguous policy fails locally with `503`.
- forced insufficient forwarded permissions still fail at the Control Plane second gate.

## Acceptance Criteria

Implementation can close when:

- gateway runtime has a hosted read-model permission-source mode.
- static fixture mode remains available for focused local tests.
- real Postgres dogfood proves read-model-backed gateway decisions.
- all deny cases fail before forwarding.
- trusted header injection uses read-model evidence.
- Control Plane second gate remains authoritative.
- no raw tokens/secrets leak into evidence.
- no decision persistence, public CRUD, OAuth/OIDC, production gateway deployment, marketplace, vault, billing, workflow, automatic propagation, or Data Plane mutable reads are added.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Implementation v0
```
