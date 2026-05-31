# Go Control Plane Private Admin Import/Replace Endpoint Implementation v0

Date: 2026-05-31

Status: complete

## Decision

The private admin import/replace endpoint is implemented.

Recommended next task:

```text
Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0
```

## Implemented Endpoint

```text
POST /v1/admin/registry/import-replace
```

The endpoint is a thin HTTP wrapper around the registry-layer import/replace primitive.

It does not implement granular CRUD.

It does not export, publish, or reload snapshots.

## Code Changes

Implemented in:

- `services/control-plane/internal/httpapi/service.go`
- `services/control-plane/internal/httpapi/service_test.go`
- `services/control-plane/cmd/api2agent-controlplane/main.go`

Documentation updated in:

- `services/control-plane/README.md`
- `README.md`
- `CHANGELOG.md`
- roadmap and implementation plan documents

## Runtime Wiring

`httpapi.Handler` now accepts a narrow import/replace dependency:

```go
type RegistryImportReplacer interface {
    ReplacePersistentRegistry(ctx context.Context, reg registry.Registry, opts registry.ImportReplaceOptions) (registry.ImportReplaceResult, error)
}
```

The `serve` command wires this dependency only when the runtime registry store is Postgres.

File-store mode remains unchanged and cannot mutate registry files through this endpoint.

## Request Contract

Required:

- `Authorization: Bearer <admin-token>`
- `X-Request-ID`
- `Idempotency-Key`

Optional:

- `X-Actor-ID`

Request body:

```json
{
  "registry": {},
  "source": "admin_http_import",
  "dry_run": false
}
```

Behavior:

- `source` defaults to `admin_http_import`.
- `X-Actor-ID` defaults to `admin`.
- `dry_run=true` is rejected in v0.
- request body is capped at 2 MiB.

## Response Contract

Changed registry:

```text
201 Created
```

Same-fingerprint no-op:

```text
200 OK
```

Both responses include:

- `registry_store`
- `registry_fingerprint`
- `previous_registry_fingerprint`
- `snapshot_version`
- `noop`
- object counts

## Error Mapping

Implemented stable mappings:

| Condition | HTTP | error_type |
| --- | ---: | --- |
| missing/invalid admin token | 401 | `AUTH_ERROR` |
| missing `X-Request-ID` | 400 | `INVALID_REQUEST` |
| missing `Idempotency-Key` | 400 | `INVALID_REQUEST` |
| invalid JSON / missing registry / `dry_run=true` | 400 | `INVALID_REQUEST` |
| body over 2 MiB | 413 | `REQUEST_BODY_TOO_LARGE` |
| file store or unconfigured mutator | 409 | `REGISTRY_MUTATION_UNAVAILABLE` |
| invalid registry graph | 400 | `REGISTRY_MUTATION_INVALID` |
| mutation conflict | 409 | `REGISTRY_MUTATION_CONFLICT` |
| persistent read/write failure | 503 | `PERSISTENT_STORE_READ_FAILED` / `PERSISTENT_STORE_WRITE_FAILED` |
| audit write failure | 500 | `AUDIT_WRITE_FAILED` |

Unknown mutation errors fail closed as `REGISTRY_MUTATION_FAILED`.

## Snapshot Boundary

The endpoint does not advance snapshots.

The operator sequence remains:

```text
import/replace persistent registry
  -> export artifact
  -> publish distribution
  -> Data Plane reload
```

## Tests Added

Coverage includes:

- admin token required
- `X-Request-ID` required
- `Idempotency-Key` required
- file-store mutation unavailable
- invalid JSON
- missing registry wrapper field
- `dry_run=true`
- request body larger than 2 MiB
- changed registry returns `201`
- no-op registry returns `200`
- actor/request/idempotency/source options passed into registry layer
- `RegistryMutationError` HTTP mappings

## Validation

Passed:

```text
go test ./...
```

from:

```text
services/control-plane
```

## Non-Goals Preserved

- no public CRUD registry API
- no provider self-onboarding
- no marketplace
- no billing or settlement
- no credential vault
- no plaintext secret storage
- no workflow engine
- no automatic snapshot export/publish/reload
- no Data Plane reads from mutable Control Plane tables

