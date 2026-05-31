# Go Control Plane Persistent Registry Import/Replace Live Postgres Dogfood v0

日期：2026-05-31

状态：passed

## 总结

已使用 podman 启动 live Postgres-compatible database，并 dogfood `api2agent-controlplane import-replace-postgres`。

这验证了 unit tests 之外的真实数据库路径：

```text
schema apply
  -> seed-postgres
  -> import-replace-postgres changed registry
  -> import-replace-postgres same registry no-op
  -> export-snapshot from Postgres
  -> audit count assertions
```

## 脚本

```text
scripts/go_control_plane_import_replace_postgres_dogfood.py
```

运行：

```text
python scripts/go_control_plane_import_replace_postgres_dogfood.py --output tmp/go_control_plane_import_replace_postgres_dogfood.json
```

## 结果

Dogfood 已通过。

关键观测值：

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

第一次 import 把原始 `ipify_public_ip_v1` provider 替换成了 `httpbin_public_ip_v1`。

第二次 import 使用同一份 registry document，并返回 `noop=true`。

从 Postgres 导出的 snapshot 反映了替换后的 active registry view：

```text
snapshot_import_replace_live_v1
httpbin_public_ip_v1
https://httpbin.org
```

## 证明了什么

- schema 可以支撑 controlled import/replace path。
- CLI 可以在 live Postgres 中替换 active mutable registry rows。
- same-fingerprint idempotency 在 live Postgres 中成立。
- non-noop replacement 会写入新的 `registry_revisions` row。
- replacement 和 no-op 都会写入 `admin_audit_events`。
- replacement 后的 snapshot export 会读取替换后的 registry view。
- file-store behavior 和 public service APIs 保持不变。

## 保持的非目标

- 不做 public registry CRUD API
- 不做 hosted mutation endpoint
- 不做 vault
- 不做 billing
- 不做 marketplace
- 不自动 snapshot publish 或 Data Plane reload

## 下一项任务

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

Closeout/readiness review 现在已经完成。下一步应该设计 private admin service endpoint，但暂不实现。
