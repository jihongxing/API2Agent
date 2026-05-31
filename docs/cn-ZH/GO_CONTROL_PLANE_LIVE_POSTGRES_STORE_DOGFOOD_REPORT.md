# Go Control Plane Live Postgres Store Dogfood v0 报告

日期：2026-05-31

状态：已完成

## 总结

这次 dogfood 证明 Control Plane 可以通过 runtime `--registry-store postgres` 路径使用真实 Postgres-compatible store。

本次使用 `podman` 启动临时 Postgres 容器。

## 场景

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

## 结果

状态：通过

观察报告：

```text
.dogfood/go-control-plane-live-postgres/report.json
```

关键结果：

- `seed-postgres` 导入：
  - projects: 1
  - API keys: 1
  - capabilities: 1
  - providers: 1
  - credential metadata rows: 1
  - snapshot configs: 1
- file-store 和 postgres-store snapshots 完全一致
- registry fingerprint 一致：

```text
sha256:156af63d411ecc1d1a6b7773d409130203b3a5fad3c36f58e25e6393ad1981d9
```

- `/healthz` 返回：
  - `registry_store=postgres`
  - `registry_source=postgres`
  - `schema_version=api2agent.protocol.v0.2`
- `/v1/admin/registry/validate` 返回 `valid=true`
- `/v1/admin/snapshots/export-artifact` 成功导出 `snapshot_control_plane_public_ip_v1`

## 复现命令

```bash
python scripts/go_control_plane_live_postgres_store_dogfood.py \
  --output .dogfood/go-control-plane-live-postgres/report.json
```

脚本默认会启动并删除临时 `api2agent-pg-dogfood` podman 容器；传入 `--keep-container` 时会保留容器。

## 已验证

- 真实 Postgres-compatible schema application
- file registry import 到 persistent tables
- Postgres-backed registry load
- snapshot contract parity
- CLI artifact export through Postgres store
- service health with Postgres store
- service registry validation through Postgres store
- service artifact export through Postgres store

## 非目标

这次 dogfood 不实现：

- registry mutation APIs
- persisted artifact publication rows
- persisted admin audit events
- per-project hosted authorization
- remote artifact storage
- credential vault
- billing
- marketplace work

## 下一步建议

```text
Go Control Plane Persistent Export/Publish Audit Writes v0
```

原因：

read path 已经通过真实 Postgres-compatible database 验证。下一项 persistence 缺口是 export 和 publish operations 的 durable write-side audit：

- `registry_revisions`
- `snapshot_artifact_publications`
- `admin_audit_events`
