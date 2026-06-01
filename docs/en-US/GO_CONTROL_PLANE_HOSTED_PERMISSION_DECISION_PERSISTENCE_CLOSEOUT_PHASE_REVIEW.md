# Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0

Date: 2026-06-02

Status: complete

## Decision

The Hosted Permission Decision Persistence implementation slice can close for v0.

The repository now proves that the local hosted admin gateway can persist non-secret hosted permission decision evidence for authenticated allowed, denied, and source-unavailable decisions while preserving gateway-local auth failures, fail-closed forwarding behavior, Control Plane second-gate authorization, and secret-safe artifacts.

Recommended next task:

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Design v0
```

That task should remain a design/hardening task. It should focus on duplicate decision integrity, partial-failure row semantics, sentinel/schema hardening options, and metadata retention/privacy. It must not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, policy write APIs, or Data Plane reads from mutable Control Plane tables.

## What Is Now Complete

### Gateway-Owned Persistence

Completed:

- local hosted admin gateway persistence helper for `hosted_permission_decisions`
- append-only writes after permission decision resolution and before allowed forwarding
- authenticated allowed, denied, and source-unavailable decision persistence
- missing/invalid public auth persistence skip
- unknown route and unsupported method remain outside persistence
- source-unavailable sentinel subject and policy evidence
- bounded metadata with request, route, gateway key, status, error type, permission source, and persistence version
- local failure evidence for persistence write failures

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

Completed:

- local Postgres schema apply
- hosted permission seed data plus source-unavailable sentinel seed data
- private Control Plane in trusted-gateway mode
- gateway in hosted read-model permission-source mode with decision persistence enabled
- allowed, denied, source-unavailable, readonly, second-gate, partition, replay, and import cases
- secret-safe persisted-row checks
- redacted JSON artifact output

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| gateway owns hosted permission decision persistence | passed |
| allowed authenticated decisions persist before forwarding | passed |
| denied authenticated decisions persist before local denial response | passed |
| source-unavailable authenticated decisions persist with sentinel evidence when needed | passed |
| missing/invalid public auth does not persist hosted decision rows | passed |
| unknown route/method does not persist hosted decision rows | passed |
| allowed decision persistence failure fails closed before forwarding | passed |
| denied/source-unavailable persistence failure preserves original fail-closed response and records local evidence | passed |
| persisted metadata excludes public bearer tokens, `Authorization`, cookies, gateway secrets, OAuth tokens, plaintext credentials, and vault material | passed |
| live dogfood proves expected persisted row count and row families | passed |
| Control Plane audit/idempotency boundaries remain unchanged for gateway-local failures | passed |
| public CRUD, OAuth/OIDC, production gateway, marketplace, vault, billing, workflow, automatic propagation, policy write APIs, and Data Plane mutable reads remain out of scope | passed |
| duplicate decision id with different evidence raises an explicit integrity error | deferred risk |

## Dogfood Evidence

Observed:

- `status=passed`
- `audit_counts.hosted_permission_decisions=15`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`
- `permission_decision_rows_after_invalid_public_auth=0`
- `persistence_unavailable_status=503`
- `persistence_unavailable_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- decision status counts: `200=7`, `403=5`, `503=3`
- required permission counts: `validate=9`, `import_replace=2`, `project_partition_replace=4`

The dogfood artifact also proves:

- missing and invalid public auth left hosted decision rows at `0`.
- unsupported path returned `404 PUBLIC_ROUTE_NOT_FOUND`.
- unsupported method returned `405 PUBLIC_METHOD_NOT_ALLOWED`.
- allowed persistence failure returned `503 PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE` before Control Plane audit rows were created.
- readonly mutation attempts persisted denied decision rows and did not create Control Plane audit/idempotency rows.
- forced insufficient forwarded permissions produced an allowed gateway decision and then `403 AUTHZ_DENIED` from the Control Plane second gate.
- persisted rows did not contain raw public tokens, caller `Authorization`/`Cookie` material, or the trusted gateway secret.

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
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

This implementation slice is complete for local v0.

The main risk from the previous milestone was whether permission decisions could be recorded without weakening the hosted admin gateway contract. The live proof shows the answer is yes: public auth failures remain gateway-local and do not create decision rows, authenticated decisions persist before allow/deny completion, allowed write failure blocks forwarding, local denials still avoid Control Plane mutation/audit paths, and the private Control Plane remains the second authorization gate.

The implementation deliberately remains local/dogfood-scoped. It proves the request-time ownership and evidence boundary, not production retention, policy mutation, public identity lifecycle, or gateway operations.

## Remaining Risks

### Duplicate Decision Integrity Needs Hardening

The implementation uses deterministic decision IDs and `ON CONFLICT (id) DO NOTHING`. That is deterministic, but it does not yet prove byte-equivalent duplicate evidence or raise an explicit integrity error for conflicting evidence. This should be the next hardening design topic.

### Sentinel Fields Are A v0 Compatibility Choice

Source-unavailable decisions use sentinel subject/actor/org/policy values to satisfy current `NOT NULL` and FK constraints. That keeps the local proof simple, but production schema semantics may need nullable partial-failure fields, dedicated sentinel rows, or a stricter failure-evidence table shape.

### Persistence Is Still Harness-Scoped

The gateway harness writes through local SQL execution. Production gateway integration still needs explicit service/process boundary, connection lifecycle, retry/backoff, observability, and rollout design.

### Retention And Tenant Privacy Are Deferred

Append-only decision records are useful for auditability, debugging, and abuse investigation, but production retention, export, deletion, and tenant privacy controls are not implemented.

### No Real Public Identity Or Policy Write Lifecycle

Public token mapping and hosted permission seed data remain local/dogfood. OAuth/OIDC, login/session/invitation lifecycle, and hosted policy mutation APIs remain future work.

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
- policy write APIs
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Design v0
```

Why:

- the persistence proof is now working against live Postgres.
- duplicate/conflicting decision evidence is the largest remaining correctness gap inside the persistence boundary.
- sentinel row semantics are acceptable for v0 but should be deliberately hardened before production-shaped persistence.
- metadata retention/privacy needs a design before decision rows become durable product data.
- this can be designed without starting public CRUD, OAuth/OIDC, production gateway deployment, billing, marketplace, workflow, or automatic propagation.

Expected scope:

- define duplicate decision conflict behavior and tests.
- decide whether to keep, constrain, or replace sentinel evidence for partial failures.
- define metadata allowlist, redaction, and retention expectations.
- define any schema/index/constraint changes needed for persistence integrity.
- define live dogfood evidence for the hardening slice.

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
- policy write APIs
- Data Plane mutable Control Plane table reads
