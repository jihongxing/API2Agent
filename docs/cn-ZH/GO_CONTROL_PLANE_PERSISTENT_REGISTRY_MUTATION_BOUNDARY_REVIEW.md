# Go Control Plane Persistent Registry Mutation Boundary Review v0

日期：2026-05-31

状态：已完成

## 摘要

Persistent registry 现在已经完成 schema、load parity、runtime selection、live Postgres dogfood、persistent audit writes 和 failure semantics hardening。

这次 review 的目标是在增加任何 write API 之前，先确定 mutation boundary。

结论：

```text
现在不要增加 granular registry CRUD APIs。
下一步安全的写侧能力应该是 controlled full-registry import/replace transaction。
```

原因很简单：API2Agent 需要 durable registry writes，但 registry objects 之间高度耦合。单独更新 provider、credential metadata、routing policy 或 snapshot config，都可能产生 invalid 或不可解释的 routing snapshot。写入必须先把完整 registry view 校验通过，再原子性提交。

## 当前写入面

当前 persistent writes 仍然很窄：

- `seed-postgres` 把 file registry import 到 Postgres，用于 local dogfood。
- artifact export 写入 `registry_revisions`。
- distribution publish 写入 `snapshot_artifact_publications`。
- admin operations 写入 `admin_audit_events`。

当前没有 registry mutation API。

## Registry Object 分类

### Mutable Registry State

这些表定义了 `PostgresStore.Load(ctx)` 读取的 active registry view：

- `projects`
- `api_keys`
- `capabilities`
- `providers`
- `credential_metadata`
- `routing_policies`
- `snapshot_configs`

它们必须作为一个 validated registry graph 被修改，而不是作为互不相关的 rows 被修改。

### Append-Only Control Evidence

这些表是 evidence/audit surface，不应该被 registry mutation APIs 直接编辑：

- `registry_revisions`
- `snapshot_artifact_publications`
- `admin_audit_events`

它们应该作为 controlled operations 的结果被写入。

## Boundary 决策

### 下一步允许做

实现 controlled full-registry import/replace path。

推荐形态：

```text
input registry JSON
  -> parse
  -> canonicalize
  -> validate full Registry
  -> compute registry_fingerprint
  -> begin write transaction
  -> acquire registry mutation lock
  -> upsert/replace mutable registry tables
  -> write registry_revisions
  -> write admin_audit_events
  -> commit
```

这可以先作为 CLI/admin operation，而不是 public hosted API。

### 现在不允许做

暂不实现：

- individual registry objects 的 public CRUD endpoints
- provider onboarding APIs
- credential vault writes
- API key secret generation 或 plaintext storage
- marketplace provider submission
- billing 或 settlement state
- 绕过 full registry validation 的 partial mutation APIs

## Object-Level Mutation Rules

### `projects`

后续允许：

- create/update project metadata
- soft-disable project
- 仅允许把 `default_mode` 修改为合法 execution modes

暂不允许：

- hosted user/org ownership model
- hard delete

要求：

- project 变更不能 orphan active API keys 或 credential metadata。

### `api_keys`

后续允许：

- 使用 `key_hash` 创建 active key metadata
- revoke 或 disable keys
- 通过创建新 key row 并 revoke old row 完成 rotation

暂不允许：

- plaintext key storage
- hosted key issuance UX

要求：

- plaintext API keys 绝不能被返回，也不能存入 registry rows。

### `capabilities`

后续允许：

- 增加新的 capability version
- disable old version
- 更新 name/status metadata

暂不允许：

- destructive delete

要求：

- active providers 必须引用存在且 active 的 capability version。

### `providers`

后续允许：

- add/update provider metadata
- disable providers
- 通过 full validation 修改 region/cost/base URL metadata

暂不允许：

- public provider self-onboarding
- marketplace ranking edits

要求：

- active providers 必须具备有效 capability references、region metadata、mapping versions 和 `metadata.base_url`。

### `credential_metadata`

后续允许：

- add/update credential metadata references
- disable/expire metadata
- 更新 scope 和 rotation hints

暂不允许：

- secret value storage
- vault-backed secret writes
- OAuth delegated credential flows

要求：

- 这张表只存 metadata。Secret material 属于未来 vault boundary。

### `routing_policies`

后续允许：

- replace active global policy
- resolver semantics 存在后，再增加 project/capability scoped policies

暂不允许：

- hidden marketplace preference injection
- 没有显式 seed semantics 的 stochastic policy defaults

要求：

- 必须保持 exactly one active global policy。

### `snapshot_configs`

后续允许：

- registry import/replace 期间替换 active snapshot config

暂不允许：

- multi-active snapshot configs
- external snapshot distribution control

要求：

- 必须保持 exactly one active snapshot config。

## Transaction Requirements

未来写侧操作必须：

- 在单个 database transaction 内执行
- 获取 registry-wide mutation lock
- commit 前校验完整 registry view
- 在同一个 transaction 中写入 `registry_revisions`
- 在同一个 transaction 中写入 `admin_audit_events`
- 返回稳定、机器可读的 errors
- 避免 partial success states

推荐 lock：

```text
pg_advisory_xact_lock(...)
```

推荐 isolation：

```text
SERIALIZABLE for full import/replace
```

## Idempotency Requirements

Full import/replace 应该基于 registry fingerprint 实现 idempotency。

如果 incoming registry fingerprint 与当前 active registry fingerprint 一致，操作应该：

- 不无谓重写 mutable rows
- 返回 success
- 写入带 no-op marker 的 admin audit event

未来 HTTP mutation APIs 在实现前必须要求 idempotency key。

## Audit Requirements

每次 accepted mutation 必须产生：

- `registry_revisions`
- `admin_audit_events`

每次 rejected mutation 在 audit sink 可用时，应该 best-effort 写入 `admin_audit_events`。

Audit metadata 应包含：

- `registry_store`
- `registry_fingerprint`
- `previous_registry_fingerprint` when available
- `mutation_mode`
- `idempotency_key` when available
- affected object counts

## Failure Semantics

下一步实现建议使用这些稳定 errors：

| Condition | HTTP | error_type | scope | retryable |
| --- | ---: | --- | --- | --- |
| Invalid registry payload | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| Persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| Persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| Concurrent mutation conflict | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

## Rollback Requirements

如果 mutable registry writes 失败，transaction 必须回滚：

- mutable registry rows
- `registry_revisions`
- success `admin_audit_events`

Failure audit 只有在不遮盖原始 failure 时，才可以在 failed transaction 之外 best-effort 写入。

## 建议下一项任务

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```

这项任务应该设计一个单一、受控的写入路径：从经过验证的 registry document 替换 active persistent registry view。但它仍然不应该直接暴露 public API。

## 非目标

- 本次 review 未实现 mutation API。
- 未增加 schema migration。
- 未增加 hosted auth。
- 未增加 vault。
- 未增加 billing、settlement 或 marketplace 工作。
