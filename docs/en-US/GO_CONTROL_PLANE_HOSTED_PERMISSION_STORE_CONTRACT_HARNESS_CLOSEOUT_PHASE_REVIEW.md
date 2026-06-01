# Go Control Plane Hosted Permission Store Contract Harness Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Hosted Permission Store Contract Harness implementation slice can close.

The repository now proves the hosted permission-store lookup boundary in the local gateway harness:

```text
public authenticated principal
  -> hosted permission-store-shaped read model
  -> hosted subject
  -> project membership
  -> role bindings
  -> permission grants
  -> policy version/fingerprint/decision evidence
  -> gateway-issued trusted X-API2Agent-* claims
  -> Control Plane endpoint permission check
  -> Postgres audit/idempotency evidence
```

Recommended next task:

```text
Go Control Plane Hosted Permission Store Schema v0
```

That task should introduce the durable schema/read boundary for the hosted permission store without adding public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, or Data Plane reads from mutable Control Plane tables.

## What Is Now Complete

### Design

Completed:

- durable hosted permission-store boundary
- store model for subjects, project memberships, roles, role bindings, permission grants, policy versions, and optional decisions
- gateway lookup input/output contract
- endpoint permission mapping for six hosted admin routes
- fail-closed semantics for unavailable, ambiguous, stale, or denied policy
- consistency and cache expectations
- secret-safe audit/report evidence requirements
- contract harness plan and non-goals

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_DESIGN.md`

### Contract Harness

Completed:

- store-shaped local fixture/read model in the hosted admin gateway harness
- public principal to hosted subject resolution
- active project membership enforcement
- role binding and permission grant resolution
- policy source, version, fingerprint, required permission, and decision id evidence
- safe policy evidence headers forwarded as metadata only
- gateway-local fail-closed denial for missing membership, suspended membership, revoked permission, unavailable store, and stale policy
- endpoint mapping for:
  - `POST /v1/admin/registry/validate`
  - `POST /v1/admin/registry/import-replace`
  - `POST /v1/admin/registry/project-partition/replace`
  - `POST /v1/admin/snapshots/export-artifact`
  - `GET /v1/admin/distribution/current`
  - `POST /v1/admin/distribution/publish`
- Control Plane second-gate proof for insufficient trusted permissions
- regression tests for store lookup, failure typing, trusted header injection, policy evidence headers, and endpoint permission mapping

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| gateway lookup contract is proven through local harness tests | passed |
| store-shaped subject, membership, role binding, and grant lookup is explicit | passed |
| unavailable store fails closed before forwarding | passed |
| missing membership fails closed before forwarding | passed |
| suspended membership fails closed before forwarding | passed |
| revoked permission fails closed before forwarding | passed |
| stale policy view fails closed before forwarding | passed |
| endpoint permission absence fails closed before forwarding | passed |
| policy source/version/fingerprint/decision id evidence is present | passed |
| policy evidence remains secret-safe | passed |
| Control Plane second-gate denial remains covered | passed |
| hosted project mutation uses `control_plane.registry.project_partition_replace` | passed |
| broad import/replace is not required for hosted project mutation | passed |
| no public CRUD, OAuth/OIDC, production gateway, marketplace, vault, billing, workflow, or automatic propagation scope was added | passed |

## Dogfood Evidence

Live dogfood artifact:

```text
.dogfood/go-control-plane-hosted-permission-store-contract-harness/report.json
```

Observed:

- `status=passed`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `permission_source=hosted-permission-store-fixture`
- `policy_version=hosted-policy-v1`
- `policy_fingerprint=sha256:hosted-permission-store-fixture-v1`
- permission decisions include `decision_id` and `required_permission`
- endpoint permission map covers all six hosted admin routes
- gateway-local denials did not create Control Plane audit/idempotency rows
- Control Plane second gate returned `403 AUTHZ_DENIED` for insufficient trusted permissions
- partition mutation succeeded with `partition_status=201`
- partition replay returned `partition_replay_status=200`
- partition violation returned `partition_violation_status=403`
- audit counts were `registry_revisions=3`, `admin_audit_events=5`, `idempotency_records=2`
- raw public tokens, gateway secrets, spoofed identities, session tokens, and vault material were absent from evidence

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-store-contract-harness/report.json
git diff --check
```

Go test directory:

```text
services/control-plane
```

## Closeout Judgment

This implementation slice is complete.

The contract harness satisfies the hosted permission store v0 design as a local proof. It demonstrates the intended read path, policy evidence, gateway-local fail-closed behavior, and Control Plane second gate without adding durable storage or public management surfaces.

The harness is not production authorization. It is sufficient for v0 because it proves the shape and safety properties that a durable schema/read implementation must preserve.

## Remaining Risks

### No Durable Schema Yet

The permission store is still a local fixture. The next task should introduce durable schema and read-model boundaries before any production behavior depends on it.

### No Policy Write Path

There is no mutation API, role CRUD, invitation flow, or user-management lifecycle. That remains intentional until the durable read path and hosted product boundaries are safer.

### No Real Public Identity Lifecycle

OAuth/OIDC, login, session, invitation, and external subject lifecycle are still future work.

### No Production Gateway Deployment

The gateway remains local dogfood tooling. Production routing, TLS, private network enforcement, observability, rate limits, and rollout are future work.

### Cache/Consistency Is Still Contractual

The harness proves fail-closed stale policy behavior, but there is no durable transaction or policy version table yet.

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
Go Control Plane Hosted Permission Store Schema v0
```

Why:

- the durable permission-store boundary is designed
- the local contract harness proves lookup semantics and failure behavior
- the remaining gap is a durable schema/read model that can preserve policy version, fingerprint, membership state, role bindings, and permission grants
- schema work can stay private/internal and avoid public CRUD, OAuth/OIDC, and production gateway scope

Expected scope:

- define and add hosted permission store tables/migrations or equivalent schema artifacts
- preserve a read-only/seeded implementation boundary
- support subject, membership, role, role binding, permission grant, policy version, and decision evidence
- keep gateway-local fail-closed behavior
- add schema/read tests and secret-safe evidence checks

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
