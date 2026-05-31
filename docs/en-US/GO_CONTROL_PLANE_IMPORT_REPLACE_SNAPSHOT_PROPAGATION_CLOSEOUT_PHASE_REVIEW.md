# Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0

Date: 2026-05-31

Status: complete

## Decision

The import/replace snapshot propagation milestone can close.

The project now has a proven local Control Plane write-side path and a proven manual snapshot handoff into Data Plane execution:

```text
private admin HTTP import/replace
  -> persistent Postgres registry replacement
  -> snapshot artifact export
  -> distribution publish
  -> manual Data Plane reload
  -> Data Plane execution with replaced provider
```

Recommended next task:

```text
Go Control Plane Admin Mutation Idempotency Store Design v0
```

This should be a design task before implementation. The current endpoint requires `Idempotency-Key`, but it does not yet persist request/result idempotency records.

## What Is Now Complete

### Persistent Registry Write Path

Completed:

- controlled full-registry import/replace transaction
- serializable transaction boundary
- transaction-scoped advisory lock
- same-fingerprint no-op handling
- same-transaction revision and audit evidence
- rollback on required audit failure
- local/admin CLI mutation path

References:

- `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_TRANSACTION_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_CLI_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_LIVE_POSTGRES_DOGFOOD_REPORT.md`

### Private Admin Endpoint

Completed:

- `POST /v1/admin/registry/import-replace`
- admin bearer auth boundary
- required `X-Request-ID`
- required `Idempotency-Key`
- wrapper request body
- request-size limit
- Postgres-only mutation wiring
- FileStore/unconfigured mutation rejection
- stable service error mapping
- live Postgres dogfood

References:

- `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_LIVE_POSTGRES_DOGFOOD_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_CLOSEOUT_PHASE_REVIEW.md`

### Snapshot Propagation E2E

Completed:

- Control Plane and Data Plane local service startup
- initial `ipify_public_ip_v1` snapshot publication
- HTTP import/replace to `httpbin_public_ip_v1`
- replacement snapshot artifact export
- replacement distribution publish
- manual Data Plane reload
- Data Plane execution using the replaced provider
- usage/decision attribution to the replaced provider and snapshot version
- persistent audit count assertions

Observed:

```json
{
  "initial_published_snapshot_version": "snapshot_propagation_ipify_v1",
  "replacement_published_snapshot_version": "snapshot_propagation_httpbin_v2",
  "usage_provider_id": "httpbin",
  "usage_snapshot_version": "snapshot_propagation_httpbin_v2",
  "decision_selected_provider_id": "httpbin_public_ip_v1",
  "audit_counts": {
    "registry_revisions": 4,
    "admin_audit_events": 5,
    "providers": 1,
    "snapshot_artifact_publications": 2
  }
}
```

Reference:

- `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| Persistent registry can be replaced through a controlled private endpoint | passed |
| Replacement writes persistent audit evidence | passed |
| Replacement remains Postgres-only | passed |
| FileStore remains default and read-only for mutation | passed |
| Replaced registry can be exported as a snapshot artifact | passed |
| Replaced artifact can be published into a distribution | passed |
| Data Plane can manually reload the changed distribution | passed |
| Data Plane execution uses the replaced provider | passed |
| Usage and decision records preserve replaced provider attribution | passed |
| Snapshot propagation remains manually sequenced | passed |
| Public CRUD remains out of scope | passed |
| Credential vault, billing, marketplace, workflow runtime, and provider onboarding remain out of scope | passed |

## Closeout Judgment

This milestone is complete and can pause.

The important proof is not just that the endpoint writes Postgres. The important proof is that a registry mutation can be moved through the existing artifact/distribution boundary and change real Data Plane execution without letting the Data Plane read mutable Control Plane tables.

That preserves the architecture rule:

```text
Control Plane owns mutable registry state.
Data Plane consumes immutable/versioned snapshots.
```

## Remaining Risks

### Idempotency Is Header-Only

The endpoint requires `Idempotency-Key`, but v0 does not persist idempotency records.

Current behavior is safe enough for local dogfood because registry fingerprint no-op detection prevents many duplicate effects. It is not enough for hosted mutation semantics because it cannot distinguish:

- same key + same request body replay
- same key + different request body conflict
- request completed but client timed out
- request accepted but audit/export side effects need result replay

This is the next highest-signal gap.

### Admin Auth Is Still Local-Private

Bearer-token admin auth is sufficient for local/private dogfood.

It is not a hosted multi-admin identity or permission model.

### Propagation Is Manual

Import/replace does not automatically publish or reload snapshots.

This remains intentional. Automatic propagation should not be implemented without a separate design for blast radius, rollout order, rollback, and multi-node Data Plane consistency.

### Full Registry Replacement Is Blunt

Full replacement is the correct v0 mutation primitive, but it is not the final operator experience.

Granular CRUD remains deferred.

### Distribution Is Still Local Filesystem

The current distribution is a local directory.

Remote object storage, signed artifacts, and multi-region distribution remain later hosted concerns.

### Registry Size Limit Is Conservative

The endpoint still uses a conservative 2 MiB request-size limit.

Large hosted registries may need artifact-based upload or configurable limits later.

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
Go Control Plane Admin Mutation Idempotency Store Design v0
```

Why:

- the endpoint already requires `Idempotency-Key`
- the write path is now proven end to end
- hosted/private admin mutation cannot rely only on request headers and registry fingerprint no-op checks
- idempotency semantics should be designed before adding more mutation endpoints or operator convenience features

Expected design scope:

- persistent idempotency record shape
- key scope: actor/project/operation/key
- request fingerprint semantics
- response replay semantics
- conflict detection for key reuse with a different request
- audit linkage to registry revision and admin audit event ids
- transaction boundary with `ReplacePersistentRegistry`
- expiration/retention policy
- failure semantics

Out of scope for that task:

- public CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace

## Validation

Passed before closeout:

```text
python scripts/go_control_plane_import_replace_snapshot_propagation_dogfood.py --output tmp/go_control_plane_import_replace_snapshot_propagation_dogfood.json
go test ./...
```

Go test directories:

```text
services/control-plane
services/data-plane
```
