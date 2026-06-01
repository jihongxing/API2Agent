# Go Control Plane Hosted Permission Decision Persistence Stage Closeout + Readiness Review v0

Date: 2026-06-02

Status: complete

## Decision

The full Hosted Permission Decision Persistence lane can close for local v0.

API2Agent now has a local, production-shaped proof that the hosted admin gateway can resolve hosted permission decisions, persist secret-safe evidence, fail closed before forwarding when required evidence cannot be written, preserve duplicate/conflict integrity, and expose enough metadata for future retention, history, and operations work.

Recommended next task:

```text
Go Control Plane Hosted Permission Decision Retention + Customer History Boundary Design v0
```

That task should design retention, customer-visible history, export/delete boundaries, access control, auditability, and operator evidence for persisted hosted permission decisions. It must not add public CRUD, OAuth/OIDC, invitation/session lifecycle, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, policy write APIs, Data Plane reads from mutable Control Plane tables, or real production gateway deployment.

## Lane Summary

The decision-persistence lane completed these slices:

```text
Go Control Plane Hosted Permission Decision Persistence Design v0
Go Control Plane Hosted Permission Decision Persistence Implementation v0
Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Design v0
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Implementation v0
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Closeout + Phase Review v0
Go Control Plane Hosted Permission Decision Persistence Production Boundary Design v0
Go Control Plane Hosted Permission Decision Persistence Production Boundary Implementation v0
Go Control Plane Hosted Permission Decision Persistence Production Boundary Live Dogfood + Closeout v0
```

## What Is Now Complete

### Request-Time Decision Evidence

Completed:

- hosted admin gateway resolves permission decisions through the hosted permission read model.
- authenticated allowed, denied, and source-unavailable decisions can be persisted.
- missing/invalid public auth and unknown routes remain outside decision persistence.
- allowed write failure fails closed before private Control Plane forwarding.
- local denials and source-unavailable responses preserve gateway-local failure semantics.
- private Control Plane remains the second authorization gate for forwarded requests.

References:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_CLOSEOUT_PHASE_REVIEW.md`

### Integrity Hardening

Completed:

- canonical controlled-evidence comparison for duplicate decision ids.
- equivalent duplicates are accepted as no-op success.
- conflicting duplicates return `PERMISSION_DECISION_INTEGRITY_CONFLICT`.
- allowed integrity conflicts fail closed before private Control Plane audit/idempotency writes.
- sentinel constraints reject invalid allowed evidence while preserving source-unavailable sentinel evidence.
- persisted metadata remains bounded and secret-safe.

References:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_CLOSEOUT_PHASE_REVIEW.md`

### Production-Shaped Boundary

Completed:

- gateway-owned in-process persistence writer.
- bounded write timeout and transient retry budget.
- fail-closed behavior for persistence unavailable and timeout cases.
- canonical `evidence_fingerprint` on persisted rows.
- `production_boundary_version=hosted-permission-decision-production-boundary-v0` metadata.
- tenant/time, subject/time, retention, and policy-fingerprint indexes.
- secret-safe live Postgres dogfood artifact proving 16 persisted decision rows.

References:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`

## Evidence Review

Accepted evidence:

- base persistence dogfood: `15` hosted permission decision rows.
- integrity hardening dogfood: duplicate-equivalent and duplicate-conflict probes keep row count stable at `15`.
- production-boundary dogfood: `16` hosted permission decision rows.
- production-boundary dogfood: `16/16` rows include `evidence_fingerprint`.
- production-boundary dogfood: `16/16` rows include `production_boundary_version=hosted-permission-decision-production-boundary-v0`.
- production-boundary dogfood: `permission_decision_retry_count=1`.
- production-boundary dogfood: `permission_decision_timeout_count=1`.
- production-boundary dogfood: unavailable and timeout persistence failures return `PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`.
- production-boundary dogfood: allowed persistence unavailable and timeout probes create `0` private Control Plane audit rows.
- production-boundary dogfood: integrity conflict returns `PERMISSION_DECISION_INTEGRITY_CONFLICT`.
- production-boundary dogfood: integrity conflict leaves hosted decision row count stable at `16`.

Artifacts:

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
.dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
.dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| decision persistence design is complete | passed |
| gateway-owned request-time persistence is implemented | passed |
| allowed decisions fail closed when persistence cannot write required evidence | passed |
| denied/source-unavailable decisions persist secret-safe evidence | passed |
| missing/invalid public auth stays outside persistence | passed |
| duplicate-equivalent evidence is stable | passed |
| duplicate-conflicting evidence fails explicitly | passed |
| allowed integrity conflict fails before Control Plane forwarding/audit | passed |
| production-shaped retry/timeout behavior is implemented locally | passed |
| persisted rows carry canonical evidence fingerprints | passed |
| persisted rows carry production-boundary metadata | passed |
| tenant/time, subject/time, retention, and conflict-investigation indexes exist | passed |
| live dogfood proves secret-safe artifacts | passed |
| retention/customer-history design is complete | next task |
| real production gateway deployment is complete | deferred |
| public identity lifecycle and policy mutation APIs are complete | deferred |

## Completion Estimate

Hosted permission decision persistence lane:

```text
100%
```

This lane is accepted as complete for local v0.

Hosted Control Plane phase:

```text
70%
```

This is an estimate, not a formal product-completion claim. The local hosted-readiness foundation is strong, but the broader Hosted Control Plane still lacks retention execution, customer-visible decision history, real public identity lifecycle, hosted policy mutation APIs, production gateway deployment, production migration rollout, vault/billing/marketplace/workflow surfaces, and Data Plane mutable-read decisions.

## Remaining Hosted-Readiness Risks

### Decision Retention And Customer History

The schema has retention-friendly indexes, but there is no retention policy execution, customer-visible decision history, export path, delete path, access-control model, or audit trail for viewing decision evidence. This is now the highest-signal next design boundary.

### Real Public Identity Lifecycle

Public principal mapping is still dogfood/local. OAuth/OIDC, invitations, sessions, organization/project membership lifecycle, and external subject lifecycle remain future work.

### Hosted Policy Mutation Lifecycle

Hosted roles, grants, memberships, and policy versions are seeded for local proof. There is still no policy write API, review flow, promotion flow, rollback story, or tenant admin UX/API.

### Production Gateway Deployment

The local harness proves the contract a production gateway must preserve. It does not deploy TLS, private networking, rate limits, rollout controls, production health/readiness, SLOs, or production observability.

### Production Migration And Operations

Schema hardening exists in the local schema file, but production migration ordering, backfills, compatibility windows, rollback, cleanup jobs, metrics, traces, and alerting remain future work.

### Product Surface Boundaries

Vault writes, billing, marketplace/provider onboarding, workflow runtime, automatic propagation, and Data Plane reads from mutable Control Plane tables remain intentionally deferred.

## Ranked Next Work

1. `Go Control Plane Hosted Permission Decision Retention + Customer History Boundary Design v0`
2. `Go Control Plane Hosted Permission Policy Mutation Boundary Design v0`
3. `Go Control Plane Hosted Public Identity Lifecycle Boundary Design v0`
4. `Go Control Plane Hosted Gateway Production Deployment Boundary Design v0`

The first item should go next because decision rows are now durable local product evidence. Before exposing them or retaining them long-term, the project needs a deliberate boundary for customer history, privacy, export, deletion, access, and operator audit.

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

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Hosted Permission Decision Retention + Customer History Boundary Design v0
```

Expected scope:

- define retention classes and default retention stance for hosted permission decisions.
- define whether and how customers can query decision history.
- define export, deletion, legal hold, and audit boundaries.
- define access control for tenant admins, project admins, support operators, and internal systems.
- define privacy redaction requirements for decision evidence.
- define implementation/dogfood evidence required before any customer-visible history endpoint.

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
- real production gateway deployment
