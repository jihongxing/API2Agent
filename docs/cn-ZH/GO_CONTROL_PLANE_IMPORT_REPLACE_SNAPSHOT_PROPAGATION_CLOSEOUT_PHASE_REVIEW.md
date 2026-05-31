# Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0

日期：2026-05-31

状态：complete

## 决策

import/replace snapshot propagation milestone 可以关闭。

项目现在已经证明了本地 Control Plane write-side path，以及进入 Data Plane execution 的手动 snapshot handoff：

```text
private admin HTTP import/replace
  -> persistent Postgres registry replacement
  -> snapshot artifact export
  -> distribution publish
  -> manual Data Plane reload
  -> Data Plane execution with replaced provider
```

推荐下一项任务：

```text
Go Control Plane Admin Mutation Idempotency Store Design v0
```

这应该先做 design，再进入 implementation。当前 endpoint 已要求 `Idempotency-Key`，但还没有持久化 request/result idempotency records。

## 现在已经完成了什么

### Persistent Registry Write Path

已完成：

- controlled full-registry import/replace transaction
- serializable transaction boundary
- transaction-scoped advisory lock
- same-fingerprint no-op handling
- same-transaction revision and audit evidence
- required audit failure 时 rollback
- local/admin CLI mutation path

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_TRANSACTION_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_CLI_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_LIVE_POSTGRES_DOGFOOD_REPORT.md`

### Private Admin Endpoint

已完成：

- `POST /v1/admin/registry/import-replace`
- admin bearer auth boundary
- 必需 `X-Request-ID`
- 必需 `Idempotency-Key`
- wrapper request body
- request-size limit
- Postgres-only mutation wiring
- FileStore/unconfigured mutation rejection
- stable service error mapping
- live Postgres dogfood

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_LIVE_POSTGRES_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_CLOSEOUT_PHASE_REVIEW.md`

### Snapshot Propagation E2E

已完成：

- Control Plane 和 Data Plane local service startup
- initial `ipify_public_ip_v1` snapshot publication
- HTTP import/replace 到 `httpbin_public_ip_v1`
- replacement snapshot artifact export
- replacement distribution publish
- manual Data Plane reload
- Data Plane execution 使用替换后的 provider
- usage/decision attribution 指向替换后的 provider 和 snapshot version
- persistent audit count assertions

观测值：

```json
{
  "initial_published_snapshot_version": "snapshot_propagation_ipify_v1",
  "replacement_published_snapshot_version": "snapshot_propagation_httpbin_v2",
  "usage_provider_id": "httpbin",
  "usage_snapshot_version": "snapshot_propagation_httpbin_v2",
  "decision_selected_provider_id": "httpbin_public_ip_v1",
  "audit_counts": {
    "registry_revisions": 4,
    "admin_audit_events": 5,
    "providers": 1,
    "snapshot_artifact_publications": 2
  }
}
```

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`

## 验收标准复盘

| Criterion | Status |
| --- | --- |
| Persistent registry can be replaced through a controlled private endpoint | passed |
| Replacement writes persistent audit evidence | passed |
| Replacement remains Postgres-only | passed |
| FileStore remains default and read-only for mutation | passed |
| Replaced registry can be exported as a snapshot artifact | passed |
| Replaced artifact can be published into a distribution | passed |
| Data Plane can manually reload the changed distribution | passed |
| Data Plane execution uses the replaced provider | passed |
| Usage and decision records preserve replaced provider attribution | passed |
| Snapshot propagation remains manually sequenced | passed |
| Public CRUD remains out of scope | passed |
| Credential vault, billing, marketplace, workflow runtime, and provider onboarding remain out of scope | passed |

## Closeout 判断

这个 milestone 已完成，可以暂停。

关键证明不只是 endpoint 能写入 Postgres，而是 registry mutation 可以穿过现有 artifact/distribution boundary，并改变真实 Data Plane execution，同时 Data Plane 不需要读取 mutable Control Plane tables。

这保持了核心架构规则：

```text
Control Plane owns mutable registry state.
Data Plane consumes immutable/versioned snapshots.
```

## Remaining Risks

### Idempotency 仍然只是 Header-Only

endpoint 要求 `Idempotency-Key`，但 v0 不持久化 idempotency records。

当前行为对 local dogfood 足够安全，因为 registry fingerprint no-op detection 可以避免很多重复影响。但这不足以支撑 hosted mutation semantics，因为它无法区分：

- same key + same request body replay
- same key + different request body conflict
- request completed but client timed out
- request accepted but audit/export side effects need result replay

这是下一项最高信号缺口。

### Admin Auth 仍然是 Local-Private 级别

Bearer-token admin auth 对 local/private dogfood 足够。

它还不是 hosted multi-admin identity 或 permission model。

### Propagation 仍然是手动的

Import/replace 不会自动 publish 或 reload snapshots。

这是刻意保留的边界。没有单独设计 blast radius、rollout order、rollback 和 multi-node Data Plane consistency 之前，不应该实现 automatic propagation。

### Full Registry Replacement 很钝

Full replacement 是正确的 v0 mutation primitive，但不是最终 operator experience。

Granular CRUD 继续 deferred。

### Distribution 仍然是 Local Filesystem

当前 distribution 是本地目录。

Remote object storage、signed artifacts 和 multi-region distribution 是后续 hosted concerns。

### Registry Size Limit 偏保守

endpoint 仍使用保守的 2 MiB request-size limit。

未来大型 hosted registries 可能需要 artifact-based upload 或 configurable limits。

## 仍然不允许

不要启动：

- public registry CRUD APIs
- provider self-onboarding
- marketplace provider submission
- credential vault writes
- plaintext secret storage
- billing or settlement state
- workflow engine support
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## 下一项任务理由

下一项最高信号任务是：

```text
Go Control Plane Admin Mutation Idempotency Store Design v0
```

原因：

- endpoint 已经要求 `Idempotency-Key`
- write path 已经端到端证明
- hosted/private admin mutation 不能只依赖 request headers 和 registry fingerprint no-op checks
- 在增加更多 mutation endpoints 或 operator convenience features 之前，应该先设计 idempotency semantics

预期 design scope：

- persistent idempotency record shape
- key scope：actor/project/operation/key
- request fingerprint semantics
- response replay semantics
- conflict detection for key reuse with a different request
- audit linkage to registry revision and admin audit event ids
- 和 `ReplacePersistentRegistry` 的 transaction boundary
- expiration/retention policy
- failure semantics

该任务不包含：

- public CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace

## 验证

closeout 前已通过：

```text
python scripts/go_control_plane_import_replace_snapshot_propagation_dogfood.py --output tmp/go_control_plane_import_replace_snapshot_propagation_dogfood.json
go test ./...
```

Go test 目录：

```text
services/control-plane
services/data-plane
```
