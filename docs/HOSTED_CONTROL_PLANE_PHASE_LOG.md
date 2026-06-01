# Hosted Control Plane Phase Log

Status: complete for local v0 (100%)

This is the compact running log for Hosted Control Plane work.

New entries should stay short. Prefer this file over new per-slice implementation reports, dogfood reports, and closeout documents unless the task introduces a durable public API, storage, security, protocol, deployment, or customer-data boundary.

## Entry Format

```text
Date:
Task:
Commit:
Changed:
Validation:
Decision:
Next:
Completion:
```

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Idempotency Replay Evidence Review + Hosted Control Plane Phase Closeout v0

Commit: `a49d383 Close hosted control plane local v0`

Changed:

- strengthened durable hosted policy mutation replay evidence for promotion and rollback
- proved promotion replay does not append policy versions, re-run hosted graph writes, or create extra admin audit events
- proved rollback replay keeps policy-version-only rollback semantics stable without graph rewrites or extra audit/version rows
- verified replay metadata updates `replay_count` and `last_replay_request_id` while preserving idempotency/audit linkage
- verified raw idempotency keys do not appear in idempotency records, audit events, policy versions, or hosted graph evidence
- preserved private trusted-gateway-only policy mutation scope and did not add public policy CRUD, OAuth/OIDC, invitation/session lifecycle, deployment, marketplace, vault, billing, workflow, automatic propagation, customer export/delete/legal-hold APIs, or Data Plane mutable Control Plane reads

Validation:

- `go test ./internal/registry -run "TestPostgresHostedPermissionPolicyMutation(PromoteReplaysAndRejectsConflicts|PromoteReplayDoesNotReapplyGraphOrAudit|RollbackAppendsActiveVersion)$" -v`
- `go test ./internal/registry -run "TestPostgresHostedPermissionPolicyMutation" -v`
- `go test ./internal/httpapi -run "TestTrustedGatewayHostedPermissionPolicyMutation|TestHostedPermissionPolicyMutation" -v`
- `go test ./cmd/api2agent-controlplane -v`
- `go test ./...`
- `git diff --check`

Decision:

- Hosted Control Plane local v0 is accepted as 100% complete
- hosted admin identity, trusted gateway authentication, permission source, tenant partition mutation, hosted permission store, decision persistence/retention, and private hosted policy mutation lanes now have implementation, regression, and compact phase-log evidence
- remaining work belongs to the next phase selection rather than another Hosted Control Plane readiness slice

Next:

- select the post-Hosted Control Plane phase under the compact documentation policy

Completion:

- idempotency replay evidence review lane: 100%
- Hosted Control Plane phase estimate: 100%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness Closeout + Phase Review v0

Commit: `17500ad Close hosted permission policy mutation harness`

Changed:

- accepted the local/private hosted permission policy mutation contract proof for v0
- recorded draft, validation, review, promotion, rollback, idempotency replay/conflict, stale-base conflict, scope violation, duplicate grant conflict, gateway-compatible decision evidence, and secret-safe audit metadata as sufficient for the contract harness lane
- preserved public CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, customer-facing decision history, legal-hold customer APIs, customer export/delete APIs, marketplace, vault, billing, workflow, automatic propagation, policy write APIs, and Data Plane mutable reads as out of scope

Validation:

- `git diff --check`
- `go test ./...` from `services/control-plane`
- `git diff --cached --check`

Decision:

- local/private contract harness lane is complete for v0
- Hosted Control Plane completion estimate moved to 74%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation Design v0`

Completion:

- contract harness closeout lane: 100%
- Hosted Control Plane phase estimate: 74%

## 2026-06-02

Task: Documentation Consolidation + Future Documentation Policy v0

Commit: this documentation governance commit

Changed:

- introduced a repository-level documentation policy to stop per-slice document growth
- introduced this single Hosted Control Plane phase log as the default place for compact progress, validation, decisions, next task, and completion estimates
- slimmed the README documentation navigation to core entry points instead of a full historical report index

Validation:

- `git diff --check`
- `git diff --cached --check`

Decision:

- future normal implementation work should update code, tests, `CHANGELOG.md`, and this phase log
- standalone documents are reserved for durable API, storage, security, protocol, deployment, customer-data, or major product-direction boundaries

Next:

- `Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation Design v0`, under the new documentation policy

Completion:

- documentation governance lane: 100%
- Hosted Control Plane phase estimate remains 74%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation Design v0

Commit: pending until this design slice is committed

Changed:

- designed durable private draft and change row ownership for hosted permission policy mutation
- mapped promotion and rollback to serializable Postgres transactions
- reused `admin_mutation_idempotency_records` and `admin_audit_events` for replay/conflict and secret-safe evidence
- preserved gateway read-model compatibility and Data Plane mutable-read exclusion
- kept public CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, automatic propagation, customer-facing history/export/delete/legal-hold APIs, marketplace, vault, billing, and workflow runtime out of scope

Validation:

- `git diff --check`
- `git diff --cached --check`

Decision:

- durable private implementation design lane is complete for v0
- Hosted Control Plane completion estimate moves to 75%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation v0`

Completion:

- durable private implementation design lane: 100%
- Hosted Control Plane phase estimate: 75%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation v0

Commit: pending until this implementation slice is committed

Changed:

- added private Postgres-backed hosted permission policy draft, draft-change, review, promotion, and rollback mutation helpers
- persisted canonical draft change evidence without changing the active read model before promotion
- reused admin mutation idempotency records for promotion/rollback replay and conflict handling
- reused admin audit events with hashed idempotency metadata and secret-safe patch summaries
- extended persistent test rows and the scripted registry DB to cover hosted policy versions, mutation drafts, and draft changes

Validation:

- `go test ./internal/registry -run "TestPostgresHostedPermissionPolicyMutation|TestPersistentRegistrySQLSchemaContainsHostedPolicyMutationDraftBoundary"`
- `go test ./internal/registry`

Decision:

- durable private implementation lane is complete for v0
- no per-slice implementation report or closeout document was created under the new documentation policy
- Hosted Control Plane completion estimate moves to 77%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Durable Private Endpoint/Service Wiring v0`

Completion:

- durable private implementation lane: 100%
- Hosted Control Plane phase estimate: 77%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Durable Private Endpoint/Service Wiring v0

Commit: pending until this implementation slice is committed

Changed:

- wired a private hosted permission policy mutation HTTP route for trusted gateway principals
- mapped begin/change/review/promote/rollback operations to operation-specific hosted policy permissions
- forwarded resolved hosted principal project, organization, actor, request, idempotency, draft, policy version, and fingerprint inputs into the durable mutation service
- connected the Postgres runtime adapter to the durable hosted policy mutation helpers
- returned replay headers for idempotent promote/rollback responses and mapped policy conflicts to HTTP 409

Validation:

- `go test ./internal/httpapi -run "TestHostedPermissionPolicyMutation|TestTrustedGatewayHostedPermissionPolicyMutation|TestProjectPartitionReplaceReplayUsesOKStatus"`
- `go test ./internal/registry ./internal/httpapi ./cmd/api2agent-controlplane`

Decision:

- durable private endpoint/service wiring lane is complete for v0
- route remains private/trusted-gateway-only and does not introduce public role CRUD or customer-facing policy APIs
- no per-slice implementation report or closeout document was created under the new documentation policy
- Hosted Control Plane completion estimate moves to 78%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Private Endpoint Dogfood v0`

Completion:

- durable private endpoint/service wiring lane: 100%
- Hosted Control Plane phase estimate: 78%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Private Endpoint Dogfood v0

Commit: pending until this dogfood slice is committed

Changed:

- added an HTTP handler dogfood path that drives trusted gateway begin, draft change, review, promote, promote replay, and rollback
- used a harness-backed private mutator to verify endpoint wiring, operation-specific permissions, request/idempotency headers, policy lifecycle state, gateway-compatible decisions, and secret-safe audit metadata together
- kept evidence in tests plus this phase log instead of creating a standalone dogfood report

Validation:

- `go test ./internal/httpapi -run TestTrustedGatewayHostedPermissionPolicyMutationEndpointDogfood -v`
- `go test ./internal/httpapi -run "TestHostedPermissionPolicyMutation|TestTrustedGatewayHostedPermissionPolicyMutation"`
- `go test ./internal/registry -run "TestHostedPermissionPolicyMutation|TestPostgresHostedPermissionPolicyMutation"`

Decision:

- private hosted permission policy mutation endpoint dogfood lane is complete for v0
- trusted gateway private lifecycle proof covers replay and rollback without exposing public policy CRUD
- Hosted Control Plane completion estimate moves to 79%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Durable Graph Apply Semantics v0`

Completion:

- private endpoint dogfood lane: 100%
- Hosted Control Plane phase estimate: 79%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Durable Graph Apply Semantics v0

Commit: pending until this implementation slice is committed

Changed:

- applied hosted policy mutation draft changes into the durable hosted permission graph during promotion
- covered subject, project membership, role, role binding, and permission grant upserts plus binding/grant revocation status changes
- recorded `draft_change_count` and graph apply metadata on promoted policy versions and graph rows
- extended persistent registry fixtures and scripted Postgres tests for graph row mutation evidence

Validation:

- `go test ./internal/registry -run "TestPostgresHostedPermissionPolicyMutationPromoteAppliesGraph|TestPostgresHostedPermissionPolicyMutation"`
- `go test ./internal/registry`
- `go test ./...`

Decision:

- durable graph apply semantics lane is complete for v0
- promotion now mutates the hosted permission read graph instead of only appending policy versions
- rollback remains append-style; historical graph rewind is not claimed because graph rows are not versioned
- no per-slice implementation report, dogfood report, or closeout document was created under the new documentation policy
- Hosted Control Plane completion estimate moves to 80%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Rollback Graph Semantics Readiness Review v0`

Completion:

- durable graph apply semantics lane: 100%
- Hosted Control Plane phase estimate: 80%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Rollback Graph Semantics Readiness Review v0

Commit: pending until this readiness slice is committed

Changed:

- reviewed the durable Postgres rollback boundary after promotion-time graph apply semantics
- kept rollback as policy-version-only for v0 because hosted graph rows are not versioned
- added rollback policy version metadata for `graph_apply_mode`, `graph_rollback_status`, and the non-versioned graph reason
- added regression coverage that rollback appends a new active policy version without silently rewriting hosted graph rows

Validation:

- `go test ./internal/registry -run "TestPostgresHostedPermissionPolicyMutationRollback|TestPostgresHostedPermissionPolicyMutation"`
- `go test ./internal/registry`

Decision:

- rollback graph semantics readiness lane is complete for v0
- historical graph rewind remains out of scope until graph row versioning or inverse draft replay is designed
- no per-slice implementation report, dogfood report, or closeout document was created under the new documentation policy
- Hosted Control Plane completion estimate moves to 81%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Read Model Consistency Dogfood v0`

Completion:

- rollback graph semantics readiness lane: 100%
- Hosted Control Plane phase estimate: 81%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Read Model Consistency Dogfood v0

Commit: pending until this dogfood slice is committed

Changed:

- added registry-level dogfood that promotes hosted policy draft changes into durable hosted graph rows and resolves them through the existing read model
- extended the persistent scripted Postgres fixture so the same mutation-written graph rows answer hosted read model queries
- proved promoted subject, membership, role, binding, and grant rows produce an allowed hosted permission decision with policy-v2 evidence
- proved rollback changes read-model policy evidence to the rollback version while preserving the v0 policy-version-only graph boundary

Validation:

- `go test ./internal/registry -run "TestPostgresHostedPermissionPolicyMutationReadModelConsistencyDogfood" -v`
- `go test ./internal/registry -run "TestPostgresHostedPermissionPolicyMutation|TestHostedPermissionReadModel"`
- `go test ./internal/registry`
- `go test ./...`

Decision:

- read model consistency dogfood lane is complete for v0
- promotion-written graph rows are compatible with the hosted permission read model
- rollback read-model evidence is explicit but does not claim historical graph rewind
- no standalone dogfood report or closeout document was created under the new documentation policy
- Hosted Control Plane completion estimate moves to 82%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Private Endpoint Read Model Consistency Wiring v0`

Completion:

- read model consistency dogfood lane: 100%
- Hosted Control Plane phase estimate: 82%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Private Endpoint Read Model Consistency Wiring v0

Commit: pending until this wiring slice is committed

Changed:

- added HTTP private endpoint dogfood for trusted-gateway hosted policy mutation read-model consistency
- drove begin, subject, membership, role, role binding, grant, review, promote, and rollback requests through `/v1/private/hosted/permission-policy/mutation`
- verified promoted endpoint graph changes become read-model-visible for `control_plane.permission_policy.promote`
- verified rollback changes policy evidence while preserving the v0 policy-version-only graph boundary
- verified trusted principal project, organization, actor, and rollback idempotency key are forwarded into mutation options

Validation:

- `go test ./internal/httpapi -run "TestTrustedGatewayHostedPermissionPolicyMutationReadModelConsistencyWiring" -v`
- `go test ./internal/httpapi -run "TestTrustedGatewayHostedPermissionPolicyMutation|TestHostedPermissionPolicyMutation"`
- `go test ./internal/registry -run "TestPostgresHostedPermissionPolicyMutation|TestHostedPermissionReadModel"`
- `go test ./...`

Decision:

- private endpoint read-model consistency wiring lane is complete for v0
- trusted-gateway private mutation wiring now has endpoint-level consistency evidence without exposing public policy CRUD
- no standalone implementation, dogfood, or closeout document was created under the new documentation policy
- Hosted Control Plane completion estimate moves to 83%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Durable Endpoint Adapter Readiness Review v0`

Completion:

- private endpoint read-model consistency wiring lane: 100%
- Hosted Control Plane phase estimate: 83%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Durable Endpoint Adapter Readiness Review v0

Commit: pending until this readiness slice is committed

Changed:

- reviewed the production `api2agent-controlplane serve` runtime adapter boundary for hosted permission policy mutation
- added a compile-time guard that `postgresHostedPermissionPolicyMutator` satisfies the HTTP hosted policy mutator interface
- made the Postgres runtime opener testable without changing production behavior
- added cmd-level readiness coverage that file runtime does not expose hosted policy mutation and Postgres runtime failures stay fail-closed
- verified the durable adapter delegates into registry helpers by asserting nil-DB promotion fails through the persistent store error path

Validation:

- `go test ./cmd/api2agent-controlplane -run "TestOpenRegistryRuntimeHostedPolicyMutatorBoundary" -v`
- `go test ./internal/httpapi -run "TestTrustedGatewayHostedPermissionPolicyMutation|TestHostedPermissionPolicyMutation"`
- `go test ./...`

Decision:

- durable endpoint adapter readiness lane is complete for v0
- production serve wiring has a guarded Postgres-only hosted policy mutation adapter
- file registry mode remains non-mutating for hosted policy policy changes
- no standalone readiness report or closeout document was created under the new documentation policy
- Hosted Control Plane completion estimate moves to 84%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Serve Boundary Dogfood v0`

Completion:

- durable endpoint adapter readiness lane: 100%
- Hosted Control Plane phase estimate: 84%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Serve Boundary Dogfood v0

Commit: pending until this dogfood slice is committed

Changed:

- added serve-boundary dogfood for hosted trusted-gateway private policy mutation wiring
- made `serve` listener injection testable without changing production `http.ListenAndServe` behavior
- verified file registry serve mode rejects hosted policy mutation with `REGISTRY_MUTATION_UNAVAILABLE`
- verified Postgres registry serve mode routes private promote requests into the durable adapter and fails closed on persistent store unavailability
- preserved private/trusted-gateway-only mutation scope and did not expose public policy CRUD

Validation:

- `go test ./cmd/api2agent-controlplane -run "TestServeHostedPermissionPolicyMutationBoundaryDogfood" -v`
- `go test ./cmd/api2agent-controlplane`
- `go test ./internal/httpapi -run "TestTrustedGatewayHostedPermissionPolicyMutation|TestHostedPermissionPolicyMutation"`
- `go test ./...`

Decision:

- serve boundary dogfood lane is complete for v0
- hosted trusted-gateway serve wiring reaches the private policy mutation route and keeps file-mode mutation unavailable
- no standalone dogfood report or closeout document was created under the new documentation policy
- Hosted Control Plane completion estimate moves to 85%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Operational Error Semantics Review v0`

Completion:

- serve boundary dogfood lane: 100%
- Hosted Control Plane phase estimate: 85%

## 2026-06-02

Task: Go Control Plane Hosted Permission Policy Mutation Operational Error Semantics Review v0

Commit: pending until this review slice is committed

Changed:

- reviewed hosted private policy mutation operational error mapping for caller/platform scope, retryability, and HTTP status
- replaced the single policy-version conflict endpoint check with a hosted policy mutation error semantics matrix
- covered policy scope/state/version conflicts, idempotency key conflicts, in-progress idempotency requests, persistent store failures, idempotency store failures, audit failures, and replay decode failures
- kept the existing private trusted-gateway-only mutation route and did not introduce public policy CRUD

Validation:

- `go test ./internal/httpapi -run "TestTrustedGatewayHostedPermissionPolicyMutationMapsOperationalErrors" -v`
- `go test ./internal/httpapi -run "TestTrustedGatewayHostedPermissionPolicyMutation|TestHostedPermissionPolicyMutation|TestImportReplaceRegistryMapsMutationErrors"`
- `go test ./internal/registry -run "TestPostgresHostedPermissionPolicyMutation"`
- `go test ./...`

Decision:

- operational error semantics review lane is complete for v0
- hosted policy mutation endpoint error responses now have dedicated coverage for status, scope, and retryability
- no standalone review report or closeout document was created under the new documentation policy
- Hosted Control Plane completion estimate moves to 86%

Next:

- `Go Control Plane Hosted Permission Policy Mutation Idempotency Replay Evidence Review v0`

Completion:

- operational error semantics review lane: 100%
- Hosted Control Plane phase estimate: 86%
