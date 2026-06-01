# Go Control Plane Hosted Permission Policy Mutation Boundary Design v0

Date: 2026-06-02

Status: complete

## Decision

Design the hosted permission policy mutation boundary before turning seeded hosted permission rows into mutable policy state.

The next implementation should remain local/private and prove mutation semantics for hosted subjects, memberships, roles, role bindings, permission grants, and policy versions. It should not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, Data Plane reads from mutable Control Plane tables, customer-facing decision history, or a public policy write API.

Recommended next task:

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness v0
```

That task should implement local contract helpers and tests for draft policy mutation, review, promotion, rollback, idempotency, audit, conflict handling, and gateway read-model compatibility.

## Why This Design Now

The hosted permission lane has proven:

- durable permission-store schema
- internal read model over hosted permission tables
- live Postgres permission lookup from seeded rows
- gateway runtime wiring to the read model
- request-time permission decision persistence
- duplicate/conflict integrity for decision evidence
- production-shaped decision persistence behavior
- retention/history metadata and redacted local history queries

The remaining hosted-readiness gap is that policy data is still seeded. Roles, grants, memberships, and policy versions need a safe mutation lifecycle before future customer-facing identity, history, export, or administration surfaces can be considered.

## Goals

- define the mutation ownership boundary for hosted permission policy rows
- define staged/draft policy changes before activation
- define review and promotion semantics for active policy versions
- define rollback semantics without rewriting decision evidence
- define idempotency, conflict, and concurrency behavior
- define audit evidence for mutation attempts and promotions
- define gateway/read-model compatibility requirements
- define implementation and dogfood evidence for a local/private contract harness

## Non-Goals

Do not start:

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation, login, or session lifecycle
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- public policy write APIs
- Data Plane reads from mutable Control Plane tables
- real production gateway deployment
- customer-facing decision history endpoint
- legal-hold customer API
- customer export or deletion API

## Boundary

Hosted permission mutation is a private Control Plane operation behind trusted gateway claims and Control Plane second-gate checks:

```text
trusted hosted admin request
  -> private policy mutation service
  -> staged mutation validation
  -> policy draft / policy version rows
  -> audited review and promotion
  -> active policy version
  -> gateway read model consumes coherent active policy
```

The gateway continues to own request-time permission lookup. The Data Plane continues to consume immutable/versioned execution snapshots and must not read mutable hosted permission tables.

For v0, mutation should be implemented as local contract helpers or private internal endpoints only. Public product surfaces remain deferred.

## Mutable Entities

The mutation boundary covers these hosted permission-store entities:

| Entity | Mutation stance |
| --- | --- |
| `hosted_subjects` | May be created or status-updated only from trusted local/test principals in v0. Public identity lifecycle is deferred. |
| `hosted_project_memberships` | May be added, suspended, or revoked within a project/organization scope. |
| `hosted_roles` | May be created or disabled for a project/organization policy source. Platform roles remain operator/internal only. |
| `hosted_role_bindings` | May be added or revoked for a subject/project/role tuple. |
| `hosted_permission_grants` | May be added or revoked for a role and scope type. |
| `hosted_policy_versions` | Owns draft, active, superseded, revoked, promoted, and rollback policy state. |

Hosted permission decision rows are not mutable policy state. They are append-only evidence and must not be rewritten during policy rollback.

## Operation Set

The local contract harness should prove these conceptual operations:

| Operation | Purpose |
| --- | --- |
| `policy_mutation.begin_draft` | Open a scoped draft from the currently active policy version. |
| `policy_mutation.apply_patch` | Apply subject, membership, role, binding, or grant changes to the draft. |
| `policy_mutation.validate_draft` | Check policy invariants without activating the draft. |
| `policy_mutation.request_review` | Freeze the draft for promotion review. |
| `policy_mutation.promote` | Atomically activate the reviewed policy version. |
| `policy_mutation.rollback` | Promote a rollback version derived from a previous active policy version. |
| `policy_mutation.cancel_draft` | Mark an unused draft as abandoned. |

These names are contract labels, not public endpoint paths.

## Draft And Promotion Lifecycle

Policy versions should move through a narrow state machine:

```text
draft -> review_requested -> active
active -> superseded
draft -> abandoned
active -> rollback_candidate -> active
```

Rules:

- only one active policy version may exist per policy source
- draft changes must not affect gateway read decisions
- promotion must be atomic with audit evidence
- promotion must compute a deterministic `policy_fingerprint`
- superseding an active policy must preserve the previous version for rollback evidence
- rollback creates a new active version derived from prior state, rather than mutating historical rows in place
- mixed-version reads must fail closed in the gateway/read model

## Policy Fingerprint

The active policy fingerprint must be deterministic over the effective permission graph:

- active subjects relevant to the policy source
- active memberships
- active roles
- active role bindings
- active permission grants
- active policy source and policy version

It must exclude:

- raw public tokens
- idempotency keys
- request ids
- audit ids
- draft-only notes
- timestamps that do not change effective authorization

The fingerprint format remains:

```text
sha256:<hex>
```

## Idempotency

Policy mutation idempotency should follow the existing admin mutation pattern:

```text
project_id + actor_id + operation + idempotency_key_hash
```

The request fingerprint is a canonical mutation intent, not the raw HTTP body.

Minimum request fingerprint fields:

```json
{
  "version": "hosted-permission-policy-mutation-v0",
  "operation": "policy_mutation.promote",
  "policy_source": "hosted_permission_store",
  "project_id": "project_alpha",
  "organization_id": "org_alpha",
  "base_policy_version": "permission-policy-v7",
  "draft_policy_version": "permission-policy-v8-draft",
  "mutation_patch_fingerprint": "sha256:..."
}
```

Rules:

- same scoped key plus same request fingerprint returns the committed outcome
- same scoped key plus different request fingerprint returns `IDEMPOTENCY_KEY_CONFLICT`
- raw `Idempotency-Key` must not be stored
- idempotency records must link to audit evidence and promoted policy version when applicable
- failed validation before canonical fingerprint creation does not need a durable idempotency outcome

## Conflict Semantics

The mutation service must reject:

- promotion from a stale base policy version
- two active policies for one policy source
- duplicate active role binding for the same subject/project/role
- duplicate active grant for the same role/permission/scope type
- membership, binding, or grant changes outside the trusted project scope
- project-scoped mutation that attempts platform scope
- disabled role or revoked membership activation
- policy fingerprint mismatch during promotion

Recommended stable conflict types:

| Condition | Error type |
| --- | --- |
| stale base policy | `POLICY_VERSION_CONFLICT` |
| duplicate active role binding | `POLICY_BINDING_CONFLICT` |
| duplicate active permission grant | `POLICY_GRANT_CONFLICT` |
| scope escape | `POLICY_SCOPE_VIOLATION` |
| invalid status transition | `POLICY_STATE_CONFLICT` |
| idempotency mismatch | `IDEMPOTENCY_KEY_CONFLICT` |

## Authorization

V0 authorization remains private and trusted-gateway based.

Required permissions should be explicit:

| Operation family | Required permission |
| --- | --- |
| validate draft | `control_plane.permission_policy.validate` |
| create or patch draft | `control_plane.permission_policy.draft_write` |
| request review | `control_plane.permission_policy.request_review` |
| promote policy | `control_plane.permission_policy.promote` |
| rollback policy | `control_plane.permission_policy.rollback` |
| cancel draft | `control_plane.permission_policy.cancel_draft` |

Project-scoped actors may mutate only their project policy surface. Platform/operator roles may manage platform policy sources only in private/internal contexts.

The Control Plane second gate must check trusted gateway permissions and project scope before mutation work starts.

## Audit Evidence

Every accepted mutation attempt that reaches canonical mutation intent should create secret-safe audit evidence.

Audit metadata should include:

- actor id
- subject id when available
- project id
- organization id
- operation
- policy source
- base policy version
- draft policy version
- promoted policy version when applicable
- previous active policy version
- resulting policy fingerprint
- mutation patch fingerprint
- idempotency key hash and prefix
- request id
- outcome

Audit metadata must not include:

- raw public bearer tokens
- raw gateway secrets
- raw session tokens
- OAuth access or refresh tokens
- plaintext API keys
- raw idempotency key
- full request body when it may contain user-supplied notes or external identifiers

## Gateway Read-Model Compatibility

After promotion, the existing read model must be able to resolve a coherent active policy view:

- one active `hosted_policy_versions` row for the policy source
- active membership and binding rows visible for the project
- active grants mapped to endpoint permissions
- deterministic policy version and fingerprint in permission decisions
- revoked membership or grants deny future decisions
- stale or mixed-version reads fail closed

Promotion must not force automatic snapshot publish/reload. It affects hosted gateway authorization only.

## Rollback

Rollback is a policy mutation, not a table rewind.

Rules:

- rollback creates a new active policy version whose effective graph matches a previous active version
- the previous active version becomes superseded
- rollback must create audit evidence linking source and target versions
- persisted permission decisions remain immutable and continue to reference the policy version/fingerprint used at decision time
- rollback must be idempotent and conflict-aware

## Local Contract Harness Requirements

The next implementation should prove:

- draft creation from an active seeded policy
- patching membership, role binding, and grant changes
- validation rejects scope escape and duplicate active grants/bindings
- review/promotion activates exactly one policy version
- gateway read model observes promoted permissions
- revoked or removed grants deny after promotion
- stale-base promotion conflicts deterministically
- rollback restores the prior effective permission graph as a new active version
- idempotent replay returns the original mutation outcome
- idempotency conflict does not mutate policy rows
- audit rows are written with secret-safe metadata
- Data Plane does not read mutable permission tables

## Dogfood Evidence Requirements

The later local/private dogfood artifact should report:

- active policy version before and after promotion
- active policy fingerprint before and after promotion
- draft validation status
- promotion status
- rollback status
- idempotency replay count
- idempotency conflict status
- scope-violation status
- stale-base conflict status
- gateway decision before promotion
- gateway decision after promotion
- gateway decision after rollback
- audit row count delta
- absence of raw tokens, raw idempotency keys, and gateway secrets

Suggested artifact path:

```text
.dogfood/go-control-plane-hosted-permission-policy-mutation-boundary/report.json
```

## Acceptance Criteria

This design is complete when:

- mutation ownership for hosted permission policy rows is documented
- draft/review/promotion/rollback lifecycle is explicit
- idempotency, audit, conflict, and authorization semantics are explicit
- gateway read-model compatibility is defined
- local contract harness and dogfood requirements are defined
- public CRUD, OAuth/OIDC, production deployment, vault, billing, marketplace, workflow, automatic propagation, policy write APIs, customer-facing decision history, and Data Plane mutable reads remain deferred

## Completion Estimate

Hosted permission policy mutation boundary design lane:

```text
100%
```

Hosted Control Plane phase:

```text
73%
```

This is an estimate. The design reduces policy lifecycle ambiguity, but hosted policy mutation still needs a contract harness, local implementation proof, live dogfood, closeout, public identity lifecycle, customer-facing history/export/delete, production gateway deployment, production operations, vault/billing/marketplace/workflow surfaces, and Data Plane mutable-read decisions to remain explicitly bounded.

## Next Task

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness v0
```

The next task should implement the local/private mutation contract harness and tests only. It should not expose public policy write APIs or start public role management.
