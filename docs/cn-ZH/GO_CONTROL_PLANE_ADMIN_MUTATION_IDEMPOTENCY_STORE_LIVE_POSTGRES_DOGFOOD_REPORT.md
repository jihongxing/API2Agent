# Go Control Plane Admin Mutation Idempotency Store Live Postgres Dogfood Report v0

日期：2026-05-31

状态：complete

## Summary

Admin Mutation Idempotency Store implementation 的 live Postgres dogfood 已通过。

这次 dogfood 使用 podman-backed Postgres 和 private admin HTTP import/replace endpoint，在真实数据库上验证 durable idempotency behavior。

## Script

```text
scripts/go_control_plane_idempotency_store_dogfood.py
```

命令：

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

观测值：

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

已通过：

- first import/replace 返回 `201` 和 `noop=false`
- same key plus same request 返回 cached `201`
- replay response 和 first response 完全一致
- replay response 包含 `Idempotency-Replayed: true`
- replay response 包含 `Idempotency-Record-ID`
- same key plus different request 返回 `409 IDEMPOTENCY_KEY_CONFLICT`
- independent no-op import 返回 `200` 和 `noop=true`
- persistent idempotency records count 是 `2`
- replacement idempotency record 同时链接 registry revision 和 admin audit event
- no-op idempotency record 链接 admin audit event，且没有 registry revision
- replacement idempotency record 的 `replay_count=1`
- stored idempotency key hash 和 prefix 均为 hashed
- exported Postgres snapshot 使用 provider `httpbin_public_ip_v1`

## Validation

已通过：

```text
go test ./...
```

目录：

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Admin Mutation Idempotency Store Closeout + Phase Review v0
```

closeout 应判断这个 idempotency slice 是否足够，然后再进入下一个 hosted Control Plane readiness gap。
