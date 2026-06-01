# Go Control Plane Hosted Permission Decision Persistence Production Boundary Closeout + Phase Review v0

Date: 2026-06-02

Status: complete

## Decision

The Hosted Permission Decision Persistence Production Boundary implementation slice can close for local v0.

The repository now proves that hosted permission decision persistence has a production-shaped local boundary: the gateway owns the in-process writer, allowed decisions fail closed before forwarding when persistence is unavailable or times out, persisted rows carry canonical `evidence_fingerprint` values, bounded retry/timeout settings are visible in secret-safe metadata, and duplicate/conflict integrity remains stable.

Recommended next task:

```text
Go Control Plane Hosted Permission Decision Persistence Stage Closeout + Readiness Review v0
```

That task should summarize the full hosted permission decision persistence lane from design through production-boundary proof, decide whether this lane is complete for local v0, and rank the next hosted-readiness gap. It must not add public CRUD, OAuth/OIDC, invitation/session lifecycle, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, policy write APIs, Data Plane reads from mutable Control Plane tables, or real production gateway deployment.

## What Is Now Complete

### Production Boundary Implementation

Completed:

- `hosted_permission_decisions.evidence_fingerprint`
- `CHECK (evidence_fingerprint LIKE 'sha256:%')`
- project/time query index for tenant history
- subject/time query index
- `created_at` index for retention scans
- policy fingerprint index for conflict investigation
- canonical controlled-evidence fingerprinting
- gateway-owned bounded write timeout and transient retry behavior
- production-boundary metadata on persisted rows
- timeout fail-closed behavior for allowed decisions
- transient retry success proof
- duplicate-equivalent no-op preservation
- conflicting duplicate `PERMISSION_DECISION_INTEGRITY_CONFLICT` preservation

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

Completed:

- real local Postgres schema application
- hosted permission store seeding
- private Control Plane service startup in trusted-gateway mode
- local hosted admin gateway harness startup
- production-boundary persistence writer exercise
- transient write failure retry success
- forced persistence unavailable and timeout fail-closed probes
- duplicate-equivalent and duplicate-conflict probes
- secret-safe persisted rows and artifact checks

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| gateway-owned production-shaped persistence writer is implemented locally | passed |
| allowed persistence unavailable fails closed before forwarding | passed |
| allowed persistence timeout fails closed before forwarding | passed |
| transient write failure retries and succeeds within budget | passed |
| persisted rows include canonical `evidence_fingerprint` | passed |
| persisted rows include production boundary metadata | passed |
| tenant/time and retention query indexes exist | passed |
| duplicate-equivalent decision remains no-op success | passed |
| conflicting duplicate decision remains `PERMISSION_DECISION_INTEGRITY_CONFLICT` | passed |
| integrity conflict does not mutate decision rows | passed |
| allowed integrity conflict fails before private Control Plane audit | passed |
| missing/invalid public auth decisions remain outside persistence | passed |
| secret markers are absent from rows, audit, idempotency, and artifact evidence | passed |
| public CRUD, OAuth/OIDC, production gateway deployment, marketplace, vault, billing, workflow, automatic propagation, policy write APIs, and Data Plane mutable reads remain out of scope | passed |

## Dogfood Evidence

Observed:

- `status=passed`
- `audit_counts.hosted_permission_decisions=16`
- `audit_counts.admin_audit_events=6`
- `permission_decision_rows_written_count=16`
- `permission_decision_retry_count=1`
- `permission_decision_timeout_count=1`
- `permission_decision_write_attempt_count=18`
- `transient_retry_status=200`
- `transient_retry_valid=true`
- `persistence_unavailable_status=503`
- `persistence_unavailable_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- `persistence_timeout_status=503`
- `persistence_timeout_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- `audit_rows_after_persistence_unavailable=0`
- `audit_rows_after_persistence_timeout=0`
- `hosted_permission_decision_rows_after_duplicate_equivalent=16`
- `integrity_conflict_status=503`
- `integrity_conflict_error_type=PERMISSION_DECISION_INTEGRITY_CONFLICT`
- `audit_rows_after_integrity_conflict=6`
- `hosted_permission_decision_rows_after_integrity_conflict=16`
- `permission_decision_duplicate_equivalent_count=1`
- `permission_decision_integrity_conflict_count=1`
- 16/16 decision rows have `evidence_fingerprint`
- 16/16 decision rows have `production_boundary_version=hosted-permission-decision-production-boundary-v0`

The dogfood artifact also proves:

- persisted row evidence is secret-safe.
- private Control Plane audit rows correlate to forwarded allowed requests.
- gateway-local denials and source-unavailable decisions do not create private Control Plane audit rows.
- allowed persistence failures and integrity conflicts do not reach private Control Plane mutation/audit paths.

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
git diff --check
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

This slice is complete for local v0.

The production-boundary design asked for gateway-owned persistence, synchronous allowed-decision evidence, bounded failure behavior, observability-ready metadata, retention/query schema hardening, and secret-safe live proof. The implementation and dogfood satisfy those requirements locally.

This does not mean API2Agent has a real production hosted gateway. It means the local Control Plane hosted admin gateway harness now proves the decision persistence contract that a production gateway must preserve.

## Remaining Risks

### Real Production Gateway Deployment Is Still Future Work

TLS, private networking, deployment topology, gateway health/readiness endpoints, rate limiting, rollout, and production SLOs remain outside this slice.

### Public Identity Lifecycle Remains Local

Public principal mapping, token/session lifecycle, invitations, OAuth/OIDC, and public role/policy mutation APIs remain future work.

### Retention Execution Is Not Implemented

The schema now supports retention scans, but no cleanup job, export path, deletion API, or customer-visible decision history exists.

### Observability Is Local Evidence Only

The artifact proves metadata and counters locally. Production metrics/logs/traces still need real instrumentation in the eventual gateway process.

### Schema Migration Strategy Remains Local

The schema file is hardened, but there is still no production migration/versioning rollout plan for already-deployed databases.

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
- real production gateway deployment

## Stage Completion Estimate

Hosted permission decision persistence production-boundary lane:

```text
100%
```

The local production-boundary proof is complete and accepted for v0. The broader Hosted Control Plane phase is not complete because public identity lifecycle, production deployment, policy mutation, retention execution, and customer-visible history remain future work.

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Hosted Permission Decision Persistence Stage Closeout + Readiness Review v0
```

Why:

- decision persistence has now passed design, implementation, integrity hardening, production-boundary design, production-boundary implementation, and live dogfood closeout.
- before opening a new hosted-readiness lane, the repository should record whether the full decision-persistence lane is complete for local v0.
- the next gap should be chosen from remaining hosted risks rather than automatically expanding product scope.

Expected scope:

- summarize the full hosted permission decision persistence lane.
- decide whether the lane is complete for local v0.
- rank remaining hosted-readiness risks.
- choose the next narrow task without starting public CRUD, OAuth/OIDC, production deployment, billing, marketplace, vault, workflow, policy write APIs, automatic propagation, or Data Plane mutable reads.
