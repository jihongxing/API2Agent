# Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation Design v0

Date: 2026-06-02

Status: complete

## Decision

Design the durable/private implementation boundary for hosted permission policy mutation before adding Postgres-backed code.

This task is allowed as a standalone design under `docs/DOCUMENTATION_POLICY.md` because it changes durable storage, transaction, idempotency, audit, and private service boundaries.

Recommended next task:

```text
Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation v0
```

That task should implement the private durable mutation path only. It must not add public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, public policy write APIs, customer-facing decision history/export/delete/legal-hold APIs, or Data Plane reads from mutable Control Plane tables.

## Current Proofs

Already complete:

- hosted permission-store schema with subjects, memberships, roles, bindings, grants, policy versions, and decision rows
- internal read model over active hosted permission rows
- gateway runtime wiring against the read model
- decision persistence and retention boundaries
- local/private mutation contract harness proving draft, validation, review, promotion, rollback, idempotency, conflict, audit, and gateway-compatible decisions
- documentation policy that stops per-slice report growth

The remaining gap is durable private mutation state and transactions.

## Durable Boundary

Durable policy mutation remains a private Control Plane operation:

```text
trusted gateway principal
  -> Control Plane second gate
  -> private mutation service
  -> serializable Postgres transaction
  -> idempotency reservation
  -> draft rows / policy graph patch rows
  -> validation
  -> promotion or rollback
  -> admin audit event
  -> idempotency completion
  -> gateway read model observes active version
```

The gateway continues to read the hosted permission read model. The Data Plane continues to consume immutable/versioned execution snapshots and must not read mutable Control Plane tables.

## Schema Strategy

Reuse existing tables:

- `hosted_subjects`
- `hosted_project_memberships`
- `hosted_roles`
- `hosted_role_bindings`
- `hosted_permission_grants`
- `hosted_policy_versions`
- `admin_audit_events`
- `admin_mutation_idempotency_records`

Add durable private mutation tables:

```text
hosted_policy_mutation_drafts
hosted_policy_mutation_draft_changes
```

### hosted_policy_mutation_drafts

Purpose: own draft/review/promotion lifecycle before a policy version becomes active.

Required fields:

- `id`
- `project_id`
- `organization_id`
- `policy_source`
- `base_policy_version`
- `draft_policy_version`
- `draft_policy_fingerprint`
- `status`: `draft`, `review_requested`, `promoted`, `abandoned`, `failed`
- `actor_id`
- `review_requested_by`
- `review_requested_at`
- `promoted_policy_version`
- `promoted_at`
- `admin_audit_event_id`
- `metadata`
- `created_at`
- `updated_at`

Required constraints:

- non-empty project, organization, policy source, base version, and draft version
- unique `(policy_source, draft_policy_version)`
- at most one open draft per `(project_id, policy_source, actor_id)` for `draft` and `review_requested`
- fingerprint must use `sha256:` when present

### hosted_policy_mutation_draft_changes

Purpose: store canonical patch evidence without mutating active rows before promotion.

Required fields:

- `id`
- `draft_id`
- `change_seq`
- `object_type`: `subject`, `membership`, `role`, `role_binding`, `permission_grant`
- `operation`: `upsert`, `revoke`, `disable`
- `object_id`
- `project_id`
- `organization_id`
- `patch_fingerprint`
- `patch_summary`
- `created_at`

Required constraints:

- unique `(draft_id, change_seq)`
- `patch_fingerprint` uses `sha256:`
- `patch_summary` is secret-safe JSONB
- no raw public tokens, gateway secrets, OAuth tokens, plaintext API keys, raw idempotency keys, or vault material

## Policy Version Rows

`hosted_policy_versions` remains the durable active-version authority.

Implementation may extend it in a later migration with:

- `project_id`
- `organization_id`
- `base_policy_version`
- `superseded_by_policy_version`
- `rollback_of_policy_version`
- `activated_by_audit_event_id`

If the first implementation avoids schema expansion, equivalent evidence must be present in `metadata` and audit rows. The active invariant remains:

```text
one active hosted_policy_versions row per policy_source
```

Promotion must not rewrite historical decision rows. Existing `hosted_permission_decisions` keep their original policy version and fingerprint.

## Transaction Boundaries

Use serializable transactions for promotion and rollback.

### Begin Draft

1. Authorize trusted principal and project scope before opening a transaction.
2. Load the active policy version for `policy_source`.
3. Insert `hosted_policy_mutation_drafts` with `status='draft'`.
4. Record an admin audit event with secret-safe metadata.
5. Return draft id, base version, draft version, and policy source.

No active read-model rows change.

### Apply Patch

1. Authorize `control_plane.permission_policy.draft_write`.
2. Lock the draft row with `FOR UPDATE`.
3. Reject non-`draft` status with `POLICY_STATE_CONFLICT`.
4. Validate project and organization scope for every patch.
5. Insert canonical patch rows into `hosted_policy_mutation_draft_changes`.
6. Recompute draft fingerprint from base policy plus patches.
7. Update draft fingerprint and audit evidence.

No active read-model rows change.

### Request Review

1. Authorize `control_plane.permission_policy.request_review`.
2. Lock draft.
3. Validate effective draft graph.
4. Change status to `review_requested`.
5. Record reviewer and audit evidence.

### Promote

1. Authorize `control_plane.permission_policy.promote`.
2. Reserve idempotency using `(project_id, actor_id, operation, idempotency_key_hash)`.
3. Lock draft, active policy version, and all affected hosted permission rows.
4. Reject stale base with `POLICY_VERSION_CONFLICT`.
5. Validate effective graph and deterministic fingerprint.
6. Insert/update hosted subjects, memberships, roles, bindings, and grants as private durable rows.
7. Update previous active policy version to `superseded`.
8. Insert or update draft policy version as `active`.
9. Mark draft `promoted`.
10. Insert admin audit event.
11. Complete idempotency record with cached response.

All steps must commit atomically.

### Rollback

1. Authorize `control_plane.permission_policy.rollback`.
2. Reserve idempotency.
3. Lock active policy version and target historical version.
4. Create a new policy version whose effective graph matches the target version.
5. Supersede the previous active version.
6. Insert audit evidence linking previous, target, and new active versions.
7. Complete idempotency.

Rollback is append-style. It does not rewind tables or mutate historical decision evidence.

## Idempotency

Reuse `admin_mutation_idempotency_records`.

Scope:

```text
project_id + actor_id + operation + idempotency_key_hash
```

Operations:

- `policy_mutation.begin_draft`
- `policy_mutation.apply_patch`
- `policy_mutation.request_review`
- `policy_mutation.promote`
- `policy_mutation.rollback`
- `policy_mutation.cancel_draft`

Canonical request summary must include:

- version: `hosted-permission-policy-mutation-v0`
- operation
- project id
- organization id
- actor id
- policy source
- base policy version
- draft policy version when present
- target policy version when present
- patch fingerprint or mutation fingerprint
- source: `hosted_permission_policy_mutation_private`

Rules:

- same key and same fingerprint returns cached response
- same key and different fingerprint returns `IDEMPOTENCY_KEY_CONFLICT`
- `processing` state returns retryable `IDEMPOTENCY_REQUEST_IN_PROGRESS`
- replay increments `replay_count`
- raw idempotency keys are never stored

## Conflict Semantics

Stable durable errors:

| Condition | Error type |
| --- | --- |
| stale base policy | `POLICY_VERSION_CONFLICT` |
| duplicate active role binding | `POLICY_BINDING_CONFLICT` |
| duplicate active permission grant | `POLICY_GRANT_CONFLICT` |
| scope escape | `POLICY_SCOPE_VIOLATION` |
| invalid draft or version transition | `POLICY_STATE_CONFLICT` |
| fingerprint mismatch | `POLICY_FINGERPRINT_CONFLICT` |
| idempotency mismatch | `IDEMPOTENCY_KEY_CONFLICT` |
| idempotency in progress | `IDEMPOTENCY_REQUEST_IN_PROGRESS` |

Caller errors must not partially mutate policy rows. Platform errors during audit, idempotency completion, or transaction commit must roll back the transaction and return retryable failure evidence where possible.

## Authorization

The private service requires trusted gateway claims plus Control Plane second-gate checks.

Required permissions:

| Operation | Permission |
| --- | --- |
| begin draft | `control_plane.permission_policy.draft_write` |
| apply patch | `control_plane.permission_policy.draft_write` |
| validate draft | `control_plane.permission_policy.validate` |
| request review | `control_plane.permission_policy.request_review` |
| promote | `control_plane.permission_policy.promote` |
| rollback | `control_plane.permission_policy.rollback` |
| cancel draft | `control_plane.permission_policy.cancel_draft` |

Project-scoped actors may mutate only project-scoped rows. Platform scope remains private/operator-only and must reject customer project actors with `POLICY_SCOPE_VIOLATION`.

## Audit Evidence

Use `admin_audit_events`.

Metadata should include:

- actor id
- project id
- organization id
- operation
- policy source
- draft id
- base policy version
- draft policy version
- previous active policy version
- promoted or rollback policy version
- target rollback version when applicable
- policy fingerprint
- patch or mutation fingerprint
- idempotency key hash and prefix
- request id
- outcome

Metadata must not include:

- raw public bearer tokens
- raw gateway secrets
- OAuth access or refresh tokens
- raw session tokens
- plaintext API keys
- raw idempotency keys
- vault material
- unbounded user notes or full raw request bodies

## Private Response Shape

Private responses should be evidence-first and replay-safe:

```json
{
  "operation": "policy_mutation.promote",
  "project_id": "project_alpha",
  "organization_id": "org_alpha",
  "actor_id": "actor_alpha",
  "request_id": "req-123",
  "replayed": false,
  "policy_source": "hosted_permission_store",
  "base_policy_version": "permission-policy-v7",
  "draft_policy_version": "permission-policy-v8-draft",
  "previous_policy_version": "permission-policy-v7",
  "policy_version": "permission-policy-v8",
  "previous_policy_fingerprint": "sha256:...",
  "policy_fingerprint": "sha256:...",
  "idempotency_record_id": 123,
  "admin_audit_event_id": 456
}
```

The response must not include raw tokens, raw idempotency keys, gateway secrets, or full patch bodies.

## Gateway Read-Model Compatibility

After promotion, the existing read model must observe:

- exactly one active policy version for the policy source
- active membership rows for allowed subjects
- active role bindings and grants for promoted permissions
- revoked memberships, bindings, and grants as denials
- policy version/fingerprint in decisions

Gateway reads must fail closed if active policy rows are missing, duplicated, stale, or mixed.

Promotion does not trigger automatic publish/reload and does not affect Data Plane snapshots.

## Implementation Scope

The next implementation should add:

- schema migration or schema extension for draft tables
- private registry package functions for begin draft, patch, review, promote, rollback, and cancel
- transaction tests using the existing sqlmock-style harness
- idempotency replay/conflict tests
- audit secret-safety tests
- read-model compatibility regression after promotion and rollback
- compact phase-log entry and `CHANGELOG.md` update

Out of scope:

- public endpoints for customer policy writes
- OAuth/OIDC or invitation/session lifecycle
- production gateway deployment
- automatic snapshot publish/reload/cache invalidation
- customer-facing history/export/delete/legal-hold APIs
- marketplace/provider onboarding
- vault writes
- billing
- workflow runtime
- Data Plane reads from mutable Control Plane tables

## Live Dogfood Criteria

The future implementation dogfood should prove with Postgres-backed rows:

- draft creation from an active policy
- patch storage without changing active gateway decisions
- review request
- promotion changes gateway-compatible decisions
- idempotent promotion replay returns cached response
- idempotency conflict does not mutate active policy
- stale-base promotion fails
- scope escape fails
- rollback creates a new active version and removes promoted grant access
- admin audit and idempotency rows are secret-safe
- decision rows remain append-only evidence

The dogfood evidence should be stored as machine-readable output, with only a compact phase-log summary.

## Acceptance Criteria

This design is complete when:

- durable draft and patch row ownership is defined
- promotion and rollback transaction order is explicit
- idempotency reuse is mapped to existing records
- audit evidence and secret exclusions are explicit
- private response shape is defined
- gateway read-model compatibility is preserved
- future implementation and dogfood criteria are clear
- deferred public surfaces remain out of scope

## Completion Estimate

Hosted permission policy mutation durable private design lane:

```text
100%
```

Hosted Control Plane phase:

```text
75%
```

The estimate increases because durable private transaction ownership is now designed. It remains below completion because the Postgres-backed implementation, private service wiring, live dogfood, production gateway rollout, public identity lifecycle, and customer-facing policy/history surfaces are still deferred.
