# Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Design v0

Date: 2026-06-02

Status: complete

## Decision

The next hosted-readiness implementation slice should harden hosted permission decision persistence integrity without expanding the hosted product surface.

Recommended next implementation task:

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Implementation v0
```

The implementation should remain local/dogfood-scoped. It should make duplicate decision handling explicit, prove conflicting evidence is rejected as a platform integrity error, tighten partial-failure/sentinel evidence semantics, and document metadata retention/privacy expectations. It must not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, policy write APIs, or Data Plane reads from mutable Control Plane tables.

## Why This Slice Now

The hosted admin gateway now:

- resolves public admin permission decisions through the hosted permission read model.
- persists authenticated allowed, denied, and source-unavailable decision rows.
- skips missing/invalid public auth and unknown route/method failures.
- fails closed before forwarding when allowed-decision persistence is unavailable.
- proves 15 secret-safe decision rows in live Postgres dogfood.

The remaining correctness gap is not whether rows can be written; it is whether the persistence boundary can prove row integrity when decision IDs collide or evidence changes.

The current local implementation uses:

```text
ON CONFLICT (id) DO NOTHING
```

That is deterministic, but it silently ignores a conflicting duplicate. The hardening slice should make the accepted duplicate case byte-equivalent and make the conflicting duplicate case explicit.

## Goals

- preserve append-only decision persistence.
- make duplicate decision handling observable and deterministic.
- accept duplicate inserts only when controlled evidence is equivalent.
- reject duplicate decision IDs with conflicting evidence as `PERMISSION_DECISION_INTEGRITY_CONFLICT`.
- keep allowed-decision integrity conflicts fail-closed before forwarding.
- preserve original denied/source-unavailable fail-closed responses while recording local conflict evidence.
- clarify sentinel and partial-failure row semantics.
- keep persisted metadata secret-safe and bounded.
- define retention/privacy expectations for decision rows before they become production product data.
- prove the hardening with focused tests and live dogfood evidence.

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
- policy write APIs
- Data Plane reads from mutable Control Plane tables
- policy cache invalidation or propagation

## Integrity Boundary

The gateway remains the owner of permission lookup and decision recording:

```text
GatewayPermissionDecision
  -> normalize persistence evidence
  -> compute controlled evidence fingerprint
  -> insert hosted_permission_decisions
  -> if id exists, compare controlled evidence fingerprint
  -> accept exact/equivalent duplicate or raise integrity conflict
```

The private Control Plane still must not write hosted permission decisions during endpoint authorization.

## Controlled Evidence

The hardening implementation should define a canonical controlled-evidence object for duplicate comparison.

Recommended fields:

| Field | Include |
| --- | --- |
| `subject_id` | yes |
| `actor_id` | yes |
| `project_id` | yes |
| `organization_id` | yes |
| `token_id` | yes |
| `required_permission` | yes |
| `allowed` | yes |
| `deny_reason` | yes |
| `roles` | yes, sorted or preserved canonically |
| `permissions` | yes, sorted or preserved canonically |
| `policy_source` | yes |
| `policy_version` | yes |
| `policy_fingerprint` | yes |
| `resolved_at` | yes, normalized to timestamptz precision used by storage |
| metadata allowlist | yes |
| `created_at` | no |

`created_at` should not participate because it is a write timestamp. Database-generated or operational-only fields should not cause a duplicate conflict.

The canonical form should be serialized with stable key ordering and no secrets. A future production schema can store an explicit `decision_evidence_fingerprint`; the v0 local implementation can compare queried row values directly or compute the fingerprint in the harness before deciding whether the duplicate is equivalent.

## Duplicate Handling

Recommended behavior:

| Case | Behavior |
| --- | --- |
| new `id` | insert row |
| duplicate `id` with equivalent controlled evidence | no-op success; record duplicate-equivalent evidence in dogfood/report if useful |
| duplicate `id` with conflicting controlled evidence | raise `PERMISSION_DECISION_INTEGRITY_CONFLICT` |

The implementation should stop using unconditional silent `ON CONFLICT (id) DO NOTHING` as the only proof of correctness.

Allowed implementation strategies:

1. Insert first with `ON CONFLICT DO NOTHING`, then query existing row and compare controlled evidence when no row was inserted.
2. Query existing row first, compare if present, otherwise insert.
3. Add a local-only canonical evidence fingerprint and use it in SQL conflict handling.

For v0, prefer the smallest local harness change that proves the behavior clearly in tests.

## Failure Semantics

Integrity conflict is a platform failure.

Recommended caller behavior:

| Decision being persisted | Integrity conflict behavior |
| --- | --- |
| allowed decision | return `503 PERMISSION_DECISION_INTEGRITY_CONFLICT` before forwarding |
| denied `403` decision | preserve original `403`; record local integrity-conflict evidence |
| source-unavailable `503` decision | preserve original `503 PERMISSION_SOURCE_UNAVAILABLE`; record local integrity-conflict evidence |

This mirrors persistence-unavailable behavior: do not forward an allowed request when durable evidence is corrupted or ambiguous, but do not turn an already fail-closed denial into a different caller-visible authorization result.

## Sentinel And Partial-Failure Semantics

Current v0 sentinel values:

| Missing evidence | Sentinel |
| --- | --- |
| unknown subject | `unknown-subject` |
| unknown actor | `unknown-actor` |
| unknown organization | `unknown-organization` |
| unknown policy source | `hosted-permission-source-unavailable` |
| unknown policy version | `unavailable` |
| unknown policy fingerprint | `sha256:unavailable` |

Hardening should keep these sentinels for local compatibility, but constrain their use:

- only authenticated source-unavailable decisions may use unknown subject/actor/org sentinels.
- allowed decisions must never use unknown subject, actor, organization, policy source, policy version, or policy fingerprint.
- denied `403` decisions may use unknown actor/org only when the read model legitimately could not derive membership evidence.
- sentinel policy source/version rows must be seeded explicitly and marked non-active.
- dogfood should count sentinel rows and prove they correspond only to source-unavailable or partial-denial cases.

Future production schema work can revisit nullability or a dedicated partial-failure evidence table. This design does not require that schema migration now.

## Metadata Allowlist

Allowed metadata keys for v0 hardening:

| Key | Status |
| --- | --- |
| `decision_status` | keep |
| `error_type` | keep |
| `permission_source` | keep |
| `request_id` | keep |
| `method` | keep |
| `path` | keep |
| `gateway_key_id` | keep |
| `persistence_version` | keep |
| `duplicate_resolution` | optional local evidence |
| `integrity_error_type` | optional local evidence |

Do not add raw request body, raw public bearer token, raw `Authorization`, cookies, gateway secret, OAuth access/refresh tokens, plaintext credentials, vault material, or unbounded exception strings to persisted metadata.

Local in-memory/report failure evidence may include a bounded error type and decision id, but should not include raw SQL, DSN passwords, tokens, or headers.

## Retention And Privacy

V0 hardening should document and preserve this stance:

- local dogfood rows are retained for the life of the temporary Postgres container.
- production retention, export, deletion, tenant privacy controls, and legal discovery workflows are deferred.
- no cleanup automation should run inside request handling.
- future production design should define retention by tenant/project and clarify which decision fields are customer-visible.

The implementation should not add a cleanup job in this slice.

## Schema Guidance

No schema migration is required for the local hardening proof.

Permitted optional local changes:

- add a local-only helper for canonical evidence fingerprinting.
- add tests that query existing rows and compare controlled evidence.
- add dogfood report fields for duplicate-equivalent and duplicate-conflict probes.

Deferred production/schema options:

- explicit `decision_evidence_fingerprint` column.
- uniqueness over `(id, decision_evidence_fingerprint)`.
- partial-failure nullable fields or dedicated sentinel entities.
- retention indexes by `organization_id`, `project_id`, and `created_at`.

## Test Requirements

Implementation tests should prove:

- duplicate insert with equivalent controlled evidence succeeds without creating another row.
- duplicate insert with conflicting allowed evidence raises `PERMISSION_DECISION_INTEGRITY_CONFLICT`.
- allowed conflict fails closed before forwarding.
- duplicate conflict for denied/source-unavailable decisions preserves the original fail-closed response and records local evidence.
- allowed decisions cannot be normalized with sentinel subject/actor/org/policy values.
- source-unavailable sentinel rows are accepted only for authenticated decisions.
- metadata allowlist rejects secret-like material and unbounded raw headers/bodies.
- canonical evidence comparison ignores `created_at`.
- role/permission ordering is canonicalized or compared consistently.

## Dogfood Requirements

Live dogfood should extend the existing persistence artifact with:

1. an equivalent duplicate persistence probe.
2. a conflicting duplicate persistence probe.
3. an allowed conflict probe returning `503 PERMISSION_DECISION_INTEGRITY_CONFLICT` before forwarding.
4. evidence that hosted decision row count does not increase for equivalent duplicates.
5. evidence that conflicting duplicates do not mutate existing rows.
6. evidence that sentinel rows are limited to expected decision families.
7. secret-safety checks for persisted rows and local failure evidence.

The existing artifact path can be reused or a hardening-specific artifact path can be created. If reused, the report should include explicit hardening fields so closeout can distinguish base persistence from integrity probes.

## Non-Goals Preserved

This design does not add public CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic snapshot publish/reload, policy write APIs, or Data Plane mutable table reads.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Implementation v0
```
