# Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0

Date: 2026-05-31

Status: complete

## Decision

The private admin import/replace endpoint milestone can close.

Recommended next task:

```text
Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0
```

The next task should verify the full operator sequence after a registry mutation:

```text
HTTP import/replace
  -> snapshot artifact export
  -> distribution publish
  -> Data Plane reload
  -> Data Plane execution uses replaced provider
```

This is still dogfood and propagation validation. It is not public CRUD, marketplace, billing, vault, or provider onboarding.

## What Is Now Complete

### Endpoint Design

Completed:

- private admin method/path
- wrapper request body
- required `X-Request-ID`
- required `Idempotency-Key`
- optional actor identity
- 2 MiB request-size limit
- stable response shape
- stable error mapping
- audit mapping through the registry layer
- explicit snapshot boundary

Reference:

- `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`

### Endpoint Implementation

Completed:

- `POST /v1/admin/registry/import-replace`
- narrow `RegistryImportReplacer` seam
- Postgres-only mutation wiring in `serve`
- FileStore/unconfigured mutation rejection
- request/idempotency header enforcement
- wrapper request decoding
- `dry_run=true` rejection
- `RegistryMutationError` HTTP mapping
- unit tests for request validation, status codes, options propagation, and error mapping

Reference:

- `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

Completed with podman:

- service started with `--registry-store postgres`
- changed-registry HTTP import/replace returned `201`
- same-registry HTTP import/replace returned `200`
- service validation saw replaced registry
- service artifact export saw replaced registry
- exported snapshot provider was `httpbin_public_ip_v1`
- persistent audit counts were asserted

Observed:

```json
{
  "replace_status": 201,
  "replace_noop": false,
  "noop_status": 200,
  "second_noop": true,
  "snapshot_version": "snapshot_http_import_replace_live_v1",
  "provider_id": "httpbin_public_ip_v1",
  "audit_counts": {
    "registry_revisions": 3,
    "admin_audit_events": 4,
    "providers": 1
  }
}
```

Reference:

- `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_LIVE_POSTGRES_DOGFOOD_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| Private admin endpoint contract documented | passed |
| Endpoint implemented behind admin auth | passed |
| Postgres-only mutation boundary enforced | passed |
| FileStore behavior unchanged | passed |
| `X-Request-ID` required | passed |
| `Idempotency-Key` required | passed |
| Wrapper request body implemented | passed |
| Request-size limit implemented | passed |
| Changed registry returns `201` | passed |
| Same-fingerprint no-op returns `200` | passed |
| Registry-layer audit remains authoritative | passed |
| Live Postgres HTTP replacement verified | passed |
| Service validation/export sees replaced registry | passed |
| Public CRUD remains out of scope | passed |
| Snapshot publish/reload remains separate | passed |

## Closeout Judgment

This milestone is complete.

The project now has a controlled private write-side path for replacing the persistent registry through the service API.

This matters because the Control Plane is no longer read-only for persistent registry state, but the write boundary is still narrow, auditable, and reversible by replacing the full registry document again.

## Remaining Risks

### Hosted Auth Is Still Local-Admin Grade

Current admin auth is bearer-token based and suitable for local/private dogfood.

It is not yet a hosted multi-admin identity model.

### Idempotency Key Is Required But Not Cached

The endpoint requires `Idempotency-Key`, but v0 idempotency is still fingerprint-based.

Future hosted mutation APIs may need a request/idempotency table to detect conflicting key reuse.

### Full Registry Replacement Is Blunt

This is intentional for v0.

Granular CRUD remains deferred until the full replacement path proves stable.

### Snapshot Propagation Is Manual

Import/replace does not publish or reload snapshots.

The next useful proof is an E2E dogfood of the full manual propagation sequence.

### Large Registry Limit Is Conservative

The 2 MiB HTTP limit is enough for current dogfood.

Future large hosted registries may need a configurable limit or artifact-based upload.

## Still Not Allowed

Do not start:

- public CRUD registry APIs
- provider self-onboarding
- marketplace provider submission
- credential vault writes
- plaintext secret storage
- billing or settlement state
- workflow engine support
- automatic publish/reload without an explicit propagation design

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0
```

Why:

- the write-side endpoint is proven
- snapshot export and publish already exist
- Data Plane manual reload already exists
- the missing proof is propagation from changed registry to Data Plane execution behavior

Expected proof:

- HTTP import/replace changes provider from `ipify_public_ip_v1` to `httpbin_public_ip_v1`
- Control Plane exports and publishes the new snapshot
- Data Plane reloads the distribution
- Data Plane execution records use `httpbin_public_ip_v1`

## Validation

Passed:

```text
go test ./...
```

from:

```text
services/control-plane
```

