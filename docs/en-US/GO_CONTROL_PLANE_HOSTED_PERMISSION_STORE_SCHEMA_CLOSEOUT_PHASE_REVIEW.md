# Go Control Plane Hosted Permission Store Schema Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Hosted Permission Store Schema implementation slice can close.

The repository now has a durable Postgres schema boundary for hosted permission-store lookup:

```text
hosted_subjects
  -> hosted_project_memberships
  -> hosted_role_bindings
  -> hosted_roles
  -> hosted_permission_grants
  -> hosted_policy_versions
  -> hosted_permission_decisions
```

Recommended next task:

```text
Go Control Plane Hosted Permission Store Read Model v0
```

That task should add an internal read model over the schema and prove it can return the same permission decision shape as the local harness. It must not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, or Data Plane reads from mutable Control Plane tables.

## What Is Now Complete

### Design

Completed:

- durable permission-store entities and relationships
- gateway lookup input/output contract
- endpoint permission mapping for six hosted admin routes
- fail-closed semantics for unavailable, ambiguous, stale, missing, revoked, or denied policy
- consistency and cache expectations
- policy source/version/fingerprint/decision evidence requirements
- non-goals for public CRUD, OAuth/OIDC, production gateway, marketplace, vault, billing, workflow, and automatic propagation

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_DESIGN.md`

### Contract Harness

Completed:

- store-shaped local fixture/read model
- public principal to subject resolution
- membership, role binding, and permission grant lookup
- policy source/version/fingerprint/decision evidence
- gateway-local missing membership, suspended membership, revoked permission, unavailable store, and stale policy denial
- Control Plane second-gate denial proof

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`

### Schema

Completed in `services/control-plane/schema/postgres/001_persistent_registry_store.sql`:

- `hosted_subjects`
- `hosted_project_memberships`
- `hosted_roles`
- `hosted_role_bindings`
- `hosted_permission_grants`
- `hosted_policy_versions`
- `hosted_permission_decisions`

Added constraints and indexes for:

- unique non-empty external subject references
- one membership per subject/project
- membership project/status lookup
- active role binding uniqueness
- role binding project/status lookup
- active permission grant uniqueness
- permission/status grant lookup
- policy source/version uniqueness
- one active policy version per policy source
- decision lookup by subject/project/resolved time
- decision lookup by policy version
- `sha256:` policy fingerprint format

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| durable schema/read boundary is explicit | passed |
| schema represents hosted subjects | passed |
| schema represents project memberships and active/suspended/revoked state | passed |
| schema represents hosted roles | passed |
| schema represents role bindings | passed |
| schema represents permission grants | passed |
| schema represents policy versions and active version uniqueness | passed |
| schema represents permission decision evidence | passed |
| schema can preserve policy source/version/fingerprint/decision id | passed |
| schema supports fail-closed lookup semantics for membership, revocation, stale policy, and endpoint permission denial | passed |
| raw public tokens, raw session tokens, OAuth tokens, gateway secrets, plaintext API keys, and vault material remain out of schema | passed |
| runtime read wiring remains deferred | passed |
| no public CRUD, OAuth/OIDC, production gateway, marketplace, vault, billing, workflow, or automatic propagation scope was added | passed |

## Dogfood Evidence

Live dogfood artifact:

```text
.dogfood/go-control-plane-hosted-permission-store-schema/report.json
```

Observed:

- `status=passed`
- schema apply succeeded with the new hosted permission tables present
- service health returned `status=ok`
- gateway health returned `status=ok`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `import_status=201`
- audit counts were `registry_revisions=3`, `admin_audit_events=5`, `idempotency_records=2`
- audit/idempotency rows did not contain gateway secrets, raw public tokens, or spoofed public identity

## Validation

Passed:

```text
go test ./internal/registry -run "TestPersistentRegistrySQLSchemaContainsHostedPermissionStoreBoundary|TestHostedPermissionStoreSchemaDoesNotPersistRawSecrets|TestPersistentRegistrySQLSchemaContainsRequiredTablesAndConstraints"
go test ./...
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-store-schema/report.json
git diff --check
```

Go test directory:

```text
services/control-plane
```

## Closeout Judgment

This implementation slice is complete.

The schema satisfies the v0 hosted permission-store boundary. It can represent the contract harness read path and evidence shape without storing raw public tokens, gateway secrets, plaintext API keys, OAuth tokens, session tokens, or vault material.

The schema is intentionally not wired into runtime gateway lookup yet. That separation is the point of this slice: it gives the next read-model task a durable boundary to target while keeping public management surfaces and production gateway behavior out of scope.

## Remaining Risks

### No Runtime Read Model Yet

The schema exists, but no Go read model resolves hosted permission decisions from it yet.

### No Seed Or Migration Lifecycle Beyond The Draft Schema

The current project still uses a single schema draft for local dogfood. Migration ordering, rollbacks, and production deployment lifecycle remain future work.

### No Policy Write Path

There is still no public or internal policy mutation API. Role/user/project management remains intentionally out of scope.

### No Real Public Identity Lifecycle

OAuth/OIDC, login, session, invitation, and external subject lifecycle are still future work.

### No Production Gateway Deployment

The gateway remains local dogfood tooling. Production routing, TLS, private network enforcement, observability, rate limits, and rollout remain future work.

### Cache/Consistency Still Needs Runtime Proof

The schema has policy version and fingerprint fields, but runtime transaction/read consistency is not implemented yet.

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
Go Control Plane Hosted Permission Store Read Model v0
```

Why:

- the lookup contract is designed
- the local harness proves behavior
- the durable schema exists
- the next risk is whether Go code can resolve the same decision shape from the schema while preserving fail-closed semantics and secret-safe evidence

Expected scope:

- add an internal Go read model over the hosted permission tables
- resolve subject, membership, role binding, grants, active policy version, and decision evidence
- return a local decision shape compatible with the gateway contract
- prove missing membership, suspended membership, revoked grants, stale/no active policy, and missing permission fail closed
- keep the implementation private/internal and test-only or seeded for v0

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
