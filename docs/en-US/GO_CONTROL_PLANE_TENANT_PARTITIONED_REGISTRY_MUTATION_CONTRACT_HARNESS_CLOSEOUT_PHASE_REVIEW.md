# Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Tenant-Partitioned Registry Mutation Contract Harness slice can close.

The repository now has a local registry-layer contract proof for hosted project partition mutation:

```text
current registry
  + proposed full registry
  + resolved project scope
  -> partition diff validation
  -> allow same-project metadata/provider changes
  -> reject cross-project and platform/global changes
  -> stable partition decision evidence
```

Recommended next task:

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Design v0
```

That task should design, but not implement, a private hosted admin endpoint that uses the partition validator before registry replacement. It must not add public CRUD, public project/user/role CRUD, provider onboarding, marketplace, vault, billing, workflow runtime, automatic propagation, production gateway deployment, or Data Plane mutable-table reads.

## What Is Now Complete

### Design

Completed:

- tenant/project ownership boundary
- global/platform read-only object rules
- provider ownership metadata fallback for v0 harness
- partition diff validation algorithm
- separate permission and endpoint shape for future project partition mutation
- idempotency and audit evidence contract
- snapshot boundary preservation
- contract harness test plan

Reference:

- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_DESIGN.md`

### Implementation

Completed:

- `ValidateProjectPartitionMutation(current, proposed, projectID)`
- `ProjectPartitionMutationDecision`
- `ProjectPartitionMutationViolation`
- `ProjectPartitionMutationCounts`
- `registry.project_partition_replace` operation constant
- stable `REGISTRY_PARTITION_VIOLATION` errors
- fail-closed missing project scope with `AUTHZ_DENIED`
- full-registry validation before partition decisions
- platform-owned provider default when `metadata.owner_project_id` is absent
- project-owned provider mutation only when owner metadata matches the principal project
- provider ownership transfer rejection
- global capability, routing policy, and snapshot config rejection
- project-isolated idempotency fingerprint coverage in tests

Reference:

- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| partition validation helper exists | passed |
| same-project project/API-key/credential metadata cases pass | passed |
| caller-owned provider metadata changes pass | passed |
| cross-project project/API-key/credential changes fail | passed |
| platform credential changes fail | passed |
| global routing policy changes fail | passed |
| active snapshot config changes fail | passed |
| capability changes fail | passed |
| platform-owned provider changes fail | passed |
| provider ownership transfer fails | passed |
| new provider without ownership fails | passed |
| invalid proposed registry fails before partition mutation | passed |
| missing project scope fails closed | passed |
| project-scoped idempotency fingerprint evidence is covered | passed |
| no HTTP endpoint, public CRUD, production gateway deployment, automatic propagation, or Data Plane mutable reads were added | passed |

## Validation

Passed:

```text
go test ./internal/registry
go test ./...
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
git diff --check
```

Go test directory:

```text
services/control-plane
```

## Closeout Judgment

This contract harness slice is complete.

The local helper is sufficient for v0 because it proves the hard hosted mutation question before adding service surface:

- project-scoped actors can change only their own project partition
- global/platform objects remain protected
- provider ownership remains explicit and conservative
- partition violations are machine-readable
- idempotency evidence includes project scope
- snapshot export, distribution publish, and Data Plane reload remain separate

The implementation intentionally does not persist a project-partition mutation, expose an HTTP route, or write audit rows. Those are the next design concerns, not gaps in this contract harness slice.

## Remaining Risks

### No Endpoint Uses The Validator Yet

The helper is not wired into an HTTP handler. The next design must define request/response shape, required headers, principal requirements, error mapping, and how the helper composes with `ReplacePersistentRegistry`.

### Audit Persistence Is Not Implemented

The decision object has the evidence shape, but no `registry.project_partition_replace` audit row is written yet.

### Provider Ownership Is Metadata-Based

The harness uses `provider.metadata.owner_project_id` as a v0-compatible proof. A production schema should eventually use first-class owner fields.

### Project Row Policy Is Still Narrow

The helper allows changes to the caller project row, but a service design still needs to define which fields can change in hosted mode.

### Durable Permission Store Is Still Future Work

The gateway permission source remains static dogfood policy. Real hosted authorization still needs durable policy after mutation scope is safe.

### No Automatic Propagation Was Added

Partitioned mutation must still be followed by explicit snapshot export, distribution publish, and Data Plane reload.

## Still Not Allowed

Do not start:

- public registry CRUD APIs
- public project/user/role CRUD
- OAuth/OIDC provider integration
- invitation/login/session lifecycle
- provider onboarding workflow
- marketplace/provider submission
- credential vault writes
- plaintext credential storage
- billing or settlement state
- workflow runtime
- production gateway deployment
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Design v0
```

Why:

- the partition rules are now proven locally
- hosted project mutation needs a private endpoint contract before implementation
- the design should decide how the validator composes with auth, idempotency, audit, and existing replacement mechanics
- this keeps public CRUD and automatic propagation out of scope while moving from helper proof toward a real hosted admin path

Expected design scope:

- endpoint method/path and wrapper shape
- required hosted/trusted principal behavior
- required permission name
- request size and validation ordering
- partition validator invocation point
- registry replacement transaction composition
- idempotency operation and replay semantics
- audit mapping for success/failure partition decisions
- error mapping for `REGISTRY_PARTITION_VIOLATION`
- tests and dogfood requirements for a later implementation slice

Out of scope:

- endpoint implementation
- public CRUD
- OAuth/OIDC
- provider onboarding
- marketplace
- vault
- billing
- workflow runtime
- automatic publish/reload
- production gateway deployment
- Data Plane mutable Control Plane table reads
