# Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Closeout + Phase Review v0

Date: 2026-06-02

Status: complete

## Decision

The Hosted Permission Decision Persistence Integrity Hardening implementation slice can close for local v0.

The repository now proves that duplicate hosted permission decision IDs are no longer silently ignored. Equivalent duplicate evidence is accepted as no-op success, conflicting controlled evidence raises `PERMISSION_DECISION_INTEGRITY_CONFLICT`, and allowed conflicts fail closed before forwarding to the private Control Plane.

Recommended next task:

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Design v0
```

That task should remain a design task. It should define the production persistence boundary, service/process ownership, operational behavior, retention/privacy, observability, and schema hardening needed before hosted decision rows become durable product data. It must not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, policy write APIs, or Data Plane reads from mutable Control Plane tables.

## What Is Now Complete

### Integrity Hardening

Completed:

- canonical controlled-evidence comparison for duplicate decision IDs
- equivalent duplicate no-op behavior
- conflicting duplicate detection with `PERMISSION_DECISION_INTEGRITY_CONFLICT`
- allowed conflict fail-closed behavior before forwarding
- bounded local failure evidence with decision id and error type
- sentinel constraints that reject allowed decisions with unknown subject/actor/org/policy evidence
- regression tests for duplicate-equivalent, duplicate-conflict, allowed-sentinel rejection, source-unavailable sentinel normalization, and auth-failure skips

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

Completed:

- existing persistence dogfood with 15 hosted decision rows
- equivalent duplicate persistence probe
- conflicting duplicate persistence probe
- allowed conflict probe returning `503 PERMISSION_DECISION_INTEGRITY_CONFLICT`
- row-count checks proving duplicates/conflicts do not create or mutate rows
- audit-count checks proving allowed conflict fails before private Control Plane audit writes
- redacted JSON artifact output

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| duplicate-equivalent decisions are accepted as no-op success | passed |
| conflicting duplicate decisions raise `PERMISSION_DECISION_INTEGRITY_CONFLICT` | passed |
| allowed integrity conflict fails closed before forwarding | passed |
| conflicting duplicate does not mutate existing hosted decision rows | passed |
| equivalent duplicate does not create an additional hosted decision row | passed |
| allowed decisions cannot use sentinel subject/actor/org/policy evidence | passed |
| source-unavailable sentinel normalization still works | passed |
| missing/invalid public auth decisions remain outside persistence | passed |
| canonical comparison excludes `created_at` and operational write timestamps | passed |
| roles and permissions are compared canonically | passed |
| metadata remains bounded and secret-safe | passed |
| public CRUD, OAuth/OIDC, production gateway, marketplace, vault, billing, workflow, automatic propagation, policy write APIs, schema migration, and Data Plane mutable reads remain out of scope | passed |

## Dogfood Evidence

Observed:

- `status=passed`
- `audit_counts.hosted_permission_decisions=15`
- `hosted_permission_decision_rows_after_duplicate_equivalent=15`
- `hosted_permission_decision_rows_after_integrity_conflict=15`
- `integrity_conflict_status=503`
- `integrity_conflict_error_type=PERMISSION_DECISION_INTEGRITY_CONFLICT`
- `audit_rows_after_integrity_conflict=5`
- `permission_decision_duplicate_equivalent_count=1`
- `permission_decision_integrity_conflict_count=1`

The dogfood artifact also proves:

- equivalent duplicates do not add rows.
- conflicting duplicates do not mutate rows.
- allowed integrity conflicts do not reach private Control Plane audit/idempotency writes.
- persisted rows and local failure evidence stay secret-safe.

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
git diff --check
git diff --cached --check
```

Go test directory:

```text
services/control-plane
```

Python test and dogfood directory:

```text
repository root
```

## Closeout Judgment

This integrity hardening slice is complete for local v0.

The largest correctness gap from the previous slice was silent duplicate handling. That gap is closed locally: duplicates are compared against canonical controlled evidence, equivalent duplicates no-op, and conflicting duplicates become explicit platform integrity failures. The gateway still refuses to forward allowed requests when durable evidence is ambiguous.

This is still a local harness proof. It does not define production connection management, deployment topology, retention policy, tenant privacy controls, or customer-visible decision history.

## Remaining Risks

### Production Persistence Boundary Is Undefined

The harness writes directly through local SQL execution. Production needs a clear service/process boundary, connection lifecycle, retry/backoff behavior, observability, rollout plan, and operational ownership model.

### Schema Hardening Is Deferred

No schema migration was added. Production may still need a stored evidence fingerprint, retention indexes, explicit partial-failure shape, nullable fields, or stronger constraints.

### Retention And Tenant Privacy Are Still Deferred

Append-only decision rows are now more trustworthy, but production retention, export, deletion, privacy controls, legal discovery, and customer-visible history remain undefined.

### Public Identity And Policy Lifecycle Remain Local

Public principal mapping and hosted policy data are still local/dogfood seeded. OAuth/OIDC, login/session/invitation lifecycle, and hosted policy mutation APIs remain future work.

### Production Gateway Deployment Is Still Out Of Scope

TLS, private networking, rate limits, rollout, production observability, health checks, and gateway SLOs remain future work.

## Still Not Allowed

Do not start:

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation/login/session lifecycle
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- policy write APIs
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Design v0
```

Why:

- local persistence and integrity semantics are now proven.
- the next risk is not another local evidence tweak; it is deciding how this persistence boundary should operate in production-shaped infrastructure.
- retention/privacy must be designed before decision rows become durable customer/product data.
- production boundary design can stay narrow without starting public CRUD, OAuth/OIDC, billing, marketplace, workflow, policy write APIs, or automatic propagation.

Expected scope:

- define production persistence ownership and process/service boundary.
- define connection lifecycle, retry/backoff, fail-closed/buffering posture, and observability.
- define retention/privacy expectations and customer-visible history stance.
- define whether schema hardening is required before production use.
- define tests and dogfood/canary evidence for the next implementation slice.

Out of scope:

- public CRUD
- OAuth/OIDC
- invitation/session lifecycle
- marketplace/provider onboarding
- vault writes
- billing
- workflow runtime
- automatic publish/reload
- policy write APIs
- Data Plane mutable Control Plane table reads
