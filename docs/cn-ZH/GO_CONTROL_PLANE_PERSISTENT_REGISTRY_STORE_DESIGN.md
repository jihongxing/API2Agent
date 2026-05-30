# Go Control Plane Persistent Registry Store Design v0

日期：2026-05-31

状态：已为下一项 implementation slice 冻结设计

判断：API2Agent 应该在现有 `registry.Store` 边界后面引入 persistent registry store，同时保持当前 Data Plane snapshot contract 不变。

## 1. 目标

把 Control Plane state 从 local file registry 推进到 durable database-backed registry，但不改变：

- routing snapshot shape
- artifact manifest semantics
- distribution pointer semantics
- Data Plane snapshot loading behavior
- registry validation rules
- registry fingerprint audit field

Database 会成为 Control Plane source of truth。Exported snapshot 仍然是 Data Plane contract。

## 2. 非目标

这个设计不实现：

- hosted deployment
- public signup 或 user management
- secret vault storage
- provider billing
- marketplace
- remote object storage
- distributed publish locks
- registry mutation HTTP APIs

## 3. 当前边界

当前 Go interface：

```go
type Store interface {
    Load(ctx context.Context) (*Registry, error)
}
```

当前实现：

```text
registry.FileStore
```

设计规则：

```text
Persistent store v0 must implement Load(ctx) without changing snapshot export callers.
```

未来 mutation APIs 应该使用独立 writer interface，不应该塞进当前 read-only `Store` contract。

## 4. Persistent Store Contract

`PostgresStore.Load(ctx)` 必须：

1. 打开 read-only transaction。
2. 读取一个一致的 active registry view。
3. 构造与 `FileStore` 相同的 in-memory `registry.Registry` object。
4. 在构造 arrays 前按确定性顺序排序 rows。
5. 执行 `Registry.Validate()`。
6. 把 registry 返回给现有 exporter。

Exporter 不应该知道 registry 来自 file 还是 Postgres。

## 5. 第一版 Postgres Table Model

这是 logical model，还不是 migration file。

### 5.1 `projects`

存储 project identity metadata。

Required fields：

- `id`
- `name`
- `status`
- `default_mode`
- `created_at`
- `updated_at`

Constraints：

- `id` primary key
- `status in ('active', 'disabled')`
- `default_mode in ('direct', 'proxy', 'shadow', 'replay')` when present

### 5.2 `api_keys`

存储 API2Agent project key metadata。

Required fields：

- `id`
- `project_id`
- `key_prefix`
- `key_hash`
- `status`
- `created_at`
- `updated_at`

Constraints：

- `id` primary key
- `project_id` references `projects(id)`
- `status in ('active', 'disabled', 'revoked')`
- raw API keys 绝不能存储

虽然当前 local registry 只携带 `key_prefix`，persistent model 仍然需要 `key_hash`。Hosted API key verification 不能只依赖 prefix。

### 5.3 `capabilities`

存储 canonical capability definitions。

Required fields：

- `id`
- `version`
- `name`
- `status`
- `created_at`
- `updated_at`

Constraints：

- primary key: `(id, version)`
- `status in ('active', 'disabled')`

Snapshot v0 只导出 active capabilities。

### 5.4 `providers`

存储 capability 的 provider candidates。

Required fields：

- `id`
- `capability_id`
- `capability_version`
- `provider_id`
- `provider_version`
- `mapping_version`
- `tool_id`
- `regions`
- `geo_affinity`
- `estimated_cost`
- `metadata`
- `status`
- `created_at`
- `updated_at`

Constraints：

- `id` primary key
- `(capability_id, capability_version)` references `capabilities(id, version)`
- `regions` must be non-empty
- active providers must include `metadata.base_url`
- `status in ('active', 'disabled')`

`metadata` 建议存储为 JSONB，且不能包含 provider secrets。

### 5.5 `credential_metadata`

只存储 credential ownership 和 policy metadata。

Required fields：

- `credential_id`
- `credential_version`
- `owner_type`
- `owner_id`
- `provider_id`
- `auth_type`
- `injection_mode`
- `source`
- `scope`
- `status`
- `rotation_hint`
- `created_at`
- `updated_at`

Constraints：

- `credential_id` primary key
- `provider_id` references provider logical ids
- `owner_type in ('user', 'project', 'platform', 'provider')`
- `auth_type in ('api_key', 'bearer', 'basic', 'oauth', 'none')`
- `injection_mode in ('header', 'query', 'body', 'none')`
- `source in ('env', 'config', 'inline', 'vault', 'none')`
- `status in ('active', 'disabled', 'expired')`
- 不存储 raw secret values

Secret values 属于未来 vault，不属于这张表。

### 5.6 `routing_policies`

存储 routing policy configuration。

Required fields：

- `id`
- `scope_type`
- `scope_id`
- `strategy`
- `routing_mode`
- `routing_seed`
- `failover_policy`
- `status`
- `created_at`
- `updated_at`

Constraints：

- `scope_type in ('global', 'project', 'capability')`
- `strategy in ('first', 'lowest_cost', 'lowest_latency', 'region_aware_latency', 'highest_success_rate', 'balanced')`
- `routing_mode in ('deterministic', 'stochastic')`
- v0 只允许一个 active global policy

`failover_policy` 建议使用 JSONB，以保留现有 snapshot structure。

### 5.7 `snapshot_configs`

存储 snapshot export settings。

Required fields：

- `id`
- `version`
- `fetched_at`
- `ttl`
- `source`
- `status`
- `created_at`
- `updated_at`

Constraints：

- v0 只允许一个 active config
- `source in ('push', 'pull')`
- `ttl` 必须能被 Go duration 解析

### 5.8 `registry_revisions`

记录 immutable registry export revisions。

Required fields：

- `id`
- `registry_fingerprint`
- `snapshot_version`
- `source_store`
- `source_revision`
- `created_by`
- `created_at`

用途：

- 审计哪个 registry state 产生了 snapshot artifact
- 支持 replay 或比较旧 export
- 把 mutable registry tables 与 immutable snapshot history 解耦

### 5.9 `snapshot_artifact_publications`

记录 artifact 和 distribution publication metadata。

Required fields：

- `id`
- `snapshot_version`
- `registry_fingerprint`
- `snapshot_digest`
- `artifact_uri`
- `manifest_uri`
- `distribution_uri`
- `published_by`
- `published_at`
- `status`

Constraints：

- unique active `snapshot_version`
- `status in ('pending', 'published', 'failed', 'replaced')`

local v0 中 URI 可以是 file paths。Hosted storage 后续可以迁移到 object storage URIs。

### 5.10 `admin_audit_events`

记录 Control Plane administrative actions。

Required fields：

- `id`
- `actor_id`
- `action`
- `resource_type`
- `resource_id`
- `request_id`
- `outcome`
- `error_type`
- `metadata`
- `created_at`

Actions 应包含：

- `registry.validate`
- `snapshot.export_artifact`
- `distribution.publish`
- `distribution.current.read`

这是 hosted readiness 的设计要求。当前 local service 尚未实现。

## 6. Transaction Boundaries

### 6.1 Registry Load

使用一个 read-only transaction。

Isolation target：

```text
REPEATABLE READ
```

规则：

- 读取 active snapshot config
- 读取 active projects、API keys、capabilities、providers、credential metadata 和 routing policy
- 每个 collection 都按确定性顺序排序
- 构造 `registry.Registry`
- 返回前执行 validate

### 6.2 Artifact Export

使用一个一致的 registry read transaction 构造 registry 并计算 fingerprint。

然后：

1. 使用现有代码 export snapshot 和 manifest。
2. 写入 artifact files 或未来 object storage objects。
3. 记录 `registry_revisions` row。
4. 记录 `admin_audit_events` row。

即使 registry tables 在 export 后立刻变化，已经导出的 snapshot 也必须保持有效。

### 6.3 Distribution Publish

对于 local filesystem v0：

1. Validate artifact content。
2. 使用现有 atomic local publisher publish。
3. 插入 `snapshot_artifact_publications`，`status='published'`。
4. 插入 `admin_audit_events`。

对于未来 remote storage：

1. 插入 publication row，状态为 `pending`。
2. 写入 artifact objects。
3. Compare-and-swap distribution pointer。
4. 标记 publication 为 `published` 或 `failed`。

不要把 remote storage transaction 设计成 database 可以原子控制 object storage。

## 7. Fingerprint and Versioning Rules

Database-backed fingerprints 必须是 deterministic。

规则：

- fingerprint input 是 canonical `registry.Registry` JSON
- internal database IDs 排除在外
- `created_at` 和 `updated_at` 等 timestamps 排除在外
- collections 按 stable logical keys 排序
- empty optional fields 遵循当前 Go models 的 JSON 行为
- output prefix 仍然是 `sha256:`

推荐 sort keys：

- projects: `id`
- API keys: `id`
- capabilities: `id`, then `version`
- providers: `id`
- credential metadata: `credential_id`
- routing policy: active global policy first

Snapshot version policy 在 v0 仍然是 explicit。

## 8. Migration and Dual-Store Strategy

### Step 1: File Import Design

加载现有 `registry.json`，validate 后映射到 database model。

### Step 2: Dual Export

对于相同 logical registry state：

```text
FileStore.ExportSnapshot()
PostgresStore.ExportSnapshot()
```

必须生成等价 snapshots。

允许不同：

- `registry_store`
- `registry_source`
- export timestamps

不允许不同：

- capabilities
- providers
- routing policy
- snapshot metadata
- canonicalization 后的 registry fingerprint

### Step 3: Service Store Selection

未来 service startup 应支持：

```text
--registry-store file|postgres
```

在 Postgres dogfood 通过前，File store 仍然是默认 runtime store。

## 9. Implementation Sequence After This Design

这个设计之后建议的下一项 implementation：

```text
Go Control Plane Persistent Registry Store Schema v0
```

范围：

1. 添加 SQL schema 或 migration draft。
2. 添加测试 fixture，把现有 file registry import 到 schema。
3. 添加 canonical registry export 的 deterministic ordering tests。
4. 保持 `FileStore` 作为默认 runtime store。

在 load/export parity 被证明前，不要实现 registry mutation APIs。

## 10. Acceptance Criteria

Persistent Registry Store Design v0 完成条件：

- table model 明确
- transaction boundaries 明确
- fingerprint rules 明确
- migration and dual-store strategy 明确
- 下一项 implementation scope 收窄到 schema/load parity
- Data Plane snapshot contract 保持不变

## 11. Strategic Judgment

Persistent store 本身不是产品。

它的作用是让 API2Agent 可以管理真实 Control Plane state，同时保持 Data Plane contract 稳定：

```text
Control Plane state can change.
Snapshot contract must stay stable.
```

这个分离是下一阶段最重要的基础设施纪律。
