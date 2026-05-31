# Go Control Plane Persistent Store Runtime Wiring v0 报告

日期：2026-05-31

状态：已完成；live Postgres dogfood 已在独立报告中完成

## 总结

这一项任务把 persistent store 接入 local runtime configuration，同时保持 `FileStore` 为默认值。

当前代码可以显式选择 `file` 或 `postgres` 作为 read-side registry loading 来源。

## 已实现

- 通过 `github.com/jackc/pgx/v5/stdlib` 增加 `pgx` Postgres driver dependency。
- 为以下命令增加 `--registry-store file|postgres`：
  - `export-snapshot`
  - `export-artifact`
  - `serve`
- 增加 `--postgres-dsn` 和 `API2AGENT_CONTROL_PLANE_POSTGRES_DSN`。
- 增加 `API2AGENT_CONTROL_PLANE_REGISTRY_STORE`，用于默认 store selection。
- 增加缺失 file registry path 和缺失/无效 Postgres DSN 的 startup validation。
- 新增 `seed-postgres --registry <registry.json> --postgres-dsn <dsn>`。
- 新增 `SeedPostgresRegistry(ctx, db, reg)`，把当前 file registry model import 到 persistent schema。
- 更新 Control Plane README，说明 Postgres store 用法。

## 已验证

- File store 仍然是默认 runtime path。
- 选择 `file` 时，缺失 `--registry` 会失败。
- 选择 `postgres` 时，缺失 `--postgres-dsn` 会失败。
- 未知 store name 会失败。
- Control Plane Go tests 通过。
- Data Plane Go tests 通过。
- Python reference tests 通过。

## Live Dogfood 状态

Live Postgres dogfood 已通过 podman 完成。

详见：

```text
docs/cn-ZH/GO_CONTROL_PLANE_LIVE_POSTGRES_STORE_DOGFOOD_REPORT.md
```

之前的环境检查显示 Docker 和 host `psql` 不可用，但 `podman` 可用，且足以完成 live dogfood。

## 非目标

这一项任务不实现：

- registry mutation APIs
- hosted public deployment
- remote artifact storage
- persisted artifact publication writes
- persisted admin audit events
- credential vault
- billing
- marketplace work

## 下一步建议

```text
Go Control Plane Persistent Export/Publish Audit Writes v0
```
