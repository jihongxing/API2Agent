# Hosted Control Plane Phase Log

Status: active

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
