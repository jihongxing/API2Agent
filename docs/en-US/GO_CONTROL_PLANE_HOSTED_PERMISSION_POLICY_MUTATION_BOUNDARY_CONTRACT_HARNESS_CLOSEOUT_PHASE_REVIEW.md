# Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness Closeout + Phase Review v0

Date: 2026-06-02

Status: complete

## Decision

The Hosted Permission Policy Mutation Boundary Contract Harness implementation slice can close.

The repository now proves the local/private mutation contract for hosted permission policy rows:

```text
private hosted policy mutation request
  -> draft policy graph
  -> validation and review state
  -> idempotency and conflict checks
  -> promotion to a new active policy version
  -> gateway-compatible permission decision evidence
  -> rollback as a new active version
  -> secret-safe mutation audit evidence
```

Recommended next task:

```text
Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation Design v0
```

That task should design the durable/private implementation boundary for policy mutation rows without adding public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, public policy write APIs, customer-facing decision history, legal-hold customer APIs, customer export/delete APIs, or Data Plane reads from mutable Control Plane tables.

## What Is Now Complete

### Design

Completed:

- private mutation ownership for hosted subjects, memberships, roles, role bindings, permission grants, and policy versions
- draft/review/promotion/rollback lifecycle
- idempotency, audit, conflict, authorization, and gateway read-model compatibility semantics
- local contract harness requirements
- explicit non-goals and deferred public surfaces

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_POLICY_MUTATION_BOUNDARY_DESIGN.md`

### Contract Harness

Completed:

- local/private `HostedPermissionPolicyMutationHarness`
- draft creation and validation helpers
- review request and promotion helpers
- rollback helper that creates a new active version instead of rewriting history
- deterministic policy fingerprints over the effective permission graph
- gateway-compatible permission decisions before promotion, after promotion, and after rollback
- idempotency replay and idempotency conflict behavior
- stale-base, duplicate-grant, and platform-scope violation checks
- secret-safe mutation audit evidence
- in-process dogfood report helper

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_POLICY_MUTATION_BOUNDARY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| draft mutation does not affect gateway decisions before promotion | passed |
| validation detects duplicate active grants | passed |
| validation rejects platform-scope escape | passed |
| review state is represented before promotion | passed |
| promotion activates a new policy version | passed |
| previous active policy version becomes superseded | passed |
| stale-base promotion fails with `POLICY_VERSION_CONFLICT` | passed |
| deterministic fingerprint changes with effective permission graph | passed |
| gateway-compatible decision observes promoted grant | passed |
| rollback creates a new active rollback version | passed |
| rollback removes promoted grant access without rewriting historical evidence | passed |
| idempotent replay returns replay evidence without a second mutation outcome | passed |
| idempotency key conflict is rejected without mutating active policy rows | passed |
| persisted permission decisions remain outside mutation scope | passed |
| audit metadata excludes raw idempotency keys, tokens, gateway secrets, OAuth tokens, plaintext API keys, and vault material | passed |
| no public CRUD, OAuth/OIDC, invitation/session, production gateway, marketplace, vault, billing, workflow, automatic propagation, public policy write API, or Data Plane mutable-read scope was added | passed |

## Dogfood Evidence

In-process dogfood helper:

```text
RunHostedPermissionPolicyMutationBoundaryDogfood()
```

Observed in tests:

- `status=passed`
- `draft_validation_status=passed`
- `promotion_status=passed`
- `rollback_status=passed`
- `idempotency_replay_count=1`
- `idempotency_conflict_status=IDEMPOTENCY_KEY_CONFLICT`
- `scope_violation_status=POLICY_SCOPE_VIOLATION`
- `stale_base_conflict_status=POLICY_VERSION_CONFLICT`
- `gateway_decision_before_promotion=denied`
- `gateway_decision_after_promotion=allowed`
- `gateway_decision_after_rollback=denied`
- no raw idempotency key, raw token, or gateway secret leakage

## Validation

Previously passed in the implementation slice:

```text
go test ./internal/registry -run "TestHostedPermissionPolicyMutation"
go test ./internal/registry
go test ./...
```

Go test directory:

```text
services/control-plane
```

Closeout validation:

```text
git diff --check
```

## Phase Completion

This local/private contract harness closeout lane is 100% complete for v0.

The broader Hosted Control Plane phase completion estimate is now 74%.

The estimate moves modestly because policy mutation semantics are accepted as a local contract proof, but durable private persistence, transaction boundaries, service wiring, live Postgres dogfood, and production gateway rollout remain future work.

## Closeout Judgment

This implementation slice is complete.

The local harness proves the intended policy mutation boundary and the safety properties that the durable implementation must preserve: drafts are isolated, promotion is explicit, rollback is append-style, idempotency is deterministic, conflicts are fail-closed, gateway reads only observe promoted policy, and audit evidence remains secret-safe.

The harness is not a public policy management API and not a production authorization system. It is sufficient for v0 because it closes the mutation semantics question before durable/private implementation design begins.

## Remaining Risks

### No Durable Mutation Store Yet

Drafts, policy mutation audit, idempotency records, and policy version promotion are still local harness state. The next task should design durable private storage and transaction ownership.

### No Private Service Endpoint Yet

There is no hosted service endpoint for policy mutation. Endpoint shape, trusted-gateway authorization, transaction behavior, and response evidence remain design work.

### No Live Postgres Dogfood Yet

The proof is in-process Go. Durable Postgres rows, migrations, constraints, and live dogfood remain future slices.

### Propagation Remains Manual/Deferred

Promotion proves read-model compatibility, but it does not implement automatic snapshot publish, gateway reload, cache invalidation, or production propagation.

### Public Product Surfaces Are Still Deferred

Public role CRUD, user/project management, OAuth/OIDC, invitations, sessions, customer-facing history, export/delete, and legal-hold customer APIs remain out of scope.

### Production Gateway Integration Remains Future Work

The local gateway-compatible decision proof must still be carried into service wiring, observability, timeout behavior, rollout controls, and production deployment.

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
- automatic snapshot publish, reload, cache invalidation, or propagation
- public policy write APIs
- customer-facing decision history
- legal-hold customer API
- customer export/delete API
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation Design v0
```

Why:

- the local/private mutation contract proof is accepted
- the next risk is durable transaction ownership, not public API shape
- durable design can preserve draft/review/promotion/rollback, idempotency, conflict, audit, and gateway read-model compatibility semantics
- the work can stay private/internal and avoid public CRUD, OAuth/OIDC, production gateway rollout, marketplace, vault, billing, workflow, and automatic propagation

Expected scope:

- design durable tables or row ownership for policy drafts, policy versions, mutation audit, and idempotency records
- define private transaction boundaries for validation, promotion, and rollback
- map conflict and idempotency semantics to durable storage
- define secret-safe response and audit evidence
- document live Postgres dogfood criteria for the future implementation slice

Out of scope:

- public CRUD
- OAuth/OIDC
- invitation/session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- vault writes
- billing
- workflow runtime
- automatic propagation
- public policy write APIs
- customer-facing decision history/export/delete/legal-hold APIs
- Data Plane mutable Control Plane table reads
