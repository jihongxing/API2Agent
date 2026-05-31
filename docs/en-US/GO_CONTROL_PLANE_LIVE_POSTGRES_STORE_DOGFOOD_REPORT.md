# Go Control Plane Live Postgres Store Dogfood v0 Report

Date: 2026-05-31

Status: complete

## Summary

This dogfood proves the Control Plane can use a real Postgres-compatible store through the runtime `--registry-store postgres` path.

It used `podman` to run a temporary Postgres container.

## Scenario

```text
podman postgres
  -> apply persistent registry schema
  -> seed-postgres from existing file registry
  -> export snapshot from file store
  -> export snapshot from postgres store
  -> compare snapshots
  -> export artifact from postgres store
  -> serve Control Plane with postgres store
  -> validate registry over HTTP
  -> export artifact over HTTP
```

## Result

Status: passed

Observed report:

```text
.dogfood/go-control-plane-live-postgres/report.json
```

Key results:

- `seed-postgres` imported:
  - projects: 1
  - API keys: 1
  - capabilities: 1
  - providers: 1
  - credential metadata rows: 1
  - snapshot configs: 1
- file-store and postgres-store snapshots were equal
- registry fingerprint matched:

```text
sha256:156af63d411ecc1d1a6b7773d409130203b3a5fad3c36f58e25e6393ad1981d9
```

- `/healthz` reported:
  - `registry_store=postgres`
  - `registry_source=postgres`
  - `schema_version=api2agent.protocol.v0.2`
- `/v1/admin/registry/validate` returned `valid=true`
- `/v1/admin/snapshots/export-artifact` exported `snapshot_control_plane_public_ip_v1`

## Repro Command

```bash
python scripts/go_control_plane_live_postgres_store_dogfood.py \
  --output .dogfood/go-control-plane-live-postgres/report.json
```

The script starts and removes a temporary `api2agent-pg-dogfood` podman container unless `--keep-container` is passed.

## Verified

- real Postgres-compatible schema application
- file registry import into persistent tables
- Postgres-backed registry load
- snapshot contract parity
- CLI artifact export through Postgres store
- service health with Postgres store
- service registry validation through Postgres store
- service artifact export through Postgres store

## Non-Goals

This dogfood does not implement:

- registry mutation APIs
- persisted artifact publication rows
- persisted admin audit events
- per-project hosted authorization
- remote artifact storage
- credential vault
- billing
- marketplace work

## Next Recommended Step

```text
Go Control Plane Persistent Export/Publish Audit Writes v0
```

Reason:

The read path is now proven against a live Postgres-compatible database. The next persistence gap is durable write-side audit for export and publish operations:

- `registry_revisions`
- `snapshot_artifact_publications`
- `admin_audit_events`
