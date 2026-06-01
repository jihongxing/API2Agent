# Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Closeout + Phase Review v0

Date: 2026-06-02

Status: complete

## Decision

The Hosted Permission Read Model Gateway Runtime Wiring slice can close.

The repository now proves that the local hosted admin gateway can use the internal hosted permission read model as its runtime permission source against a real local Postgres database, while preserving static fixture fallback, gateway-local fail-closed behavior, trusted-header safety, Control Plane second-gate authorization, zero decision persistence, and secret-safe evidence.

Recommended next task:

```text
Go Control Plane Hosted Permission Decision Persistence Design v0
```

That task should design append-only hosted permission decision persistence. It must remain a design task first, and must not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, or Data Plane reads from mutable Control Plane tables.

## What Is Now Complete

### Runtime Wiring

Completed:

- local Go lookup helper for gateway permission-source calls
- hosted read-model permission-source mode in the local gateway harness
- static fixture permission-source fallback for focused tests
- public bearer token consumption before read-model lookup
- non-secret public-principal evidence mapped to external subject refs
- read-model decisions converted into gateway-issued trusted headers
- caller-supplied public/trusted identity header stripping
- Control Plane endpoint permission checks preserved as the second gate
- no hosted decision persistence in this slice

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_READ_MODEL_GATEWAY_RUNTIME_WIRING_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

Completed:

- local Postgres 16 container startup
- schema apply from `services/control-plane/schema/postgres/001_persistent_registry_store.sql`
- registry seed through `seed-postgres`
- hosted permission seed rows in the gateway dogfood database
- private Control Plane in trusted-gateway mode
- local gateway harness in hosted read-model permission-source mode
- success, denial, stale/no-policy, ambiguous-policy, spoofing, and Control Plane second-gate cases over HTTP
- redacted JSON artifact output

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-read-model-gateway-runtime-wiring/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| gateway runtime has hosted read-model permission-source mode | passed |
| static fixture mode remains available for focused local tests | passed |
| real Postgres dogfood proves read-model-backed gateway decisions | passed |
| missing/invalid public auth remains gateway-local `401` | passed |
| missing membership fails gateway-local as `403 PUBLIC_AUTHZ_DENIED` | passed |
| suspended membership fails gateway-local as `403 PUBLIC_AUTHZ_DENIED` | passed |
| revoked/missing grant fails gateway-local as `403 PUBLIC_AUTHZ_DENIED` | passed |
| no active policy fails gateway-local as `503 PERMISSION_SOURCE_UNAVAILABLE` | passed |
| ambiguous active policy fails gateway-local as `503 PERMISSION_SOURCE_UNAVAILABLE` | passed |
| readonly validate succeeds and readonly mutation fails locally | passed |
| trusted header injection uses read-model decision evidence | passed |
| caller-supplied public/trusted identity headers are stripped | passed |
| Control Plane second gate rejects forced insufficient trusted permissions | passed |
| gateway-local denied requests do not create Control Plane audit/idempotency rows | passed |
| raw public tokens and gateway secret do not leak into evidence | passed |
| `hosted_permission_decisions` remains empty in v0 | passed |
| public CRUD, OAuth/OIDC, production gateway, marketplace, vault, billing, workflow, automatic propagation, and Data Plane mutable reads remain out of scope | passed |

## Dogfood Evidence

Observed:

- `status=passed`
- `missing_public_auth_status=401`
- `invalid_public_auth_status=401`
- `permission_source_unavailable_status=503`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `ambiguous_policy_status=503`
- `readonly_validate_status=200`
- `readonly_import_status=403`
- `readonly_partition_status=403`
- `insufficient_forward_status=403`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `import_status=201`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`
- `audit_counts.hosted_permission_decisions=0`

The dogfood artifact also proves:

- gateway-local failures left `admin_audit_events` at `0` before forwarded success cases.
- trusted-header spoofing did not affect audit principal, actor, project, organization, or token evidence.
- forced insufficient forwarded permissions reached the private Control Plane second gate and returned `403 AUTHZ_DENIED`.
- audit and idempotency rows do not contain gateway secrets or raw public bearer tokens.

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-read-model-gateway-runtime-wiring/report.json
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

This runtime wiring slice is complete.

The main risk from the previous milestone was whether the hosted admin gateway could use the internal read model without weakening the established gateway contract. The live proof shows the answer is yes: public auth remains gateway-local, project context remains gateway-derived, read-model evidence becomes trusted header evidence only after allow, local denials do not reach Control Plane mutation/audit paths, and the private Control Plane still enforces endpoint permissions as the second gate.

The static fixture fallback is also still useful. It keeps focused contract tests fast and local while the live dogfood covers the real Postgres/read-model path.

## Remaining Risks

### No Decision Persistence Yet

Runtime permission decisions have stable decision IDs and evidence, but `hosted_permission_decisions` remains empty. The next risk is designing append-only persistence without leaking secrets or creating write-path availability hazards.

### Lookup Helper Is Dogfood-Scoped

The gateway harness calls the read model through a local helper binary. That is acceptable for local dogfood, but a production gateway would need an in-process or service boundary design.

### No Real Public Identity Lifecycle

Public token to principal mapping remains local/dogfood. OAuth/OIDC, login, session, invitation, and external subject lifecycle remain future work.

### No Policy Write Path

Hosted role, grant, membership, and policy version mutation remain out of scope. Dogfood still uses direct seed SQL.

### No Production Gateway Deployment

TLS, private networking, rollout, rate limits, observability, operational health, and production routing remain future work.

### Provider Ownership Still Needs Hardening

Project-scoped mutation is constrained, but provider ownership remains metadata-based in v0.

## Still Not Allowed

Do not start:

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation/login/session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Hosted Permission Decision Persistence Design v0
```

Why:

- the hosted permission decision table already exists.
- the read model and gateway runtime now produce stable decision evidence.
- dogfood currently asserts zero persisted decision rows, which is the next explicit contract to change only by design.
- persistence is needed before production-grade auditability, debugging, and abuse investigation.
- this can be designed without adding public CRUD, OAuth/OIDC, production gateway deployment, billing, marketplace, workflow, or automatic propagation.

Expected scope:

- design append-only decision persistence shape and write timing.
- define success, denial, source-unavailable, and lookup-error persistence semantics.
- define secret-safe evidence and retention boundaries.
- define how persistence failures affect gateway allow/deny behavior.
- define idempotency/deduplication expectations for decision IDs.
- define tests and live dogfood needed before implementation.

Out of scope:

- public CRUD
- OAuth/OIDC
- invitation/session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- vault writes
- billing
- workflow runtime
- automatic publish/reload
- Data Plane mutable Control Plane table reads
