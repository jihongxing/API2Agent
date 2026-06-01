# Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood Closeout + Phase Review v0

Date: 2026-06-02

Status: complete

## Decision

The Hosted Permission Store Read Model Live Postgres Dogfood slice can close.

The repository now proves the hosted permission read model against a real local Postgres database with the actual Control Plane schema, seeded hosted permission rows, pgx lookup, fail-closed cases, zero decision persistence, and secret-safe artifact output.

Recommended next task:

```text
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Design v0
```

That task should design how the hosted admin gateway can use the internal read model as its permission source. It must remain a design task and must not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, or Data Plane reads from mutable Control Plane tables.

## What Is Now Complete

### Read Model

Completed:

- internal Go read model over hosted permission tables
- repeatable-read/read-only transaction semantics
- active policy version lookup
- subject lookup by external subject reference
- project membership lookup
- active role and grant lookup
- gateway-compatible decision evidence
- fail-closed missing membership, suspended membership, revoked/missing permission, no active policy, and ambiguous active policy
- no hosted decision persistence in v0

References:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_CLOSEOUT_PHASE_REVIEW.md`

### Live Postgres Dogfood

Completed:

- local Postgres 16 container startup
- schema apply from `services/control-plane/schema/postgres/001_persistent_registry_store.sql`
- harness project seeding through `seed-postgres`
- hosted subject, membership, role, binding, grant, and policy version seeding
- real pgx DSN lookup through the internal read model
- redacted artifact generation

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_LIVE_POSTGRES_DOGFOOD_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| real local Postgres database is used | passed |
| actual Control Plane schema is applied | passed |
| hosted permission rows are seeded | passed |
| internal read model is called through pgx against a real DSN | passed |
| allowed admin decision returns `200` and permission evidence | passed |
| readonly missing permission fails closed as `403 PUBLIC_AUTHZ_DENIED` | passed |
| missing membership fails closed as `403 PUBLIC_AUTHZ_DENIED` | passed |
| suspended membership fails closed as `403 PUBLIC_AUTHZ_DENIED` | passed |
| revoked grant fails closed as `403 PUBLIC_AUTHZ_DENIED` | passed |
| no active policy fails closed as `503 PERMISSION_SOURCE_UNAVAILABLE` | passed |
| ambiguous active policy fails closed as `503 PERMISSION_SOURCE_UNAVAILABLE` | passed |
| policy source/version/fingerprint/decision id evidence is present | passed |
| artifact output redacts DSN password, public bearer tokens, and gateway secret | passed |
| `hosted_permission_decisions` remains empty in v0 | passed |
| gateway runtime wiring remains deferred | passed |
| no public CRUD, OAuth/OIDC, production gateway, marketplace, vault, billing, workflow, or automatic propagation scope was added | passed |

## Dogfood Evidence

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-read-model-live-postgres/report.json
```

Observed:

- `status=passed`
- `hosted_subjects=5`
- `hosted_project_memberships=4`
- `hosted_roles=4`
- `hosted_role_bindings=6`
- `hosted_permission_grants=9`
- `hosted_policy_versions=1` before ambiguous-policy case
- `hosted_policy_versions=2` after ambiguous-policy case
- `hosted_permission_decisions=0`
- `secret_safe_evidence=true`
- admin import/replace allowed with policy fingerprint `sha256:hosted-permission-store-fixture-v1`
- readonly import/replace denied locally by missing permission
- missing membership, suspended membership, revoked grant, no active policy, and ambiguous active policy all failed closed

## Validation

Passed:

```text
go test ./cmd/api2agent-hosted-permission-read-model-dogfood ./internal/registry -run HostedPermission
go test ./...
python -m py_compile scripts/go_control_plane_hosted_permission_read_model_dogfood.py
python scripts/go_control_plane_hosted_permission_read_model_dogfood.py --output .dogfood/go-control-plane-hosted-permission-read-model-live-postgres/report.json
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
git diff --check
git diff --cached --check
```

Go test directory:

```text
services/control-plane
```

Python test and diff-check directory:

```text
repository root
```

## Closeout Judgment

This dogfood slice is complete.

The live proof removes the main uncertainty left by the scripted read-model tests: the schema, constraints, seeded rows, SQL queries, pgx driver, and decision evidence all work together against a real Postgres database.

The implementation intentionally remains unwired from gateway runtime request handling. That boundary is still correct. The next step should be a runtime wiring design that specifies how the gateway obtains public principal context, calls the read model, maps decision evidence into trusted headers, handles unavailable/stale policy, and preserves the Control Plane second gate.

## Remaining Risks

### No Gateway Runtime Wiring Yet

The local gateway contract harness still uses a local/static permission source. The internal read model is not yet called during gateway request handling.

### No Decision Persistence Yet

The read model returns decision evidence but does not insert into `hosted_permission_decisions`.

### No Seed Or Migration Lifecycle Beyond Dogfood

The dogfood uses direct seed SQL. Production migration ordering, rollback behavior, seed lifecycle, and policy promotion remain future work.

### No Policy Write Path

Hosted policy, role, grant, and membership mutation remain out of scope. There is still no public or internal policy management API.

### No Real Public Identity Lifecycle

OAuth/OIDC, login, session, invitation, and external subject lifecycle remain future work.

### No Production Gateway Deployment

Production routing, TLS, private network enforcement, observability, rate limits, rollout, and operational hardening remain future work.

### Provider Ownership Still Needs Hardening

Project-scoped registry mutation is constrained, but provider ownership remains metadata-based in v0.

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
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Design v0
```

Why:

- the gateway permission-source contract exists
- the local harness proves gateway semantics
- the hosted permission schema exists
- the internal read model exists
- real Postgres dogfood now proves the SQL path
- the next risk is how to wire the gateway to the read model without weakening fail-closed behavior, trusted-header safety, Control Plane second-gate authority, or non-goal boundaries

Expected scope:

- design the gateway runtime permission-source interface for the hosted read model.
- define public principal input, external subject reference handling, project context, token id evidence, timeout/unavailable behavior, and stale/ambiguous policy handling.
- define trusted header mapping from read-model decisions.
- define tests and dogfood needed for runtime wiring.
- keep decision persistence, production deployment, OAuth/OIDC, public CRUD, and policy management out of scope.

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
