# Go Control Plane Persistent Registry Import/Replace CLI Implementation v0

Date: 2026-05-31

Status: complete

## Summary

Implemented the first controlled persistent registry write-side path:

```text
api2agent-controlplane import-replace-postgres
```

This is a local/admin CLI operation only. It does not add public CRUD endpoints or a hosted mutation API.

## Implemented

- `registry.ReplacePersistentRegistry(ctx, db, reg, opts)`
- `ImportReplaceOptions`, `ImportReplaceResult`, and `ImportReplaceCounts`
- structured `RegistryMutationError`
- serializable write transaction
- transaction-scoped advisory lock:

```sql
SELECT pg_try_advisory_xact_lock(22021, 1)
```

- full mutable registry table replacement
- same-transaction `registry_revisions` write for non-noop mutations
- same-transaction success `admin_audit_events` write
- same-fingerprint no-op behavior
- best-effort failure audit
- CLI command:

```text
api2agent-controlplane import-replace-postgres \
  --registry <registry.json> \
  --postgres-dsn <dsn> \
  [--actor-id <actor>] \
  [--request-id <request-id>] \
  [--idempotency-key <key>]
```

## Preserved Boundaries

- `FileStore` remains default.
- Postgres write path is explicit opt-in.
- `seed-postgres` remains a dogfood helper, not the production mutation path.
- Registry tables still store credential metadata only, not secrets.
- Snapshot export/publish/reload remains separate from import/replace.
- No public write API was added.
- No CRUD, vault, billing, marketplace, or workflow scope was added.

## Tests Added

Added unit coverage for:

- same-fingerprint no-op writes success audit only
- changed registry replaces active rows and writes revision plus audit
- lock conflict returns `REGISTRY_MUTATION_CONFLICT`
- required success audit failure rolls back mutation
- serializable transaction options

## Validation

```text
go test ./...
```

Result:

```text
ok api2agent/services/control-plane/cmd/api2agent-controlplane
ok api2agent/services/control-plane/internal/httpapi
ok api2agent/services/control-plane/internal/registry
```

## Next Task

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

The live Postgres dogfood and readiness review are now complete. The next task should design the private admin endpoint without implementing it yet.
