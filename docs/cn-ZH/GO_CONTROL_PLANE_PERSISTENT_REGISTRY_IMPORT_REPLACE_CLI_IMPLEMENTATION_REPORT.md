# Go Control Plane Persistent Registry Import/Replace CLI Implementation v0

日期：2026-05-31

状态：complete

## 总结

已实现第一个受控的 persistent registry write-side path：

```text
api2agent-controlplane import-replace-postgres
```

这是 local/admin CLI operation。没有加入 public CRUD endpoints，也没有加入 hosted mutation API。

## 已实现

- `registry.ReplacePersistentRegistry(ctx, db, reg, opts)`
- `ImportReplaceOptions`、`ImportReplaceResult` 和 `ImportReplaceCounts`
- structured `RegistryMutationError`
- serializable write transaction
- transaction-scoped advisory lock：

```sql
SELECT pg_try_advisory_xact_lock(22021, 1)
```

- full mutable registry table replacement
- non-noop mutation 在同一 transaction 内写入 `registry_revisions`
- 在同一 transaction 内写入 success `admin_audit_events`
- same-fingerprint no-op behavior
- best-effort failure audit
- CLI command：

```text
api2agent-controlplane import-replace-postgres \
  --registry <registry.json> \
  --postgres-dsn <dsn> \
  [--actor-id <actor>] \
  [--request-id <request-id>] \
  [--idempotency-key <key>]
```

## 保持的边界

- `FileStore` 仍然是默认值。
- Postgres write path 必须显式 opt-in。
- `seed-postgres` 仍然是 dogfood helper，不是 production mutation path。
- Registry tables 仍然只存 credential metadata，不存 secrets。
- Snapshot export/publish/reload 仍然与 import/replace 分离。
- 没有加入 public write API。
- 没有加入 CRUD、vault、billing、marketplace 或 workflow scope。

## 新增测试

新增 unit coverage：

- same-fingerprint no-op 只写 success audit
- changed registry 会替换 active rows，并写入 revision plus audit
- lock conflict 返回 `REGISTRY_MUTATION_CONFLICT`
- required success audit failure 会 rollback mutation
- serializable transaction options

## 验证

```text
go test ./...
```

结果：

```text
ok api2agent/services/control-plane/cmd/api2agent-controlplane
ok api2agent/services/control-plane/internal/httpapi
ok api2agent/services/control-plane/internal/registry
```

## 下一项任务

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

Live Postgres dogfood 和 readiness review 现在都已经完成。下一项任务应该设计 private admin endpoint，但暂不实现。
