# Go Control Plane Persistent Registry Import/Replace Transaction Design v0

日期：2026-05-31

状态：complete

## 决策

第一个 persistent registry write-side operation 应该是受控的 full-registry import/replace transaction。

它不应该是 public CRUD API。

推荐下一项 implementation task：

```text
Go Control Plane Persistent Registry Import/Replace CLI Implementation v0
```

implementation 应该先提供一个很窄的 local/admin operation：从已验证的 registry document 替换 active persistent registry view，写入必要 audit evidence，并继续把 snapshot export/publish 保持为独立操作。

## 范围

本设计覆盖：

- transaction boundary
- validation 和 canonicalization order
- idempotency semantics
- registry-wide mutation lock
- mutable table replacement strategy
- required audit writes
- rollback behavior
- stable error taxonomy
- expected implementation seam

本设计不实现该 operation。

## 当前代码事实

当前仓库已经有：

- `registry.Store` 作为 Control Plane state boundary。
- `FileStore` 作为默认 runtime store。
- `PostgresStore.Load(ctx)` 作为 read-only `REPEATABLE READ` persistent load path。
- `MapRegistryToPersistentRows(reg)` 用于 file registry 到 persistent rows 的映射。
- `BuildRegistryFromPersistentRows(rows)` 用于 persistent rows 到 registry 的重建。
- `CanonicalRegistry(reg)` 和 `Registry.Fingerprint()`。
- `SeedPostgresRegistry(ctx, db, reg)` 作为 local dogfood import helper。
- persistent audit tables：`registry_revisions`、`snapshot_artifact_publications`、`admin_audit_events`。

重要区别：

`seed-postgres` 不是 production mutation path。它是 upsert-based local dogfood helper，不具备这里要求的 full import/replace transaction semantics。

## Operation Contract

建议的 internal API：

```go
type ImportReplaceOptions struct {
    ActorID        string
    RequestID      string
    IdempotencyKey string
    Source         string
}

type ImportReplaceResult struct {
    RegistryFingerprint         string
    PreviousRegistryFingerprint string
    SnapshotVersion             string
    Noop                        bool
    Counts                      ImportReplaceCounts
}

func ReplacePersistentRegistry(ctx context.Context, db *sql.DB, reg Registry, opts ImportReplaceOptions) (ImportReplaceResult, error)
```

建议的 CLI shape：

```text
api2agent-controlplane import-replace-postgres \
  --registry <registry.json> \
  --postgres-dsn <dsn> \
  --actor-id <actor> \
  --request-id <request-id> \
  [--idempotency-key <key>]
```

该命令只应该是 local/admin operation。不要暴露 hosted public mutation API。

## 执行顺序

### 1. 在 transaction 外解析输入

在打开 write transaction 前读取并 decode registry document。

失败返回：

```text
REGISTRY_MUTATION_INVALID
```

不触碰 mutable rows。

### 2. 在 transaction 外 canonicalize 并 validate

执行：

```go
canonical := CanonicalRegistry(reg)
err := canonical.Validate()
fingerprint := canonical.Fingerprint()
rows := MapRegistryToPersistentRows(canonical)
```

规则：

- canonicalization 不能修改 input registry
- fingerprint 必须基于 canonical validated registry 计算
- row mapping 不能发明 secret material
- credential rows 仍然只存 metadata
- 当前 file-shaped `APIKey` input 不能提供 `key_hash`；implementation 不能自行发明

### 3. 开启 Serializable Write Transaction

使用：

```go
db.BeginTx(ctx, &sql.TxOptions{
    Isolation: sql.LevelSerializable,
    ReadOnly:  false,
})
```

原因：

该 operation 会替换一个耦合的 registry graph，不能与另一个 mutation 交错执行。

### 4. 获取 Registry-Wide Mutation Lock

使用 transaction-scoped advisory lock。

推荐 lock：

```sql
SELECT pg_try_advisory_xact_lock(22021, 1)
```

语义：

- `true`：继续
- `false`：rollback，并返回 `REGISTRY_MUTATION_CONFLICT`

理由：

该 lock 明确、跟随 transaction 生命周期，并避免并发 registry replacement 的 partial state。

### 5. 在同一个 transaction 中读取当前 active registry

调用：

```go
LoadPersistentRows(ctx, tx)
BuildRegistryFromPersistentRows(rows)
current.Fingerprint()
```

如果 persistent store 为空，`previous_registry_fingerprint` 为空并继续。

如果 active rows 存在但无法重建，返回：

```text
PERSISTENT_STORE_READ_FAILED
```

### 6. Idempotent No-Op Check

如果：

```text
incoming_fingerprint == previous_registry_fingerprint
```

则：

- 不重写 mutable registry tables
- 写入一条 `admin_audit_events`，`outcome=success`
- 包含 `mutation_mode=import_replace_noop`
- 包含 `registry_fingerprint`、`previous_registry_fingerprint`、`idempotency_key` 和 object counts
- commit

no-op 不写重复的 `registry_revisions` row。

### 7. 替换 Mutable Registry Tables

mutable registry state 包括：

- `projects`
- `api_keys`
- `capabilities`
- `providers`
- `credential_metadata`
- `routing_policies`
- `snapshot_configs`

v0 推荐 replacement strategy：

1. 按 dependency-safe order 删除现有 mutable rows
2. 按 dependency-safe order 插入 canonical incoming rows
3. 不触碰 append-only evidence tables

删除顺序：

```text
providers
credential_metadata
api_keys
routing_policies
snapshot_configs
capabilities
projects
```

插入顺序：

```text
projects
api_keys
capabilities
providers
credential_metadata
routing_policies
snapshot_configs
```

为什么 delete/insert 优先于 row-by-row upsert：

- 这是 full-registry replacement，不是 partial CRUD
- 缺失的对象必须从 active registry view 中消失
- deterministic replacement 更容易 audit 和解释
- append-only revision tables 已经保留 evidence

后续 implementation 可以优化成 staged upsert plus disabled status，但 v0 应该优先正确性和可解释性。

### 8. Commit 前重建并验证 Written Registry

仍在同一个 transaction 中执行：

```go
writtenRows := LoadPersistentRows(ctx, tx)
writtenRegistry := BuildRegistryFromPersistentRows(writtenRows)
writtenFingerprint := writtenRegistry.Fingerprint()
```

要求：

```text
writtenFingerprint == incoming_fingerprint
```

如果不匹配，rollback 并返回：

```text
REGISTRY_MUTATION_INVALID
```

这可以防止 registry document 和 persistent rows 之间出现 silent drift。

### 9. 在同一个 transaction 中写入 Required Audit Evidence

对 accepted non-noop mutation，写入：

`registry_revisions`：

- `registry_fingerprint`
- `snapshot_version`
- `source_store=postgres`
- `source_revision=<request_id or idempotency_key>`
- `created_by=<actor_id>` when available

`admin_audit_events`：

- `action=registry.import_replace`
- `resource_type=registry`
- `resource_id=<registry_fingerprint>`
- `request_id=<request_id>`
- `actor_id=<actor_id>`
- `outcome=success`
- `metadata` 包含：
  - `mutation_mode=import_replace`
  - `registry_store=postgres`
  - `registry_fingerprint`
  - `previous_registry_fingerprint`
  - `snapshot_version`
  - `idempotency_key`
  - affected object counts

任一 required audit write 失败，operation 必须 fail closed。

### 10. Commit

只有 mutable rows、revision evidence 和 success audit 全部写入后才 commit。

## Failure Audit

rejected mutations 应该在 database connection 可用时尝试 best-effort failure audit。

failure audit 规则：

- 不遮蔽原始错误
- 不把 invalid input 变成 success
- 不在已经要 rollback 的 transaction 内写 failure audit
- 包含 `error_type`、`request_id`、`actor_id`、`idempotency_key` 和任何可用 fingerprint metadata

## Error Taxonomy

| Condition | HTTP | error_type | scope | retryable |
| --- | ---: | --- | --- | --- |
| Invalid registry payload or graph | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| Persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| Persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| Concurrent mutation lock unavailable | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Serializable transaction conflict | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

第一版 CLI implementation 可以先用 structured Go errors 表达，并输出 deterministic CLI error。HTTP mapping 留给后续 admin service endpoint。

## Rollback Semantics

transaction 必须一起 rollback：

- mutable table deletes
- mutable table inserts
- `registry_revisions` writes
- success `admin_audit_events` writes

不允许 partial success。

failure audit 可以在 rollback 后 best effort 写入。

## Snapshot Boundary

Import/replace 不 publish 或 reload snapshots。

顺序仍然是：

```text
import/replace persistent registry
  -> export artifact
  -> publish distribution
  -> Data Plane reload
```

这保持现有 Control Plane/Data Plane handoff。Data Plane 仍然消费 versioned snapshots，不直接读取 mutable Control Plane tables。

## Implementation Notes

推荐新增文件：

- `services/control-plane/internal/registry/postgres_import_replace.go`
- `services/control-plane/internal/registry/postgres_import_replace_test.go`

推荐命令：

- `import-replace-postgres`

推荐测试：

- invalid registry fails before mutation
- same fingerprint returns no-op and writes success audit only
- changed registry replaces active rows and writes revision plus audit
- removed provider disappears from active load output
- rollback on provider insert failure preserves previous registry
- lock conflict returns `REGISTRY_MUTATION_CONFLICT`
- required success audit failure rolls back the mutation
- file store behavior remains unchanged

## 非目标

- 不做 public CRUD endpoints
- 不做 hosted provider onboarding
- 不做 credential vault writes
- 不存 plaintext API key
- 不做 marketplace provider submission
- 不做 billing 或 settlement
- Data Plane 不直接读取 Control Plane tables
- 不自动 snapshot publish 或 reload

