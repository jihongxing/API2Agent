# Go Control Plane Persistent Store Runtime Wiring v0 Report

Date: 2026-05-31

Status: complete; live Postgres dogfood completed separately

## Summary

This slice wires the persistent store into local runtime configuration while keeping `FileStore` as the default.

The code can now explicitly select `file` or `postgres` for read-side registry loading.

## Implemented

- Added the `pgx` Postgres driver dependency through `github.com/jackc/pgx/v5/stdlib`.
- Added `--registry-store file|postgres` to:
  - `export-snapshot`
  - `export-artifact`
  - `serve`
- Added `--postgres-dsn` and `API2AGENT_CONTROL_PLANE_POSTGRES_DSN`.
- Added `API2AGENT_CONTROL_PLANE_REGISTRY_STORE` for default store selection.
- Added startup validation for missing file registry path and missing/invalid Postgres DSN.
- Added `seed-postgres --registry <registry.json> --postgres-dsn <dsn>`.
- Added `SeedPostgresRegistry(ctx, db, reg)` to import the current file registry model into the persistent schema.
- Updated Control Plane README with explicit Postgres store usage.

## Verified

- File store remains the default runtime path.
- Store selection rejects missing `--registry` for `file`.
- Store selection rejects missing `--postgres-dsn` for `postgres`.
- Store selection rejects unknown store names.
- Control Plane Go tests pass.
- Data Plane Go tests pass.
- Python reference tests pass.

## Live Dogfood Status

Live Postgres dogfood has now passed with podman.

See:

```text
docs/en-US/GO_CONTROL_PLANE_LIVE_POSTGRES_STORE_DOGFOOD_REPORT.md
```

Earlier environment checks showed Docker and host `psql` were unavailable, but `podman` was available and sufficient for live dogfood.

## Non-Goals

This slice does not implement:

- registry mutation APIs
- hosted public deployment
- remote artifact storage
- persisted artifact publication writes
- persisted admin audit events
- credential vault
- billing
- marketplace work

## Next Recommended Step

```text
Go Control Plane Persistent Export/Publish Audit Writes v0
```
