# Go Control Plane Admin Mutation Idempotency Store Implementation Report v0

Date: 2026-05-31

Status: complete

## Summary

Implemented the first Postgres-backed idempotency store for private admin registry mutations.

The implementation is limited to:

```text
POST /v1/admin/registry/import-replace
```

It does not add public CRUD, automatic snapshot propagation, vault, billing, marketplace, workflow runtime, or provider onboarding scope.

## What Changed

- Added `admin_mutation_idempotency_records` to the Postgres schema.
- Added scoped key hashing for `project_id + actor_id + operation + Idempotency-Key`.
- Added canonical request fingerprinting for import/replace requests.
- Added same-key same-request response replay.
- Added same-key different-request conflict detection.
- Linked idempotency records to `registry_revisions.id` and `admin_audit_events.id`.
- Kept idempotency reservation, registry mutation, registry revision, admin audit success, and cached outcome in one serializable transaction.
- Added HTTP replay headers:
  - `Idempotency-Replayed: true`
  - `Idempotency-Record-ID: <id>`
- Added stable HTTP error mapping for idempotency conflicts and store failures.

## Transaction Semantics

For requests with `Idempotency-Key`, `ReplacePersistentRegistry` now:

1. Canonicalizes and fingerprints the incoming registry.
2. Computes the import/replace idempotency request fingerprint.
3. Begins the existing serializable transaction.
4. Reserves the scoped idempotency key.
5. Replays a committed result if the same key and request fingerprint already exist.
6. Rejects the request if the same key was used for a different request fingerprint.
7. Runs the existing registry replacement or no-op path.
8. Writes registry revision and admin audit evidence.
9. Completes the idempotency record with the cached response and evidence links.
10. Commits atomically.

If the transaction rolls back, the idempotency reservation rolls back too.

## Response Semantics

Same-key same-request replay:

- does not mutate registry tables
- does not create another registry revision
- does not create another mutation audit event
- returns the cached `ImportReplaceResult`
- preserves the original status behavior:
  - changed import: `201`
  - no-op import: `200`

Same-key different-request reuse returns:

```text
409 IDEMPOTENCY_KEY_CONFLICT caller retryable=false
```

## Tests Added

- no-op import stores a completed idempotency record with audit linkage and no registry revision linkage
- changed import stores a completed idempotency record with audit and revision linkage
- raw idempotency keys are not stored in the scripted persistent rows
- same key plus same canonical request replays the cached result without replacing rows again
- same key plus different request returns `IDEMPOTENCY_KEY_CONFLICT`
- HTTP replay responses include replay headers
- HTTP error mapping covers idempotency conflict, in-progress, store read/write, and replay failures
- schema test asserts the idempotency table, unique key, and audit/revision references

## Validation

Passed:

```text
go test ./...
```

Directory:

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Admin Mutation Idempotency Store Live Postgres Dogfood v0
```

The dogfood should verify the same replay and conflict semantics against a real Postgres instance.
