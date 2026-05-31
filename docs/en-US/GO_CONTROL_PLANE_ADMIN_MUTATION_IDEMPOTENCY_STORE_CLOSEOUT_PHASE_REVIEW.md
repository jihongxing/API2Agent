# Go Control Plane Admin Mutation Idempotency Store Closeout + Phase Review v0

Date: 2026-05-31

Status: complete

## Decision

The Admin Mutation Idempotency Store slice can close.

The private admin import/replace endpoint now has durable Postgres-backed idempotency semantics for committed registry mutations:

```text
same scoped key + same request
  -> cached committed response replay

same scoped key + different request
  -> 409 IDEMPOTENCY_KEY_CONFLICT
```

Recommended next task:

```text
Go Control Plane Hosted Admin Identity Boundary Design v0
```

That should be a design task. Do not start implementation before the identity boundary is accepted.

## What Is Now Complete

### Design

Completed:

- persistent idempotency record schema
- key scope: `project_id + actor_id + operation + idempotency_key_hash`
- raw idempotency key hashing
- canonical request fingerprint semantics
- response replay semantics
- conflict behavior for key reuse with a different request
- transaction boundary with `ReplacePersistentRegistry`
- registry revision and admin audit linkage
- retention and cleanup policy
- failure semantics
- implementation test requirements

Reference:

- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_DESIGN.md`

### Implementation

Completed:

- `admin_mutation_idempotency_records` Postgres table
- scoped key hashing and hash-prefix storage
- import/replace request fingerprinting
- same-key same-request replay
- same-key different-request conflict detection
- same-transaction idempotency completion
- linkage to `registry_revisions.id`
- linkage to `admin_audit_events.id`
- replay metadata updates
- HTTP replay headers
- stable idempotency error mapping
- schema, registry-layer, and HTTP regression tests

Reference:

- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

Completed with podman-backed Postgres:

- first HTTP import/replace returned `201` and `noop=false`
- same-key same-request replay returned cached `201`
- replay returned `Idempotency-Replayed: true`
- replay returned `Idempotency-Record-ID: 1`
- same-key different-request reuse returned `409 IDEMPOTENCY_KEY_CONFLICT`
- independent same-registry key returned `200` and `noop=true`
- exported snapshot used `httpbin_public_ip_v1`
- persistent evidence rows were asserted

Observed:

```json
{
  "first_status": 201,
  "replay_status": 201,
  "conflict_status": 409,
  "noop_status": 200,
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 2,
    "idempotency_records": 2,
    "providers": 1
  }
}
```

Reference:

- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_LIVE_POSTGRES_DOGFOOD_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| idempotency record schema is implemented | passed |
| same-key same-request replay returns cached committed response | passed |
| same-key different-request conflict returns `409 IDEMPOTENCY_KEY_CONFLICT` | passed |
| transaction linkage with registry import/replace is implemented | passed |
| audit and revision linkage is implemented | passed |
| raw idempotency key is not stored in persistent idempotency rows | passed |
| live Postgres dogfood validates replay and conflict semantics | passed |
| public CRUD remains out of scope | passed |
| automatic propagation remains out of scope | passed |
| vault, billing, marketplace, workflow, and provider onboarding remain out of scope | passed |

## Closeout Judgment

This slice is complete.

The Control Plane write path now has a durable answer for retry safety, client timeouts after commit, and accidental idempotency key reuse. The implementation also preserves the existing architecture rule:

```text
Control Plane owns mutable registry state.
Data Plane consumes immutable/versioned snapshots.
```

Idempotency replay does not publish snapshots, reload Data Plane instances, or let the Data Plane read mutable Control Plane tables.

## Remaining Risks

### Hosted Admin Identity Is Still Local-Private

The service still authenticates private admin requests with a bearer token.

`X-Actor-ID` remains a local/private actor hint, not a hosted identity boundary.

The idempotency store has a `project_id` scope, but v0 fills it with `control_plane` until hosted project identity exists.

### Project Scope Is Not Yet Real

The current mutation path is registry-wide.

There is no hosted project membership, role, permission, or tenant boundary yet. Before more mutation endpoints exist, the Control Plane needs a clear model for:

- authenticated admin principal
- project or organization scope
- actor attribution
- permission checks
- audit identity fields
- idempotency project scope

### Automatic Snapshot Propagation Is Still Manual

Import/replace remains separated from export, publish, and Data Plane reload.

This is still intentional. Automatic propagation needs its own rollout, consistency, and rollback design.

### Full Registry Replacement Remains Blunt

Full replacement is acceptable as the v0 mutation primitive.

Granular CRUD should stay deferred until hosted identity, project scope, and mutation safety are clearer.

### Retention Cleanup Is Designed But Not Operationalized

Records have `expires_at`, but no background cleanup job exists yet.

That is acceptable for the local slice. Hosted deployments will need cleanup scheduling and retention policy controls.

## Still Not Allowed

Do not start:

- public registry CRUD APIs
- provider self-onboarding
- marketplace provider submission
- credential vault writes
- plaintext secret storage
- billing or settlement state
- workflow engine support
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Hosted Admin Identity Boundary Design v0
```

Why:

- idempotency scope already needs real `project_id` and authenticated `actor_id`
- current `X-Actor-ID` is only a local/private hint
- future hosted mutations need permissions before more write surfaces are added
- audit evidence should be tied to a stable admin principal, not an arbitrary header
- hosted readiness now depends more on identity/project boundaries than on adding more mutation mechanics

Expected design scope:

- authenticated admin principal shape
- project or organization scope
- replacement for local `X-Actor-ID` semantics in hosted mode
- role/permission checks for private admin mutations
- audit identity mapping
- idempotency `project_id` and `actor_id` derivation
- local/private compatibility behavior
- tests required for the later implementation slice

Out of scope for that task:

- public CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime

## Validation

Passed:

```text
python -m py_compile scripts\go_control_plane_idempotency_store_dogfood.py
python scripts\go_control_plane_idempotency_store_dogfood.py --output tmp\go_control_plane_idempotency_store_dogfood.json
go test ./...
```

Go test directory:

```text
services/control-plane
```
