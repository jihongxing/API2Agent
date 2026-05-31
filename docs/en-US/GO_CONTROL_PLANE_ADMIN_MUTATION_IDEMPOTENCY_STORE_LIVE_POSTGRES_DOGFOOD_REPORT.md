# Go Control Plane Admin Mutation Idempotency Store Live Postgres Dogfood Report v0

Date: 2026-05-31

Status: complete

## Summary

Live Postgres dogfood passed for the Admin Mutation Idempotency Store implementation.

The dogfood used podman-backed Postgres and the private admin HTTP import/replace endpoint to verify durable idempotency behavior against a real database.

## Script

```text
scripts/go_control_plane_idempotency_store_dogfood.py
```

Command:

```text
python scripts/go_control_plane_idempotency_store_dogfood.py --output tmp/go_control_plane_idempotency_store_dogfood.json
```

## Flow

```text
podman Postgres
  -> apply persistent registry schema
  -> seed-postgres from file registry
  -> start Control Plane service with --registry-store postgres
  -> HTTP import/replace with idempotency key A
  -> HTTP replay with same idempotency key A and same request
  -> HTTP conflict with same idempotency key A and different request
  -> HTTP no-op import with idempotency key B
  -> export snapshot from Postgres store
  -> query persistent evidence tables
```

## Results

Observed:

```json
{
  "status": "passed",
  "first_status": 201,
  "replay_status": 201,
  "conflict_status": 409,
  "noop_status": 200,
  "replay_headers": {
    "Idempotency-Replayed": "true",
    "Idempotency-Record-ID": "1"
  },
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 2,
    "idempotency_records": 2,
    "providers": 1
  },
  "snapshot_version": "snapshot_idempotency_store_live_v1",
  "provider_id": "httpbin_public_ip_v1"
}
```

## Assertions

Passed:

- first import/replace returned `201` and `noop=false`
- same key plus same request returned cached `201`
- replay response matched the first response
- replay response included `Idempotency-Replayed: true`
- replay response included `Idempotency-Record-ID`
- same key plus different request returned `409 IDEMPOTENCY_KEY_CONFLICT`
- independent no-op import returned `200` and `noop=true`
- persistent idempotency records count was `2`
- replacement idempotency record linked to both registry revision and admin audit event
- no-op idempotency record linked to admin audit event and no registry revision
- replacement idempotency record had `replay_count=1`
- stored idempotency key hash and prefix were hashed
- exported Postgres snapshot used provider `httpbin_public_ip_v1`

## Validation

Passed:

```text
go test ./...
```

Directory:

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Admin Mutation Idempotency Store Closeout + Phase Review v0
```

The closeout should decide whether this idempotency slice is sufficient before moving to the next hosted Control Plane readiness gap.
