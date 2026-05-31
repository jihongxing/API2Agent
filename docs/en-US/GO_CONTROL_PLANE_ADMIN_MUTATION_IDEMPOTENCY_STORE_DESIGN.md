# Go Control Plane Admin Mutation Idempotency Store Design v0

Date: 2026-05-31

Status: complete

## Decision

Add a Postgres-backed idempotency record for private admin mutation requests before adding more mutation endpoints or operator convenience features.

The first consumer is:

```text
POST /v1/admin/registry/import-replace
```

This design does not implement the table or service code yet. It defines the durable semantics that the later implementation slice must follow.

Recommended next task after this design is accepted:

```text
Go Control Plane Admin Mutation Idempotency Store Implementation v0
```

## Goals

The idempotency store must make these cases deterministic:

- same key plus same request returns the original committed response
- same key plus different request returns a stable conflict
- client timeout after server success can be retried safely
- response replay does not run the registry mutation again
- registry revision and admin audit evidence can be linked to the idempotency record
- records expire through explicit cleanup, not implicit request-time ambiguity

## Non-Goals

- no public registry CRUD APIs
- no provider self-onboarding
- no marketplace provider submission
- no credential vault writes
- no plaintext secret storage
- no billing, settlement, or revenue-share state
- no workflow engine
- no automatic snapshot export, publish, or Data Plane reload
- no direct Data Plane reads from Control Plane mutable tables

## Key Scope

The idempotency key is scoped by:

```text
project_id + actor_id + operation + idempotency_key_hash
```

For the current local/private import-replace endpoint:

- `project_id` is `control_plane` until hosted project identity exists.
- `actor_id` comes from the authenticated admin principal. In the current local endpoint this is `X-Actor-ID` or `admin`.
- `operation` is `registry.import_replace`.
- the raw `Idempotency-Key` header is trimmed, hashed, and never used alone as a global key.

The raw idempotency key should not be stored in the durable table. Store:

- `idempotency_key_hash`
- a short `idempotency_key_prefix` for debugging
- the hash algorithm, initially `sha256`

The existing audit metadata currently carries `idempotency_key`. The implementation slice should migrate new mutation audit metadata to `idempotency_key_hash` and `idempotency_key_prefix` to avoid preserving caller-supplied tokens indefinitely.

## Request Fingerprint

The request fingerprint is a hash of the canonical mutation intent, not the raw HTTP body.

For `registry.import_replace`, compute:

```json
{
  "version": "admin-mutation-idempotency-v0",
  "operation": "registry.import_replace",
  "method": "POST",
  "path": "/v1/admin/registry/import-replace",
  "registry_fingerprint": "sha256:...",
  "source": "admin_http_import",
  "dry_run": false
}
```

Rules:

- JSON field order, whitespace, and equivalent registry ordering must not change the fingerprint.
- `X-Request-ID` is not part of the fingerprint so a retry can use a new request id.
- `Idempotency-Key` is not part of the fingerprint because it is the lookup key.
- `actor_id` and `project_id` are not part of the fingerprint because they are already part of the key scope.
- `source` is part of the fingerprint because it changes audit evidence.
- `dry_run=true` remains unsupported and is rejected before mutation.

The implementation can derive `registry_fingerprint` using the same canonical registry path already used by `ReplacePersistentRegistry`.

## Record Schema

Proposed table:

```sql
CREATE TABLE admin_mutation_idempotency_records (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT 'control_plane',
  actor_id TEXT NOT NULL DEFAULT '',
  operation TEXT NOT NULL,
  idempotency_key_hash TEXT NOT NULL,
  idempotency_key_prefix TEXT NOT NULL DEFAULT '',
  idempotency_key_hash_algorithm TEXT NOT NULL DEFAULT 'sha256',
  request_fingerprint TEXT NOT NULL,
  request_fingerprint_algorithm TEXT NOT NULL DEFAULT 'sha256',
  request_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  first_request_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('processing', 'succeeded')),
  response_status_code INTEGER,
  response_body JSONB,
  response_fingerprint TEXT NOT NULL DEFAULT '',
  registry_fingerprint TEXT NOT NULL DEFAULT '',
  previous_registry_fingerprint TEXT NOT NULL DEFAULT '',
  snapshot_version TEXT NOT NULL DEFAULT '',
  noop BOOLEAN NOT NULL DEFAULT false,
  registry_revision_id BIGINT REFERENCES registry_revisions(id),
  admin_audit_event_id BIGINT REFERENCES admin_audit_events(id),
  replay_count BIGINT NOT NULL DEFAULT 0,
  last_replay_request_id TEXT NOT NULL DEFAULT '',
  last_replayed_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX admin_mutation_idempotency_records_unique_key
  ON admin_mutation_idempotency_records (
    project_id,
    actor_id,
    operation,
    idempotency_key_hash
  );

CREATE INDEX admin_mutation_idempotency_records_expires_at
  ON admin_mutation_idempotency_records (expires_at);

CREATE INDEX admin_mutation_idempotency_records_request_fingerprint
  ON admin_mutation_idempotency_records (request_fingerprint);
```

`processing` is inserted inside the same transaction before the mutation work and changed to `succeeded` before commit. Because it is transaction-local, normal callers should usually observe either no row or a committed `succeeded` row. The status remains useful for lock waits, diagnostics, and future implementations that may expose in-flight reservations more directly.

## Transaction Boundary

`ReplacePersistentRegistry` should remain the owner of the registry mutation transaction.

The implementation should extend that transaction in this order:

1. Canonicalize and validate the incoming registry.
2. Compute `registry_fingerprint` and the idempotency `request_fingerprint`.
3. Begin a serializable Postgres transaction.
4. Insert the idempotency reservation row with `status='processing'`.
5. If a committed row already exists for the scoped key:
   - same `request_fingerprint`: return replay path, no mutation
   - different `request_fingerprint`: return conflict
6. Acquire the registry mutation advisory lock.
7. Execute the existing import/replace or no-op path.
8. Insert registry revision when the registry changes.
9. Insert the required admin audit success event.
10. Update the idempotency record with response status, response body, linkage ids, fingerprints, and `status='succeeded'`.
11. Commit.

The idempotency success record, registry rows, registry revision, and admin audit success event must commit atomically.

If the transaction rolls back, the idempotency reservation rolls back with it. The same key can then be retried because there is no committed mutation outcome to replay.

## Response Replay

For same scoped key plus same request fingerprint:

- do not call `ReplacePersistentRegistry` mutation logic again
- return the cached `response_status_code`
- return the cached `response_body`
- preserve the original success semantics:
  - changed registry replay returns `201 Created`
  - no-op replay returns `200 OK`
- increment `replay_count`
- set `last_replay_request_id` to the retry request id
- set `last_replayed_at`

The implementation may add response headers such as:

```text
Idempotency-Replayed: true
Idempotency-Record-ID: <id>
```

Those headers are diagnostic only. The body remains the existing `ImportReplaceResponse` shape.

## Conflict Behavior

For same scoped key plus different request fingerprint:

```http
409 Conflict
```

```json
{
  "error": {
    "error_type": "IDEMPOTENCY_KEY_CONFLICT",
    "error_scope": "caller",
    "message": "idempotency key was already used for a different request",
    "retryable": false
  }
}
```

This conflict must not run the mutation and must not create a registry revision.

The conflict response should include only safe diagnostic metadata in logs or audit, such as operation, actor, project, key hash prefix, existing request fingerprint, and incoming request fingerprint. It must not echo the raw idempotency key.

## In-Progress And Concurrency Semantics

Concurrent identical requests with the same scoped key should result in one mutation.

The preferred v0 behavior is to let the second transaction wait on the unique key conflict until the first transaction commits or rolls back:

- if the first commits, the second request observes the succeeded record and replays it
- if the first rolls back, the second request may acquire the reservation and attempt the mutation
- if the wait exceeds the caller context deadline, return a retryable platform failure

If the implementation chooses an explicit in-progress response instead of waiting, use:

```text
409 IDEMPOTENCY_REQUEST_IN_PROGRESS platform retryable=true
```

The same behavior should apply only within the scoped key. Different actors or future projects can use the same `Idempotency-Key` value independently.

## Failure Semantics

The idempotency store caches committed mutation outcomes, not every HTTP failure.

No idempotency record is required for:

- invalid admin token
- missing `X-Request-ID`
- missing `Idempotency-Key`
- invalid JSON
- over-limit request body
- missing `registry`
- `dry_run=true`
- invalid registry that fails before a canonical request fingerprint is created

Failures after the transaction begins should roll back the idempotency reservation together with the registry mutation:

- registry advisory lock conflict
- persistent read/write failure
- required audit write failure
- serializable transaction failure
- commit failure where Postgres reports rollback

If a client times out after the server commits, a retry with the same scoped key and same request fingerprint returns the cached success response.

If `tx.Commit` returns an ambiguous error but Postgres actually committed, the retry path must still find the committed idempotency record and replay the success response. If Postgres rolled back, the retry path can attempt the mutation again.

## Audit And Revision Linkage

For changed registry imports:

- `registry_revisions.id` should be stored in `registry_revision_id`.
- `admin_audit_events.id` for `registry.import_replace` success should be stored in `admin_audit_event_id`.

For same-fingerprint no-op imports:

- `registry_revision_id` is null.
- `admin_audit_event_id` points at the `registry.import_replace` no-op success audit event.

Replay requests must not create additional registry revisions. A replay may either:

- update only the idempotency record replay fields, or
- additionally write a lightweight audit event such as `registry.import_replace.replay`

The v0 implementation should prefer updating replay fields first. A separate replay audit action can be added later if operators need a full replay event stream.

## Retention And Cleanup

Default retention:

```text
30 days after completed_at
```

`expires_at` means the record is eligible for cleanup. It does not mean request-time semantics silently disappear while the row still exists.

Rules:

- while a record exists, same-key same-request replays and same-key different-request conflicts remain enforced
- cleanup may delete records where `expires_at < now()`
- deleting an idempotency record must not delete registry revision or admin audit evidence
- hosted deployments can later tune retention by operation and project tier

## HTTP Error Mapping

Add these registry/service error types:

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| Same scoped key, different request | 409 | `IDEMPOTENCY_KEY_CONFLICT` | caller | false |
| Same scoped key still in progress, if not waiting | 409 | `IDEMPOTENCY_REQUEST_IN_PROGRESS` | platform | true |
| Idempotency store read failed | 503 | `IDEMPOTENCY_STORE_READ_FAILED` | platform | true |
| Idempotency store write failed | 503 | `IDEMPOTENCY_STORE_WRITE_FAILED` | platform | true |
| Cached response cannot be replayed | 500 | `IDEMPOTENCY_RESPONSE_REPLAY_FAILED` | platform | true |

Existing mutation errors keep their current mapping.

## Implementation Shape

Recommended Go shape:

- extend `registry.ImportReplaceOptions` with project or scope fields when hosted identity is introduced
- add a small idempotency helper owned by the registry package, not the HTTP handler
- make `insertRegistryRevisionTx` and `insertAdminAuditTx` return inserted ids
- have `ReplacePersistentRegistry` return either a normal result or a replayed result with status metadata
- keep HTTP request parsing and response writing in `httpapi`
- keep all mutable table writes in the registry package

The HTTP layer should compute only request identity and body parsing. The registry layer should own canonical request fingerprinting, idempotency reservation, transaction linkage, and replay decision.

## Tests Required For Implementation

Schema and registry-layer tests:

- unique key scope is `project_id + actor_id + operation + idempotency_key_hash`
- raw idempotency key is not stored
- same key plus same canonical request returns cached result
- same key plus different source or registry fingerprint returns `IDEMPOTENCY_KEY_CONFLICT`
- changed import stores `registry_revision_id` and `admin_audit_event_id`
- no-op import stores null `registry_revision_id` and non-null `admin_audit_event_id`
- audit write failure rolls back registry mutation and idempotency reservation
- commit success followed by client retry replays the committed response
- concurrent identical requests produce one registry replacement
- cleanup deletes expired idempotency rows without deleting audit or revision rows

HTTP tests:

- replayed changed import returns the original `201` and response body
- replayed no-op import returns the original `200` and response body
- conflict key reuse returns `409 IDEMPOTENCY_KEY_CONFLICT`
- idempotency store read/write failures map to `503`
- invalid auth, missing headers, invalid JSON, over-limit body, and `dry_run=true` do not require idempotency records
- `X-Request-ID` can differ between original request and replay
- replay does not trigger snapshot export, publish, Data Plane reload, or a second registry mutation

## Acceptance Criteria

This design is accepted when:

- persistent idempotency record schema is documented
- key scope is documented
- request fingerprint semantics are documented
- response replay semantics are documented
- same-key different-request conflict behavior is documented
- transaction boundary with `ReplacePersistentRegistry` is documented
- registry revision and admin audit linkage are documented
- retention and cleanup policy is documented
- failure semantics are documented
- implementation tests are named for the next slice
- public CRUD, vault, billing, marketplace, workflow, provider onboarding, and automatic propagation remain out of scope
