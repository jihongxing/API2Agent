# Go Control Plane Persistent Registry Import/Replace Live Postgres Dogfood v0

Date: 2026-05-31

Status: passed

## Summary

Dogfooded `api2agent-controlplane import-replace-postgres` against a live Postgres-compatible database started with podman.

This validates the CLI beyond unit tests:

```text
schema apply
  -> seed-postgres
  -> import-replace-postgres changed registry
  -> import-replace-postgres same registry no-op
  -> export-snapshot from Postgres
  -> audit count assertions
```

## Script

```text
scripts/go_control_plane_import_replace_postgres_dogfood.py
```

Run:

```text
python scripts/go_control_plane_import_replace_postgres_dogfood.py --output tmp/go_control_plane_import_replace_postgres_dogfood.json
```

## Result

The dogfood passed.

Observed values:

```json
{
  "replace_noop": "false",
  "second_noop": "true",
  "snapshot_version": "snapshot_import_replace_live_v1",
  "provider_id": "httpbin_public_ip_v1",
  "provider_base_url": "https://httpbin.org",
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 2,
    "providers": 1
  }
}
```

The first import replaced the original `ipify_public_ip_v1` provider with `httpbin_public_ip_v1`.

The second import used the same registry document and returned `noop=true`.

The exported Postgres snapshot reflected the replaced active registry view:

```text
snapshot_import_replace_live_v1
httpbin_public_ip_v1
https://httpbin.org
```

## What This Proves

- The schema can support the controlled import/replace path.
- The CLI can replace active mutable registry rows in live Postgres.
- Same-fingerprint idempotency works against live Postgres.
- Non-noop replacement writes a new `registry_revisions` row.
- Replacement and no-op both write `admin_audit_events`.
- Snapshot export after replacement reads the replaced registry view.
- File-store behavior and public service APIs remain unchanged.

## Non-Goals Preserved

- no public registry CRUD API
- no hosted mutation endpoint
- no vault
- no billing
- no marketplace
- no automatic snapshot publish or Data Plane reload

## Next Task

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

The closeout/readiness review is now complete. The next step should design the private admin service endpoint, without implementing it yet.
