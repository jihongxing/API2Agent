# Go Control Plane Hosted Permission Decision Persistence Design v0

Date: 2026-06-02

Status: complete

## Decision

The next hosted-readiness implementation slice should add append-only persistence for hosted permission decisions produced by the local hosted admin gateway permission source.

Recommended next implementation task:

```text
Go Control Plane Hosted Permission Decision Persistence Implementation v0
```

The implementation should remain local/dogfood-scoped. It should persist non-secret hosted permission decision evidence into the existing `hosted_permission_decisions` table after the gateway resolves a public admin permission decision. It must not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, or Data Plane reads from mutable Control Plane tables.

## Why This Slice Now

The hosted admin path now has:

- public auth consumed by the gateway.
- explicit endpoint permission mapping.
- trusted header stripping and gateway-issued trusted header injection.
- Control Plane endpoint permission checks as a second gate.
- durable hosted permission schema.
- internal Postgres read model.
- live Postgres read-model dogfood.
- gateway runtime wiring to read-model-backed permission source.
- live gateway dogfood proving allow/deny/source-unavailable paths.

The remaining evidence gap is persistence. The system can produce stable decision IDs and non-secret evidence, but `hosted_permission_decisions` intentionally remains empty. The next implementation should change that contract deliberately by adding append-only decision records.

## Goals

- persist hosted permission decisions as append-only evidence.
- preserve the gateway as the owner of permission lookup and decision recording.
- record allowed, denied, and source-unavailable decisions when enough safe evidence exists.
- keep raw public tokens, gateway secrets, OAuth tokens, refresh tokens, cookies, and vault material out of the table.
- preserve gateway fail-closed authorization semantics.
- define persistence failure behavior without creating unsafe broad allows.
- keep decision persistence separate from Control Plane endpoint authorization.
- prove persistence with local/live Postgres dogfood.

## Non-Goals

Do not implement or design:

- public user/project/role/permission CRUD
- OAuth/OIDC provider integration
- login/session/invitation lifecycle
- production gateway deployment
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- workflow runtime
- automatic snapshot publish/reload
- Data Plane reads from mutable Control Plane tables
- policy write APIs
- cache invalidation or policy propagation

## Ownership Boundary

The gateway permission source owns decision persistence:

```text
public request
  -> gateway public auth
  -> endpoint permission mapping
  -> hosted permission source
  -> HostedPermissionReadModel.Resolve
  -> GatewayPermissionDecision
  -> persist hosted_permission_decisions
  -> gateway-local allow/deny response or trusted forwarding
```

The private Control Plane must not write hosted permission decisions during endpoint authorization. It receives trusted claims and may record admin audit events for forwarded requests, but it should not become the source of truth for public hosted permission lookup evidence.

## Existing Table

The current schema already defines:

```text
hosted_permission_decisions
```

Current fields:

| Field | Design use |
| --- | --- |
| `id` | `decision.DecisionID` |
| `subject_id` | hosted subject id when known |
| `actor_id` | hosted actor id when known |
| `project_id` | gateway-derived project context |
| `organization_id` | organization id when known |
| `token_id` | non-secret token/session id |
| `required_permission` | endpoint permission |
| `allowed` | decision allow/deny |
| `deny_reason` | stable deny reason or source-unavailable reason |
| `roles` | non-secret role ids/names |
| `permissions` | non-secret permission constants |
| `policy_source` | source identifier |
| `policy_version` | policy version used for the decision |
| `policy_fingerprint` | non-secret policy fingerprint |
| `resolved_at` | gateway decision time |
| `metadata` | bounded non-secret diagnostics |
| `created_at` | write time |

The implementation can use the existing table without a schema migration if it maps missing subject/actor/org evidence to sentinel non-secret values. A later schema hardening slice can revisit nullability if production requirements demand richer partial-failure records.

## Record Shape

Persist one row per gateway permission decision with:

| Field | Source |
| --- | --- |
| `id` | decision id |
| `subject_id` | `decision.SubjectID` or sentinel |
| `actor_id` | `decision.ActorID` or sentinel |
| `project_id` | gateway-derived project context |
| `organization_id` | `decision.OrganizationID` or sentinel |
| `token_id` | non-secret token id from public principal mapping |
| `required_permission` | endpoint permission |
| `allowed` | decision allowed flag |
| `deny_reason` | decision deny reason, empty for allowed |
| `roles` | decision roles |
| `permissions` | decision permissions |
| `policy_source` | decision policy source or fallback source |
| `policy_version` | decision policy version or sentinel |
| `policy_fingerprint` | decision policy fingerprint or sentinel `sha256:unavailable` |
| `resolved_at` | decision resolved time |
| `metadata` | bounded non-secret JSON |

Recommended sentinel values:

| Missing evidence | Sentinel |
| --- | --- |
| unknown subject | `unknown-subject` |
| unknown actor | `unknown-actor` |
| unknown organization | `unknown-organization` |
| unknown policy source | `hosted-permission-source-unavailable` |
| unknown policy version | `unavailable` |
| unknown policy fingerprint | `sha256:unavailable` |

Sentinels keep v0 compatible with the current `NOT NULL` table while making partial source-unavailable decisions inspectable.

## Metadata

Allowed metadata keys:

| Key | Purpose |
| --- | --- |
| `decision_status` | numeric decision status such as `200`, `403`, `503` |
| `error_type` | gateway-local error type |
| `permission_source` | source identifier |
| `public_principal_id` | non-secret public principal id, not raw token |
| `external_subject_ref_hash` | hash of external subject ref if included |
| `request_id` | safe request correlation id |
| `method` | normalized method |
| `path` | normalized public admin path |
| `gateway_key_id` | non-secret gateway key id |
| `persistence_version` | `hosted-permission-decision-persistence-v0` |

Do not store:

- raw public bearer token
- raw `Authorization`
- cookies
- gateway secret
- OAuth access token
- OAuth refresh token
- plaintext API key
- vault material
- raw request body

## Decision ID And Deduplication

The current decision id is deterministic over:

```text
subject_id | project_id | required_permission | policy_version | resolved_at
```

For v0 implementation, keep this decision id and insert with `ON CONFLICT (id) DO NOTHING` only when the incoming row is byte-equivalent for the fields the implementation controls. A duplicate decision id with different evidence should be treated as a platform integrity error in tests.

The gateway dogfood currently uses second-level timestamps for live request decisions. The implementation should preserve or improve uniqueness by ensuring `resolved_at` has enough precision when it creates decisions. If the existing helper emits higher precision, persist that value.

Future production work can add a request-id or nonce input to decision id generation, but that should be explicit because it changes correlation semantics.

## Write Timing

Recommended v0 timing:

1. Resolve public principal and endpoint permission.
2. Call the hosted permission read model.
3. Build a `GatewayPermissionDecision`.
4. Persist the decision row.
5. If allowed, inject trusted headers and forward.
6. If denied, return the local error response.

Persist before forwarding so an allowed decision has evidence even if the downstream Control Plane request later fails.

For missing or invalid public auth, do not persist in `hosted_permission_decisions` in v0. There is no hosted subject/policy decision yet; those failures remain gateway auth failures.

For unknown route or unsupported method, do not persist in `hosted_permission_decisions` in v0. There is no endpoint permission decision yet.

## Persistence Failure Semantics

Decision persistence is evidence, not authorization.

Recommended v0 behavior:

| Case | Persistence failure behavior |
| --- | --- |
| allowed decision | fail closed with `503 PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE` before forwarding |
| denied `403` decision | return the original `403`, include/report persistence failure evidence in local artifact/logs |
| source-unavailable `503` decision | return original `503 PERMISSION_SOURCE_UNAVAILABLE`, include/report persistence failure evidence |

Why:

- allowed decisions should not be forwarded without durable evidence once persistence is enabled.
- denied/source-unavailable decisions are already fail-closed for the caller; persistence failure should not turn them into a different authorization result.
- the dogfood should prove persistence failures never create broad allows.

The implementation should keep this behavior local/dogfood-scoped. Production operational policy can be revisited later with explicit SLOs and buffering design.

## Transaction Semantics

Do not mix decision persistence into the read-model repeatable-read transaction.

Recommended implementation:

- read-model lookup stays read-only.
- decision persistence uses a separate short write operation after the read transaction commits.
- persistence insert is append-only.
- persistence insert does not modify policy, membership, role, grant, registry, admin audit, or idempotency rows.

This keeps authorization lookup consistency separate from evidence recording and avoids turning the read model into a mutable read/write boundary.

## Source-Unavailable Decisions

Persist source-unavailable decisions when a `GatewayPermissionDecision` exists.

Examples:

- no active policy
- ambiguous active policy
- read-model helper/database unavailable after public auth has produced a known public principal

Use sentinel policy/subject fields when the source could not return full evidence. Metadata should include:

```json
{
  "decision_status": 503,
  "error_type": "PERMISSION_SOURCE_UNAVAILABLE",
  "persistence_version": "hosted-permission-decision-persistence-v0"
}
```

## Secret Safety

The implementation and dogfood must reject evidence containing these markers:

- public bearer token values
- gateway secret values
- `access_token`
- `refresh_token`
- `plaintext`
- `authorization`
- raw cookies
- vault material markers

The dogfood report should keep DSN password redacted and should not include raw public tokens.

## Retention

V0 design does not add cleanup automation.

Recommended retention stance:

- append-only records are retained for local dogfood artifacts.
- production retention, export, deletion, and tenant privacy controls are deferred.
- any future cleanup job must be explicitly designed and must not run implicitly in request handling.

## Test Requirements

Implementation tests should prove:

- allowed admin decision inserts one row.
- readonly denied mutation inserts one denied row.
- missing membership inserts one denied row with safe evidence.
- suspended membership inserts one denied row.
- revoked grant inserts one denied row.
- no active policy inserts one source-unavailable row with sentinel policy evidence.
- ambiguous policy inserts one source-unavailable row.
- missing/invalid public auth does not insert hosted permission decision rows.
- unknown route/method does not insert hosted permission decision rows.
- forced Control Plane second-gate denial has an allowed gateway decision row before forwarding.
- raw public token and gateway secret do not appear in persisted rows.
- duplicate decision id handling is deterministic.
- allowed decision persistence failure fails closed before forwarding.

## Dogfood Requirements

Live dogfood should:

1. start local Postgres.
2. apply schema.
3. seed registry and hosted permission rows.
4. start private Control Plane in trusted-gateway mode.
5. start gateway in hosted read-model permission-source mode with decision persistence enabled.
6. exercise allowed, denied, source-unavailable, and second-gate cases.
7. query `hosted_permission_decisions`.
8. assert expected row count and row evidence.
9. assert gateway-local denied requests still do not create Control Plane admin audit/idempotency rows.
10. assert secret-safe persisted evidence.

Expected persisted row families:

- allowed validate
- readonly allowed validate
- readonly denied import/replace
- missing membership
- suspended membership
- revoked grant
- no active policy
- ambiguous active policy
- allowed gateway decision followed by Control Plane `AUTHZ_DENIED`
- partition/import allowed decisions

The exact row count should be specified by implementation tests once the live dogfood case order is finalized.

## Non-Goals Preserved

This design does not add public CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic snapshot publish/reload, policy write APIs, or Data Plane mutable table reads.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Decision Persistence Implementation v0
```
