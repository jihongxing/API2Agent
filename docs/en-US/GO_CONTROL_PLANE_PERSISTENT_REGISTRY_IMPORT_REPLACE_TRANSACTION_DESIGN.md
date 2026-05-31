# Go Control Plane Persistent Registry Import/Replace Transaction Design v0

Date: 2026-05-31

Status: complete

## Decision

The first persistent registry write-side operation should be a controlled full-registry import/replace transaction.

It should not be a public CRUD API.

Recommended next implementation task:

```text
Go Control Plane Persistent Registry Import/Replace CLI Implementation v0
```

The implementation should introduce a narrow local/admin operation that replaces the active persistent registry view from a validated registry document, writes required audit evidence, and leaves snapshot export/publish as separate operations.

## Scope

This design covers:

- transaction boundary
- validation and canonicalization order
- idempotency semantics
- registry-wide mutation lock
- mutable table replacement strategy
- required audit writes
- rollback behavior
- stable error taxonomy
- expected implementation seam

This design does not implement the operation.

## Current Code Facts

The current repository already has:

- `registry.Store` as the Control Plane state boundary.
- `FileStore` as the default runtime store.
- `PostgresStore.Load(ctx)` as a read-only `REPEATABLE READ` persistent load path.
- `MapRegistryToPersistentRows(reg)` for file registry to persistent row mapping.
- `BuildRegistryFromPersistentRows(rows)` for persistent row to registry reconstruction.
- `CanonicalRegistry(reg)` and `Registry.Fingerprint()`.
- `SeedPostgresRegistry(ctx, db, reg)` as a local dogfood import helper.
- persistent audit tables: `registry_revisions`, `snapshot_artifact_publications`, and `admin_audit_events`.

Important distinction:

`seed-postgres` is not the production mutation path. It is an upsert-based local dogfood helper and does not provide the full import/replace transaction semantics required here.

## Operation Contract

Suggested internal API:

```go
type ImportReplaceOptions struct {
    ActorID        string
    RequestID      string
    IdempotencyKey string
    Source         string
}

type ImportReplaceResult struct {
    RegistryFingerprint         string
    PreviousRegistryFingerprint string
    SnapshotVersion             string
    Noop                        bool
    Counts                      ImportReplaceCounts
}

func ReplacePersistentRegistry(ctx context.Context, db *sql.DB, reg Registry, opts ImportReplaceOptions) (ImportReplaceResult, error)
```

Suggested CLI shape:

```text
api2agent-controlplane import-replace-postgres \
  --registry <registry.json> \
  --postgres-dsn <dsn> \
  --actor-id <actor> \
  --request-id <request-id> \
  [--idempotency-key <key>]
```

This command should be local/admin only. It should not expose a hosted public mutation API.

## Execution Order

### 1. Parse Input Outside the Transaction

Read and decode the registry document before opening a write transaction.

Failures here return:

```text
REGISTRY_MUTATION_INVALID
```

No mutable rows are touched.

### 2. Canonicalize and Validate Outside the Transaction

Apply:

```go
canonical := CanonicalRegistry(reg)
err := canonical.Validate()
fingerprint := canonical.Fingerprint()
rows := MapRegistryToPersistentRows(canonical)
```

Rules:

- canonicalization must not mutate the input registry
- fingerprint must be computed from the canonical validated registry
- row mapping must not invent secret material
- credential rows remain metadata-only
- current file-shaped `APIKey` input cannot author `key_hash`; the implementation must not invent one

### 3. Begin a Serializable Write Transaction

Use:

```go
db.BeginTx(ctx, &sql.TxOptions{
    Isolation: sql.LevelSerializable,
    ReadOnly:  false,
})
```

Reason:

The operation replaces a coupled registry graph and must not interleave with another mutation.

### 4. Acquire Registry-Wide Mutation Lock

Use a transaction-scoped advisory lock.

Recommended lock:

```sql
SELECT pg_try_advisory_xact_lock(22021, 1)
```

Semantics:

- `true`: continue
- `false`: rollback and return `REGISTRY_MUTATION_CONFLICT`

Rationale:

The lock is explicit, local to the transaction, and avoids partial concurrent registry replacement.

### 5. Load Current Active Registry in the Same Transaction

Call:

```go
LoadPersistentRows(ctx, tx)
BuildRegistryFromPersistentRows(rows)
current.Fingerprint()
```

If the persistent store is empty, treat `previous_registry_fingerprint` as empty and continue.

If active rows exist but cannot be reconstructed, return:

```text
PERSISTENT_STORE_READ_FAILED
```

### 6. Idempotent No-Op Check

If:

```text
incoming_fingerprint == previous_registry_fingerprint
```

then:

- do not rewrite mutable registry tables
- write one `admin_audit_events` row with `outcome=success`
- include `mutation_mode=import_replace_noop`
- include `registry_fingerprint`, `previous_registry_fingerprint`, `idempotency_key`, and object counts
- commit

Do not write a duplicate `registry_revisions` row for a no-op.

### 7. Replace Mutable Registry Tables

The mutable registry state is:

- `projects`
- `api_keys`
- `capabilities`
- `providers`
- `credential_metadata`
- `routing_policies`
- `snapshot_configs`

Recommended replacement strategy for v0:

1. delete existing mutable rows in dependency-safe order
2. insert canonical incoming rows in dependency-safe order
3. do not touch append-only evidence tables

Delete order:

```text
providers
credential_metadata
api_keys
routing_policies
snapshot_configs
capabilities
projects
```

Insert order:

```text
projects
api_keys
capabilities
providers
credential_metadata
routing_policies
snapshot_configs
```

Why delete/insert instead of row-by-row upsert:

- this is full-registry replacement, not partial CRUD
- absent objects must disappear from the active registry view
- deterministic replacement is easier to audit and reason about
- append-only revision tables already preserve evidence

The implementation may later optimize to staged upsert plus disabled status, but v0 should prioritize correctness and explainability.

### 8. Rebuild and Validate the Written Registry Before Commit

Still inside the same transaction:

```go
writtenRows := LoadPersistentRows(ctx, tx)
writtenRegistry := BuildRegistryFromPersistentRows(writtenRows)
writtenFingerprint := writtenRegistry.Fingerprint()
```

Require:

```text
writtenFingerprint == incoming_fingerprint
```

If it does not match, rollback with:

```text
REGISTRY_MUTATION_INVALID
```

This prevents silent drift between the registry document and persistent rows.

### 9. Write Required Audit Evidence in the Same Transaction

For accepted non-noop mutations, write:

`registry_revisions`:

- `registry_fingerprint`
- `snapshot_version`
- `source_store=postgres`
- `source_revision=<request_id or idempotency_key>`
- `created_by=<actor_id>` when available

`admin_audit_events`:

- `action=registry.import_replace`
- `resource_type=registry`
- `resource_id=<registry_fingerprint>`
- `request_id=<request_id>`
- `actor_id=<actor_id>`
- `outcome=success`
- `metadata` containing:
  - `mutation_mode=import_replace`
  - `registry_store=postgres`
  - `registry_fingerprint`
  - `previous_registry_fingerprint`
  - `snapshot_version`
  - `idempotency_key`
  - affected object counts

The operation must fail closed if either required audit write fails.

### 10. Commit

Only after mutable rows, revision evidence, and success audit have all been written.

## Failure Audit

Rejected mutations should attempt a best-effort failure audit when a database connection is available.

Failure audit rules:

- do not obscure the original error
- do not turn invalid input into success
- do not write failure audit inside a transaction that is already rolling back
- include `error_type`, `request_id`, `actor_id`, `idempotency_key`, and any available fingerprint metadata

## Error Taxonomy

| Condition | HTTP | error_type | scope | retryable |
| --- | ---: | --- | --- | --- |
| Invalid registry payload or graph | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| Persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| Persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| Concurrent mutation lock unavailable | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Serializable transaction conflict | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

For the first CLI implementation, these can be represented as structured Go errors and rendered as deterministic CLI error output. HTTP mapping is reserved for a later admin service endpoint.

## Rollback Semantics

The transaction must roll back all of the following together:

- mutable table deletes
- mutable table inserts
- `registry_revisions` writes
- success `admin_audit_events` writes

No partial success is allowed.

Failure audit may be written after rollback as best effort.

## Snapshot Boundary

Import/replace does not publish or reload snapshots.

The sequence remains:

```text
import/replace persistent registry
  -> export artifact
  -> publish distribution
  -> Data Plane reload
```

This preserves the existing Control Plane/Data Plane handoff. Data Plane still consumes versioned snapshots, not mutable Control Plane tables.

## Implementation Notes

Recommended new files:

- `services/control-plane/internal/registry/postgres_import_replace.go`
- `services/control-plane/internal/registry/postgres_import_replace_test.go`

Recommended command:

- `import-replace-postgres`

Recommended tests:

- invalid registry fails before mutation
- same fingerprint returns no-op and writes success audit only
- changed registry replaces active rows and writes revision plus audit
- removed provider disappears from active load output
- rollback on provider insert failure preserves previous registry
- lock conflict returns `REGISTRY_MUTATION_CONFLICT`
- required success audit failure rolls back the mutation
- file store behavior remains unchanged

## Non-Goals

- no public CRUD endpoints
- no hosted provider onboarding
- no credential vault writes
- no plaintext API key storage
- no marketplace provider submission
- no billing or settlement
- no Data Plane direct reads from Control Plane tables
- no automatic snapshot publish or reload

