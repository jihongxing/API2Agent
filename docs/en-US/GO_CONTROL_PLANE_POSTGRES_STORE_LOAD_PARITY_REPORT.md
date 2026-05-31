# Go Control Plane PostgresStore Load Parity v0 Report

Date: 2026-05-31

Status: complete

## Summary

This slice adds the first Postgres-backed registry read path behind the existing `registry.Store` interface.

It proves load parity at the registry/snapshot contract level without changing the default runtime store.

`FileStore` remains the default.

## Implemented

- Added `registry.PostgresStore`.
- Added `NewPostgresStore(db *sql.DB)`.
- Implemented `PostgresStore.Load(ctx)` using:
  - `REPEATABLE READ`
  - read-only transaction
  - existing `registry.Store` interface
- Added `LoadPersistentRows(ctx, q)` to read active persistent registry rows.
- Added `BuildRegistryFromPersistentRows(rows)` to rebuild the in-memory `Registry` shape used by `FileStore`.
- Added parsing helpers for Postgres text arrays and JSONB-like row values.
- Kept CLI and service runtime wiring on `FileStore`.

## Verified

- `PostgresStore.Load(ctx)` rejects a missing DB handle.
- `PostgresStore.Load(ctx)` begins a read-only `REPEATABLE READ` transaction.
- The existing `network.public_ip.get` file registry fixture maps to persistent rows.
- The persistent rows can rebuild an equivalent `Registry`.
- File-backed and Postgres-loaded registries produce equivalent snapshot contract output after canonicalization.
- `FileStore` remains the default runtime store.

## Non-Goals

This slice does not implement:

- runtime `--registry-store postgres` selection
- Postgres driver dependency or DSN parsing
- live Postgres dogfood
- migration runner
- registry seed/import command
- registry mutation HTTP APIs
- persisted artifact publication rows
- persisted admin audit events
- hosted deployment
- credential vault
- billing
- marketplace work

## Validation

```text
go test ./...
```

from `services/control-plane` passed.

## Next Recommended Step

The next engineering task should be:

```text
Go Control Plane Persistent Store Runtime Wiring v0
```

Recommended scope:

1. Add explicit store selection configuration while keeping `file` as default.
2. Decide and add the Postgres driver dependency.
3. Add DSN parsing and startup validation.
4. Add a seed/import path for the existing file registry fixture.
5. Dogfood the service against a real or locally provisioned Postgres-compatible database.

Do not add registry mutation APIs before read parity is dogfooded with runtime wiring.
