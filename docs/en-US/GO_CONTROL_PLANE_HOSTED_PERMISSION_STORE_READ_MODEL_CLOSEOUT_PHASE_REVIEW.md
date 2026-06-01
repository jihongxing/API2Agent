# Go Control Plane Hosted Permission Store Read Model Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Hosted Permission Store Read Model implementation slice can close.

The repository now has an internal Go read model that resolves hosted permission decisions from the hosted permission tables with repeatable-read/read-only transaction semantics.

Recommended next task:

```text
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood v0
```

That task should seed the hosted permission tables in a real local Postgres database and prove the same allow/deny evidence works against the actual schema and SQL. It must not wire the production gateway runtime, add public role CRUD, add OAuth/OIDC, add invitation/session lifecycle, deploy a production gateway, add marketplace/provider onboarding, write vault material, add billing, add workflow runtime, trigger automatic propagation, or let the Data Plane read mutable Control Plane tables.

## What Is Now Complete

### Design And Contract

Completed before this slice:

- durable permission-store entity model
- gateway lookup request/decision contract
- endpoint permission mapping for hosted admin routes
- fail-closed semantics for unavailable, ambiguous, stale, missing, revoked, or denied policy
- policy source/version/fingerprint/decision evidence requirements
- secret-safe evidence expectations

References:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`

### Schema

Completed before this slice:

- `hosted_subjects`
- `hosted_project_memberships`
- `hosted_roles`
- `hosted_role_bindings`
- `hosted_permission_grants`
- `hosted_policy_versions`
- `hosted_permission_decisions`

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_CLOSEOUT_PHASE_REVIEW.md`

### Read Model

Completed in:

```text
services/control-plane/internal/registry/hosted_permission_store.go
```

The read model now:

- requires an explicit DB.
- starts a repeatable-read, read-only transaction.
- accepts exactly one active hosted policy version.
- resolves hosted subject by external subject reference.
- resolves project membership for the requested project.
- resolves active role bindings and active hosted roles.
- resolves active permission grants.
- returns a gateway-compatible local decision with identity, roles, permissions, required permission, policy source/version/fingerprint, decision id, and resolved time.
- fails closed for missing membership, inactive membership, missing permission, missing active policy, and ambiguous active policy.
- does not persist `hosted_permission_decisions` in v0.

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| internal Go read model exists over hosted permission tables | passed |
| lookup uses repeatable-read/read-only transaction semantics | passed |
| active policy version is part of the decision evidence | passed |
| ambiguous/no active policy fails closed as `503 PERMISSION_SOURCE_UNAVAILABLE` | passed |
| hosted subject lookup is resolved by external subject reference | passed |
| missing/inactive subject fails closed | passed |
| project membership is resolved for the requested project | passed |
| missing membership fails closed as `403 PUBLIC_AUTHZ_DENIED` | passed |
| suspended membership fails closed as `403 PUBLIC_AUTHZ_DENIED` | passed |
| active roles and permission grants are resolved | passed |
| revoked/missing required permission fails closed | passed |
| decision shape is compatible with the gateway contract evidence | passed |
| raw public tokens, gateway secrets, OAuth tokens, refresh tokens, and plaintext material remain out of decision evidence | passed |
| read model does not write hosted decision rows in v0 | passed |
| gateway runtime wiring remains deferred | passed |
| no public CRUD, OAuth/OIDC, production gateway, marketplace, vault, billing, workflow, or automatic propagation scope was added | passed |

## Validation

Passed:

```text
go test ./internal/registry -run HostedPermission
go test ./...
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

This implementation slice is complete.

The read model proves that Go code can resolve the hosted permission decision shape from the hosted permission schema while preserving the gateway contract, fail-closed behavior, transaction consistency, and secret-safe evidence boundary.

The implementation intentionally remains internal and unwired from the hosted gateway runtime. That is the correct v0 boundary: it proves the private lookup layer before expanding into live seeded database proof, runtime integration, decision persistence, or public management surfaces.

## Remaining Risks

### No Live Postgres Read-Model Dogfood Yet

The current proof uses a scripted SQL driver. The SQL shape still needs a real local Postgres dogfood with seeded hosted permission rows.

### No Gateway Runtime Wiring Yet

The local gateway contract harness still uses its local/static permission source. The Go read model is not yet used by gateway request handling.

### No Decision Persistence Yet

The read model returns decision evidence but does not insert into `hosted_permission_decisions`.

### No Seed Or Migration Lifecycle Beyond The Draft Schema

The repository still uses a single draft schema for local dogfood. Migration ordering, rollback behavior, and production deployment lifecycle remain future work.

### No Policy Write Path

Hosted policy, role, grant, and membership mutation remain out of scope. There is still no public or internal policy management API.

### No Real Public Identity Lifecycle

OAuth/OIDC, login, session, invitation, and external subject lifecycle remain future work.

### No Production Gateway Deployment

Production routing, TLS, private network enforcement, observability, rate limits, rollout, and operational hardening are still future work.

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
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood v0
```

Why:

- the schema exists
- the Go read model exists
- package tests prove behavior with scripted rows
- the next risk is whether the real Postgres schema, constraints, seeded rows, and SQL queries behave the same way in local dogfood

Expected scope:

- seed hosted permission tables in a local Postgres dogfood database.
- call the internal read model against real Postgres.
- prove allowed decision evidence and fail-closed missing membership, suspended membership, revoked/missing permission, and no/ambiguous active policy cases.
- assert evidence does not contain raw public tokens or gateway secrets.
- keep gateway runtime wiring and decision persistence deferred.

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
