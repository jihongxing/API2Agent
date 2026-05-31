# Go Control Plane Private Admin Import/Replace Endpoint Design v0

Date: 2026-05-31

Status: complete

## Decision

Add a private admin HTTP contract for the already implemented persistent registry import/replace primitive.

Recommended next implementation task:

```text
Go Control Plane Private Admin Import/Replace Endpoint Implementation v0
```

This endpoint is a thin service wrapper around:

```go
registry.ReplacePersistentRegistry(ctx, db, reg, opts)
```

It must not become a public registry CRUD surface.

## Endpoint Contract

```text
POST /v1/admin/registry/import-replace
```

This endpoint is private admin only.

It replaces the active Postgres-backed registry graph from a full validated registry document, then returns the same mutation result produced by the registry layer.

It does not export, publish, or reload snapshots.

The follow-up sequence remains:

```text
POST /v1/admin/registry/import-replace
  -> POST /v1/admin/snapshots/export-artifact
  -> POST /v1/admin/distribution/publish
  -> Data Plane reload
```

## Store Boundary

The endpoint is enabled only for the explicit Postgres persistent registry store.

Rules:

- `FileStore` remains the default store.
- file-backed service mode must not mutate registry files through this endpoint.
- if the service is not running with the Postgres mutation dependency configured, return `409 REGISTRY_MUTATION_UNAVAILABLE`.
- the Data Plane continues to consume snapshots, not mutable Control Plane tables.

## Required Headers

| Header | Required | Purpose |
| --- | --- | --- |
| `Authorization: Bearer <admin-token>` | yes | Existing private admin auth boundary. |
| `X-Request-ID` | yes | Correlates admin request, mutation audit, and registry revision source. |
| `Idempotency-Key` | yes | Required for HTTP mutation safety and audit traceability. |
| `X-Actor-ID` | no | Local/private actor override. If absent, use `admin`. |

Header validation:

- `Authorization` follows the existing admin-token behavior.
- missing or blank `X-Request-ID` returns `400 INVALID_REQUEST`.
- missing or blank `Idempotency-Key` returns `400 INVALID_REQUEST`.
- blank `X-Actor-ID` is treated as absent.
- implementation should trim surrounding whitespace.

## Request Body

Use a wrapper object instead of raw registry JSON so the endpoint has room for future flags without changing the top-level contract.

```json
{
  "registry": {
    "projects": [],
    "api_keys": [],
    "capabilities": [],
    "providers": [],
    "credential_metadata": [],
    "routing_policy": {},
    "snapshot": {}
  },
  "source": "admin_http_import",
  "dry_run": false
}
```

Fields:

| Field | Required | v0 behavior |
| --- | --- | --- |
| `registry` | yes | Full registry document to canonicalize, validate, fingerprint, and replace. |
| `source` | no | Audit metadata hint. If absent, use `admin_http_import`. |
| `dry_run` | no | Reserved. Omitted or `false` is allowed; `true` returns `400 INVALID_REQUEST` in v0. |

Credential rule:

- registry credential rows remain metadata-only.
- no plaintext API key, OAuth token, or provider secret may be accepted as part of this endpoint.
- if the registry shape later grows secret-bearing fields, this endpoint must reject them before mutation.

## Request Size Limit

v0 should cap the HTTP request body before JSON decoding.

Default limit:

```text
2 MiB
```

Implementation note:

- use `http.MaxBytesReader` or equivalent.
- body-size failures return `413 REQUEST_BODY_TOO_LARGE`.
- the limit can become configurable later, but the v0 contract should ship with a bounded default.

## Response Shape

For a changed registry:

```http
201 Created
```

```json
{
  "registry_store": "postgres",
  "registry_fingerprint": "sha256:...",
  "previous_registry_fingerprint": "sha256:...",
  "snapshot_version": "snapshot_v1",
  "noop": false,
  "counts": {
    "projects": 1,
    "api_keys": 1,
    "capabilities": 1,
    "providers": 1,
    "credential_metadata": 1,
    "routing_policies": 1,
    "snapshot_configs": 1
  }
}
```

For a same-fingerprint no-op:

```http
200 OK
```

```json
{
  "registry_store": "postgres",
  "registry_fingerprint": "sha256:...",
  "previous_registry_fingerprint": "sha256:...",
  "snapshot_version": "snapshot_v1",
  "noop": true,
  "counts": {
    "projects": 1,
    "api_keys": 1,
    "capabilities": 1,
    "providers": 1,
    "credential_metadata": 1,
    "routing_policies": 1,
    "snapshot_configs": 1
  }
}
```

## Registry Mutation Options Mapping

Map HTTP request identity into registry-layer options:

```go
registry.ImportReplaceOptions{
    ActorID:        actorIDFromHeaderOrAdmin,
    RequestID:      requestIDHeader,
    IdempotencyKey: idempotencyKeyHeader,
    Source:         request.SourceOrDefault,
}
```

Rules:

- `RequestID` must come from `X-Request-ID`.
- `IdempotencyKey` must come from `Idempotency-Key`.
- `ActorID` should come from `X-Actor-ID` for local/private use, otherwise `admin`.
- future hosted auth may replace `X-Actor-ID` with the authenticated principal, but must preserve the audit field.

## Status Codes And Error Mapping

The endpoint must reuse the current service error envelope:

```json
{
  "error": {
    "error_type": "REGISTRY_MUTATION_INVALID",
    "error_scope": "caller",
    "message": "...",
    "retryable": false
  }
}
```

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| Missing or invalid admin token | 401 | `AUTH_ERROR` | caller | false |
| Wrong method | 405 | `INVALID_REQUEST` | caller | false |
| Missing `X-Request-ID` | 400 | `INVALID_REQUEST` | caller | false |
| Missing `Idempotency-Key` | 400 | `INVALID_REQUEST` | caller | false |
| Invalid JSON body | 400 | `INVALID_REQUEST` | caller | false |
| Missing `registry` wrapper field | 400 | `INVALID_REQUEST` | caller | false |
| `dry_run=true` in v0 | 400 | `INVALID_REQUEST` | caller | false |
| Request body over limit | 413 | `REQUEST_BODY_TOO_LARGE` | caller | false |
| Service not configured for Postgres mutation | 409 | `REGISTRY_MUTATION_UNAVAILABLE` | platform | false |
| Invalid registry payload or graph | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| Concurrent registry mutation | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Serializable transaction conflict | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| Persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| Required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

`registry.RegistryMutationError` should be the source of truth for registry-layer failures:

- `REGISTRY_MUTATION_INVALID` -> `400`
- `REGISTRY_MUTATION_CONFLICT` -> `409`
- `PERSISTENT_STORE_READ_FAILED` -> `503`
- `PERSISTENT_STORE_WRITE_FAILED` -> `503`
- `AUDIT_WRITE_FAILED` -> `500`

Unknown registry-layer errors should fail closed as:

```text
500 REGISTRY_MUTATION_FAILED platform retryable=true
```

## Audit Mapping

The registry layer already writes required success/failure audit evidence. The endpoint must pass request identity through; it should not write a second success audit for the same mutation.

Required audit action:

```text
registry.import_replace
```

Required audit metadata:

- `registry_store=postgres`
- `mutation_mode=import_replace`, `import_replace_noop`, or `import_replace_failure`
- `registry_fingerprint`
- `previous_registry_fingerprint` when available
- `snapshot_version` when available
- `idempotency_key`
- `source`
- object counts:
  - `projects`
  - `api_keys`
  - `capabilities`
  - `providers`
  - `credential_metadata`
  - `routing_policies`
  - `snapshot_configs`

Failure audit remains best effort and must not obscure the original HTTP error.

## Idempotency Semantics

The HTTP endpoint requires `Idempotency-Key`, but v0 idempotency is still registry-fingerprint based.

Meaning:

- if incoming fingerprint equals current persistent registry fingerprint, return `200 OK` with `noop=true`.
- if incoming fingerprint differs, execute a full replace and return `201 Created` with `noop=false`.
- v0 does not introduce an idempotency-key result cache.
- repeated requests with the same key but a different registry document are not accepted as equivalent; they should run through normal fingerprint and transaction semantics.

Future enhancement:

- a request-id/idempotency-key table may later detect conflicting reuse of an idempotency key.
- this is not required for v0 implementation.

## Implementation Seam

Recommended service seam:

```go
type RegistryImportReplacer interface {
    ReplacePersistentRegistry(ctx context.Context, reg registry.Registry, opts registry.ImportReplaceOptions) (registry.ImportReplaceResult, error)
}
```

or a narrower handler dependency over the existing Postgres DB handle.

The endpoint should not reach around the registry layer to manually edit tables.

## Tests Required For Implementation

Minimum tests:

- endpoint is registered at `POST /v1/admin/registry/import-replace`
- admin token is required
- `X-Request-ID` is required
- `Idempotency-Key` is required
- invalid JSON returns `400 INVALID_REQUEST`
- missing `registry` returns `400 INVALID_REQUEST`
- `dry_run=true` returns `400 INVALID_REQUEST`
- over-limit body returns `413 REQUEST_BODY_TOO_LARGE`
- file-store/unconfigured mutation returns `409 REGISTRY_MUTATION_UNAVAILABLE`
- changed registry returns `201` and the registry-layer result
- no-op registry returns `200` and `noop=true`
- `RegistryMutationError` values map to stable HTTP status and error response fields
- actor/request/idempotency/source are passed into `ImportReplaceOptions`
- snapshot export/publish/reload are not triggered by import/replace

## Non-Goals

- no public CRUD registry APIs
- no provider self-onboarding
- no marketplace provider submission
- no credential vault writes
- no plaintext API key storage
- no billing, settlement, or revenue-share state
- no workflow engine
- no automatic snapshot export, publish, or Data Plane reload
- no direct Data Plane reads from Control Plane mutable tables

## Acceptance Criteria

This design is accepted when:

- endpoint method/path is documented
- request/response schema is documented
- required headers and identity mapping are documented
- idempotency behavior is documented
- error mapping is documented
- audit mapping is documented
- request size limit is documented
- snapshot boundary remains explicit
- implementation remains deferred to the next task

