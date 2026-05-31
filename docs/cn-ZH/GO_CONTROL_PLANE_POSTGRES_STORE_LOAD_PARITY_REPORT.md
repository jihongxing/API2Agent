# Go Control Plane PostgresStore Load Parity v0 报告

日期：2026-05-31

状态：已完成

## 总结

这一项任务在现有 `registry.Store` interface 后面增加了第一条 Postgres-backed registry read path。

它证明的是 registry/snapshot contract 层面的 load parity，不改变默认 runtime store。

`FileStore` 仍然是默认 store。

## 已实现

- 新增 `registry.PostgresStore`。
- 新增 `NewPostgresStore(db *sql.DB)`。
- 实现 `PostgresStore.Load(ctx)`，使用：
  - `REPEATABLE READ`
  - read-only transaction
  - 现有 `registry.Store` interface
- 新增 `LoadPersistentRows(ctx, q)`，读取 active persistent registry rows。
- 新增 `BuildRegistryFromPersistentRows(rows)`，重建与 `FileStore` 相同的 in-memory `Registry` shape。
- 新增 Postgres text arrays 和 JSONB-like row values 的解析 helpers。
- CLI 和 service runtime wiring 仍然保持在 `FileStore`。

## 已验证

- `PostgresStore.Load(ctx)` 会拒绝缺失的 DB handle。
- `PostgresStore.Load(ctx)` 会开启 read-only `REPEATABLE READ` transaction。
- 现有 `network.public_ip.get` file registry fixture 可以映射为 persistent rows。
- Persistent rows 可以重建等价 `Registry`。
- File-backed 和 Postgres-loaded registries 在 canonicalization 后可以生成等价 snapshot contract output。
- `FileStore` 仍然是默认 runtime store。

## 非目标

这一项任务不实现：

- runtime `--registry-store postgres` selection
- Postgres driver dependency 或 DSN parsing
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

## 验证

```text
go test ./...
```

在 `services/control-plane` 下已通过。

## 下一步建议

下一项工程任务应该是：

```text
Go Control Plane Persistent Store Runtime Wiring v0
```

建议范围：

1. 增加显式 store selection configuration，同时保持 `file` 为默认值。
2. 决定并加入 Postgres driver dependency。
3. 增加 DSN parsing 和 startup validation。
4. 为现有 file registry fixture 增加 seed/import path。
5. 用真实或本地 provisioned 的 Postgres-compatible database 完成 service dogfood。

在 runtime read parity 完成 dogfood 前，不要添加 registry mutation APIs。
