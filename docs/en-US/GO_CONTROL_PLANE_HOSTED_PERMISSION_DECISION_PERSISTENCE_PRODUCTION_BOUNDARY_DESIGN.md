# Go Control Plane Hosted Permission Decision Persistence Production Boundary Design v0

Date: 2026-06-02

Status: complete

## Decision

Hosted permission decision persistence should remain gateway-owned in the production-shaped boundary.

The production gateway, or the hosted admin gateway process that fronts the private Control Plane, resolves the public principal and permission decision, then synchronously records a non-secret append-only decision row before forwarding allowed requests to the private Control Plane.

Recommended next task:

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Implementation v0
```

That task should implement the production-shaped persistence boundary in local infrastructure only. It should not deploy a real public gateway or add OAuth/OIDC, public user/project/role CRUD, invitation/session lifecycle, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic publish/reload, policy write APIs, or Data Plane reads from mutable Control Plane tables.

## Why This Design Now

The local hosted admin gateway has already proven:

- hosted permission read-model resolution
- gateway-owned decision persistence
- allowed/denied/source-unavailable decision evidence
- allowed persistence failure fail-closed behavior
- duplicate-equivalent no-op behavior
- conflicting duplicate detection with `PERMISSION_DECISION_INTEGRITY_CONFLICT`
- secret-safe live Postgres dogfood artifacts

The remaining risk is no longer whether local evidence can be written. The risk is where production ownership lives, how write failures behave operationally, what customers may see, and whether the current schema is strong enough before decision rows become durable product data.

## Goals

- define production persistence ownership and process boundary
- define connection lifecycle, retry/backoff, buffering posture, and fail-closed behavior
- define observability expectations for writes, conflicts, and retention
- define retention/privacy expectations and the customer-visible decision history stance
- decide which schema hardening is required before production-shaped implementation
- define implementation tests and local dogfood/canary evidence

## Non-Goals

- no OAuth/OIDC provider integration
- no public user/project/role/permission CRUD
- no invitation, login, or session lifecycle
- no marketplace/provider onboarding
- no credential vault writes
- no billing or settlement state
- no workflow runtime
- no automatic snapshot publish or Data Plane reload
- no policy write APIs
- no Data Plane reads from mutable Control Plane tables
- no real production gateway deployment

## Production Boundary Model

The boundary remains:

```text
public admin client
  -> hosted admin gateway
  -> hosted permission read model
  -> hosted permission decision persistence writer
  -> private Control Plane admin endpoint
```

The gateway owns:

- public caller authentication result consumption
- project/tenant context selection
- endpoint permission mapping
- hosted permission read-model lookup
- decision id construction
- decision persistence
- fail-closed behavior before allowed forwarding
- trusted claim/header injection after persistence succeeds

The private Control Plane owns:

- gateway authentication
- trusted claim parsing
- endpoint permission enforcement as the second gate
- admin mutation semantics
- admin audit rows for forwarded requests
- idempotency records for forwarded mutations

The private Control Plane must not become the writer of `hosted_permission_decisions`. That table records public hosted permission lookup evidence, not endpoint authorization internals.

## Process And Service Ownership

For v0, the persistence writer should run in-process with the hosted admin gateway.

Rejected for v0:

- a separate decision-audit service
- an async queue between gateway and Postgres
- Control Plane-side decision backfill
- best-effort background write behind allowed forwarding

Rationale:

- allowed admin mutations should not reach the private Control Plane without durable permission evidence once persistence is enabled.
- in-process ownership keeps the request, decision, persistence, and forwarding correlation exact.
- async buffering can be added later only after queue durability, replay, tenant isolation, and loss semantics are designed.

## Connection Lifecycle

The production-shaped writer should use a dedicated bounded Postgres connection pool owned by the gateway process.

Required behavior:

| Area | Requirement |
| --- | --- |
| startup | validate persistence configuration when decision persistence is enabled |
| health | expose readiness degraded state when the writer cannot reach Postgres |
| pool | use a bounded pool separate from read-model lookup if supported locally |
| per-write timeout | fail each insert with a short bounded timeout |
| shutdown | drain in-flight writes before process exit when possible |
| credentials | load DSN/credentials from deployment secret storage, never from source control |
| logs | redact DSN passwords and never log raw tokens/secrets |

The read-model lookup transaction must remain read-only and separate from the decision persistence write. The persistence write starts only after a permission decision object exists.

## Retry And Backoff

The writer may retry only narrowly:

| Failure | Retry stance |
| --- | --- |
| transient connection acquisition failure | retry with short bounded exponential backoff |
| serialization/deadlock retryable SQL state | retry once or twice within the request budget |
| duplicate-equivalent decision id | treat as no-op success |
| duplicate-conflicting decision id | do not retry; return `PERMISSION_DECISION_INTEGRITY_CONFLICT` |
| constraint violation from invalid evidence | do not retry; return platform integrity failure |
| request context canceled | do not retry |

Retry budgets must be small enough that the public admin caller receives a clear platform failure rather than an unbounded hang.

## Fail-Closed And Buffering Posture

Synchronous persistence is required for allowed decisions.

| Decision family | Persistence failure behavior |
| --- | --- |
| allowed | return `503 PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE` or `503 PERMISSION_DECISION_INTEGRITY_CONFLICT`; do not forward |
| denied | return the original gateway-local denial; log/metric persistence failure |
| source-unavailable | return original source-unavailable failure; log/metric persistence failure |
| missing/invalid public auth | do not persist in v0 |
| unknown route/method | do not persist in v0 |

No production-shaped implementation should silently buffer allowed decision rows after forwarding. If a future queue is introduced, the queue enqueue itself must be durable and complete before allowed forwarding.

## Conflict Semantics

Conflict handling from integrity hardening becomes part of the production boundary:

- equivalent duplicate evidence is accepted as idempotent no-op success.
- conflicting controlled evidence for the same decision id is a platform integrity conflict.
- allowed conflicts fail before private Control Plane forwarding.
- conflict evidence must be secret-safe and include decision id, project id, required permission, error type, and request correlation id when available.

## Observability

Metrics should expose:

| Metric family | Labels |
| --- | --- |
| decision persistence attempts | project, endpoint permission, allowed, result |
| persistence latency | result, allowed |
| persistence failures | error type, retryable flag |
| integrity conflicts | endpoint permission, allowed |
| duplicate-equivalent no-ops | endpoint permission |
| rows written | allowed, deny reason family |
| retention job results | status, deleted row count bucket |

Logs/traces should include:

- request id
- decision id
- project id
- required permission
- public principal id or hosted subject id when safe
- policy version/fingerprint
- gateway key id when safe
- persistence result and latency

Logs/traces must not include:

- raw public bearer tokens
- raw `Authorization`
- cookies
- gateway secrets
- OAuth access or refresh tokens
- plaintext API keys
- vault material
- raw request bodies

## Retention And Privacy

Hosted permission decision rows are security evidence, not an unbounded analytics lake.

Production stance:

- retain rows for a bounded operational/security window.
- use tenant/project-scoped deletion and export boundaries when customer-visible features are introduced.
- keep raw secrets and raw request bodies out of the table so retention can focus on authorization evidence.
- preserve append-only semantics during the active retention window.
- run cleanup out of band, never inline with public admin request handling.

Recommended v0 retention policy:

| Data | Default stance |
| --- | --- |
| decision evidence rows | retain 90 days in production-shaped environments unless configured otherwise |
| local dogfood rows | retained for test artifact lifetime |
| aggregate metrics | may outlive row retention if tenant-safe and secret-free |
| integrity conflict rows | retain at least as long as normal decision evidence |

Deletion/export APIs are not part of this slice. The implementation should only prepare schema and operational boundaries that make later tenant-scoped retention possible.

## Customer-Visible History Stance

Do not expose a customer-visible decision history UI/API yet.

When it is eventually designed, it should show:

- timestamp
- project
- endpoint/action
- required permission
- allow/deny/source-unavailable result
- deny reason family
- actor/subject display reference if approved
- policy version/fingerprint
- request id correlation

It should not show:

- raw token ids unless explicitly product-approved
- raw external identity provider subject refs
- gateway/internal secret metadata
- request bodies
- private Control Plane internal error details

## Schema Hardening Decision

The current table is good enough for local proof. Production-shaped use should add a small schema hardening slice before treating rows as durable product data.

Required hardening:

| Need | Recommendation |
| --- | --- |
| duplicate integrity | store an `evidence_fingerprint` generated from canonical controlled evidence |
| request correlation | add or standardize safe `request_id` metadata/indexing |
| tenant history queries | add indexes for `project_id, resolved_at` and `subject_id, resolved_at` |
| retention cleanup | add index support for retention by `created_at` or `resolved_at` |
| conflict investigation | keep policy version/fingerprint indexed or queryable |
| partial failure evidence | keep source-unavailable sentinel semantics but document them as operational evidence, not customer identity |

Do not add raw request body storage, raw token storage, OAuth token tables, public CRUD tables, or policy write APIs in this slice.

## Implementation Requirements

The next implementation should:

- introduce the production-shaped persistence writer interface in the gateway boundary.
- keep the local harness path working.
- keep decision persistence disabled unless explicitly configured in production-shaped mode.
- add schema hardening if migration tooling already supports it locally; otherwise document the migration file and prove tests against the evolved schema.
- enforce bounded write timeout and retry/backoff behavior.
- preserve allowed fail-closed behavior before forwarding.
- preserve duplicate-equivalent no-op and duplicate-conflict failure semantics.
- emit secret-safe metrics/log evidence in dogfood artifacts.

## Test Requirements

Implementation tests should cover:

- startup/config validation for enabled persistence without a writer DSN
- bounded write timeout maps to `PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- transient retry succeeds without duplicate row creation
- retry budget exhaustion fails allowed decisions before forwarding
- duplicate-equivalent row is no-op success
- duplicate-conflicting row returns `PERMISSION_DECISION_INTEGRITY_CONFLICT`
- denied decision persistence failure does not become allow
- source-unavailable persistence failure preserves original caller failure
- public auth failures still do not create decision rows
- unknown route/method still do not create decision rows
- schema evidence fingerprint matches canonical controlled evidence
- retention query can select old rows by tenant/project and time
- secret markers are absent from rows, logs, metrics, and dogfood artifacts

## Dogfood And Canary Requirements

Local dogfood should:

1. start local Postgres.
2. apply schema including production-boundary hardening.
3. run the gateway in production-shaped persistence mode.
4. exercise allowed, denied, source-unavailable, duplicate-equivalent, and duplicate-conflict cases.
5. simulate transient write failure and retry success.
6. simulate exhausted persistence failure and prove allowed requests are not forwarded.
7. assert decision rows include evidence fingerprints and tenant/time query fields.
8. assert secret-safe artifact output.

Production canary requirements for a later real deployment:

- persistence write success rate
- p95/p99 write latency
- fail-closed count by error type
- integrity conflict count
- duplicate-equivalent count
- retention cleanup success/failure
- correlation from gateway request id to private Control Plane audit id for forwarded allowed requests

## Acceptance Criteria

- production persistence ownership and process boundary are explicit.
- connection lifecycle and bounded retry/backoff behavior are explicit.
- allowed fail-closed and no-silent-buffering stance is explicit.
- observability requirements are explicit and secret-safe.
- retention/privacy and customer-visible history stance are explicit.
- schema hardening required before production-shaped use is explicit.
- implementation tests and dogfood/canary evidence are defined.
- OAuth/OIDC, public CRUD, production gateway deployment, vault, billing, marketplace, workflow, provider onboarding, policy write APIs, Data Plane mutable reads, and automatic propagation remain deferred.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Implementation v0
```
