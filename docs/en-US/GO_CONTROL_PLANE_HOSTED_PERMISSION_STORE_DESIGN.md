# Go Control Plane Hosted Permission Store Design v0

Date: 2026-06-01

Status: complete

## Decision

Define a durable hosted permission store boundary for gateway permission lookup.

Recommended next implementation task:

```text
Go Control Plane Hosted Permission Store Contract Harness v0
```

This design replaces the static dogfood permission source conceptually, but does not implement storage, public role CRUD, OAuth/OIDC, invitation flows, production gateway deployment, marketplace/provider onboarding, billing, workflow runtime, credential vault writes, or automatic snapshot propagation.

The permission store belongs at the hosted gateway/auth boundary. The private Control Plane remains the second authorization gate and must continue using trusted gateway claims rather than reading public permission tables directly.

## Why This Slice Now

The hosted admin path has now proven:

- hosted trusted-gateway identity and header issuance
- public caller header stripping
- gateway-local static permission decisions
- Control Plane endpoint permission checks as a second gate
- project-scoped mutation through `POST /v1/admin/registry/project-partition/replace`
- audit and idempotency evidence for hosted project mutation
- live dogfood for success, replay, partition violation, and gateway-local denial

The remaining hosted product gap is that the gateway permission source is still static dogfood policy. The next step is to design a durable lookup boundary that can later be implemented without accidentally opening public role management or moving authorization into the mutable Control Plane API surface.

## Goals

- define durable permission-store entities and relationships
- define the gateway lookup contract that replaces static policy lookup
- keep endpoint permission mapping explicit and narrow
- preserve project-scoped authorization for hosted project mutation
- keep Control Plane trusted-permission checks as the second gate
- define fail-closed semantics for unavailable, ambiguous, stale, or denied policy
- define safe audit/report evidence for permission source id, version, and decision id
- define consistency and cache expectations before implementation
- make the next contract harness testable without adding public CRUD

## Non-Goals

Do not implement or design public product surfaces for:

- OAuth/OIDC provider integration
- public user, project, role, or permission CRUD
- invitation, login, or session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables
- public mutation of global registry/provider objects

## Boundary

The hosted gateway owns permission lookup:

```text
public authenticated principal
  -> hosted permission store lookup
  -> gateway-issued trusted claims
  -> private Control Plane request
  -> Control Plane endpoint permission check
```

The Control Plane must not read hosted permission tables directly in v0. It receives only gateway-issued trusted claims:

```text
X-API2Agent-Subject-ID
X-API2Agent-Actor-ID
X-API2Agent-Project-ID
X-API2Agent-Organization-ID
X-API2Agent-Token-ID
X-API2Agent-Roles
X-API2Agent-Permissions
```

Optional safe evidence can be forwarded only as metadata:

```text
X-API2Agent-Permission-Source
X-API2Agent-Policy-Version
X-API2Agent-Policy-Fingerprint
X-API2Agent-Permission-Decision-ID
```

These evidence headers must not become authorization inputs in the Control Plane. Authorization remains based on trusted permissions and endpoint-specific checks.

## Store Model

The durable store should model the authorization facts needed to issue gateway claims. Suggested logical entities:

| Entity | Purpose |
| --- | --- |
| `hosted_subjects` | Stable hosted subject mapped from an authenticated external/public principal. |
| `hosted_project_memberships` | Subject membership in a project and organization, including active/suspended state. |
| `hosted_roles` | Internal role definitions such as `project_admin`, `project_editor`, `project_readonly`, or `platform_operator`. |
| `hosted_role_bindings` | Assignment of roles to subject/project/organization scope. |
| `hosted_permission_grants` | Permission constants granted by role and scope. This may be a role-permission binding table rather than a standalone grant table. |
| `hosted_policy_versions` | Monotonic policy version, fingerprint, activation time, and audit metadata. |
| `hosted_permission_decisions` | Optional append-only decision/audit record for gateway permission lookups. |

External token/session storage is not part of this v0 design. If future OAuth/OIDC/session tables are added, they should feed the authenticated public principal into this lookup boundary rather than changing the permission decision contract.

## Lookup Contract

Conceptual gateway contract:

```text
ResolveHostedPermissionDecision(request_context, endpoint_context)
  -> HostedPermissionDecision
```

Inputs:

| Field | Description |
| --- | --- |
| `public_principal_id` | Authenticated public subject from the gateway authenticator. |
| `external_subject_ref` | Optional provider/user reference after public auth. |
| `method` | HTTP method. |
| `path` | Public admin path after routing normalization. |
| `project_context` | Project derived from trusted route/context, not from arbitrary caller headers. |
| `request_id` | Correlation id for safe evidence. |
| `resolved_at` | Gateway decision time. |

Outputs:

| Field | Description |
| --- | --- |
| `allowed` | Whether the gateway may forward the request. |
| `deny_reason` | Stable local denial reason when `allowed=false`. |
| `subject_id` | Hosted subject id for trusted headers. |
| `actor_id` | Actor id for audit/idempotency scope. |
| `project_id` | Project scope for trusted headers. |
| `organization_id` | Organization scope for trusted headers. |
| `token_id` | Non-secret token/session id if available. |
| `roles` | Gateway-issued trusted role names. |
| `permissions` | Gateway-issued trusted permission constants. |
| `required_permission` | Endpoint permission derived from method/path. |
| `policy_source` | Durable store/source identifier. |
| `policy_version` | Monotonic policy version used for the decision. |
| `policy_fingerprint` | Non-secret fingerprint of the policy view. |
| `decision_id` | Non-secret decision id for report/audit correlation. |
| `resolved_at` | Decision timestamp. |

The gateway must check that `required_permission` is present in `permissions` before forwarding. The Control Plane must repeat the endpoint permission check using trusted claims.

## Endpoint Permission Mapping

The hosted gateway must map the current private admin endpoints explicitly:

| Method / Path | Required Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/registry/project-partition/replace` | `control_plane.registry.project_partition_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |

Hosted project mutation should grant:

```text
control_plane.registry.project_partition_replace
```

It should not grant broad full-registry replacement:

```text
control_plane.registry.import_replace
```

except to explicit operator/internal roles that are not exposed as normal hosted project memberships.

Unknown public admin paths must fail locally with `404` or `405` and must not reach the Control Plane.

## Failure Semantics

Gateway-local failures:

| Condition | HTTP | Error Type | Forward? |
| --- | --- | --- | --- |
| missing public auth | `401` | `PUBLIC_AUTH_REQUIRED` | no |
| invalid public principal | `401` | `PUBLIC_AUTH_INVALID` | no |
| permission store unavailable | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| missing project membership | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| inactive/suspended membership | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| ambiguous project scope | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| stale or ambiguous policy view | `503` or `403` | `PERMISSION_SOURCE_UNAVAILABLE` or `PUBLIC_AUTHZ_DENIED` | no |
| endpoint permission absent | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| unknown admin route | `404` | `PUBLIC_ROUTE_NOT_FOUND` | no |
| unsupported method | `405` | `PUBLIC_METHOD_NOT_ALLOWED` | no |

Unavailable store failures are gateway-local `503 PERMISSION_SOURCE_UNAVAILABLE` and must not create Control Plane audit rows or idempotency records.

Policy ambiguity, missing membership, stale policy, and permission absence must fail closed. The system must never fall back from durable lookup to broad static allow.

Control Plane failures remain separate:

- `401 AUTH_ERROR` for invalid trusted gateway auth
- `403 AUTHZ_DENIED` for missing trusted permissions
- `503 AUTH_SERVICE_UNAVAILABLE` for platform auth configuration failure

## Consistency

A single permission decision must be resolved from a coherent policy view.

Minimum v0 expectations:

- role bindings, membership state, and permission grants are read from one consistent transaction/snapshot
- decision output includes `policy_version` or `policy_fingerprint`
- revocation is not eventually allowed beyond an explicitly bounded cache window
- stale or mixed-version policy reads fail closed
- policy writes are out of scope, but the read model must leave room for monotonic versioning and revocation evidence

## Caching

The safest v0 contract harness may use no cache.

If implementation later adds gateway-local cache, it must be:

- short-lived
- keyed by subject, project, endpoint permission, and policy version/fingerprint
- invalidated or bypassed on policy version mismatch
- fail-closed when the backing store is unavailable and the cache is stale or ambiguous
- excluded from evidence that contains raw public tokens or gateway secrets

No cache may turn a revoked permission into an unbounded allow.

## Audit And Evidence

Safe evidence:

- `subject_id`
- `actor_id`
- `project_id`
- `organization_id`
- `roles`
- `permissions`
- `required_permission`
- `policy_source`
- `policy_version`
- `policy_fingerprint`
- `decision_id`
- `resolved_at`

Forbidden evidence:

- raw public bearer tokens
- raw gateway secrets
- raw session tokens
- OAuth access/refresh tokens
- credential vault material
- plaintext API keys

Gateway-local denials must be visible in gateway dogfood/report evidence but must not create Control Plane audit or idempotency rows because they are not forwarded.

Forwarded successful or Control Plane-denied requests should keep using trusted actor/project scope for Control Plane audit and idempotency evidence.

## Contract Harness Plan

The next implementation slice should prove the lookup contract without building a production permission store.

Recommended harness behavior:

1. Replace the static in-memory policy with a durable-store-shaped fixture or local read model.
2. Resolve subject, membership, role bindings, and permission grants through the new contract.
3. Return policy source/version/fingerprint/decision id in safe report evidence.
4. Preserve gateway trusted-header stripping and injection.
5. Preserve gateway-local denial before forwarding.
6. Preserve the Control Plane second-gate denial test.
7. Add revocation and unavailable-store cases.
8. Keep all public CRUD and auth-provider lifecycle out of scope.

## Test Plan

Future implementation should cover:

- lookup allow for project admin/editor on allowed endpoint
- lookup deny for readonly principal on mutation endpoint
- missing membership/project scope
- inactive/suspended membership
- permission store unavailable
- stale or ambiguous policy version
- permission revocation removes access
- endpoint permission mapping for all six current endpoints
- hosted project mutation requires `control_plane.registry.project_partition_replace`
- broad `control_plane.registry.import_replace` is not required for hosted project mutation
- Control Plane second gate still denies insufficient trusted permissions
- gateway-local denials create no Control Plane audit/idempotency rows
- audit/report evidence includes policy version/fingerprint/decision id
- raw public tokens, gateway secrets, session tokens, and vault material are redacted
- no public role CRUD, user CRUD, invitation flow, OAuth/OIDC provider integration, or production gateway deployment is added
- no registry mutation or snapshot propagation behavior changes

## Acceptance Criteria

- durable permission store model is explicit
- gateway lookup input/output contract is explicit
- endpoint permission mapping includes the project partition endpoint
- hosted project mutation uses project-partition permission, not broad import/replace
- failure semantics are fail-closed and gateway-local where appropriate
- consistency and cache rules prevent unbounded allow after revocation
- audit/report evidence is useful and secret-safe
- implementation remains deferred to a contract harness
- no public CRUD, OAuth/OIDC, production gateway, marketplace, vault, billing, workflow, or automatic propagation scope is started

## Next Recommended Task

```text
Go Control Plane Hosted Permission Store Contract Harness v0
```
