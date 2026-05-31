# Go Control Plane Import/Replace Closeout + Mutation API Readiness Review v0

日期：2026-05-31

状态：complete

## 决策

persistent registry import/replace slice 已完成。

local/admin CLI primitive 已经足够关闭这个 implementation slice：

```text
api2agent-controlplane import-replace-postgres
```

Mutation API readiness 决策：

```text
可以进入 private admin endpoint design。
不能跳过 design 直接实现 endpoint。
不能进入 public CRUD APIs。
```

推荐下一项任务：

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

## 现在已经完成了什么

### Transaction Design

已完成：

- serializable transaction boundary
- transaction-scoped advisory lock
- full mutable registry replacement
- 按 registry fingerprint 的 no-op behavior
- same-transaction success audit 和 registry revision writes
- rollback rules
- snapshot boundary

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_TRANSACTION_DESIGN.md`

### CLI Implementation

已完成：

- `registry.ReplacePersistentRegistry(ctx, db, reg, opts)`
- `api2agent-controlplane import-replace-postgres`
- structured `RegistryMutationError`
- no-op、replacement、lock conflict、audit failure rollback 和 transaction options 的 unit tests

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_CLI_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

已通过 podman 完成：

- schema apply
- `seed-postgres`
- changed-registry import/replace
- same-registry no-op
- replacement 后 snapshot export
- audit count assertions

观测值：

```json
{
  "replace_noop": "false",
  "second_noop": "true",
  "snapshot_version": "snapshot_import_replace_live_v1",
  "provider_id": "httpbin_public_ip_v1",
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 2,
    "providers": 1
  }
}
```

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_LIVE_POSTGRES_DOGFOOD_REPORT.md`

## 验收标准复盘

| Criterion | Status |
| --- | --- |
| Controlled full-registry write path exists | passed |
| Write path is local/admin only | passed |
| No public CRUD API added | passed |
| Serializable transaction used | passed |
| Registry-wide advisory lock used | passed |
| Same-fingerprint no-op behavior exists | passed |
| Non-noop writes registry revision | passed |
| Success writes admin audit | passed |
| Audit failure rolls back mutation | passed |
| Live Postgres replacement verified | passed |
| Live Postgres no-op verified | passed |
| Snapshot export sees replaced registry | passed |

## Readiness 判断

### Ready

API2Agent 已经可以设计同一个 import/replace operation 的 private admin service endpoint。

原因：

- core operation 已经是 reusable internal function
- persistent transaction behavior 已有 unit tests
- live Postgres dogfood 已通过
- 现有 Control Plane service 已有 admin auth boundary
- registry validate/export/publish endpoints 已经使用同类 service pattern

### Not Ready

API2Agent 还不能跳过设计直接实现 endpoint。

private endpoint design 必须明确：

- HTTP method 和 path
- request body shape
- max body size
- idempotency header requirements
- actor/request identity mapping
- admin auth behavior
- `RegistryMutationError` 的 error mapping
- failure audit behavior
- response shape
- endpoint 接受 raw registry JSON 还是 wrapper object
- snapshot export/publish 是否继续分离

### 仍然不允许

不要实现：

- public CRUD registry APIs
- provider self-onboarding APIs
- marketplace provider submission
- credential vault writes
- plaintext key storage
- billing or settlement state
- automatic snapshot publish/reload

## 剩余风险

### Failure Audit Timing

Failure audit 是 best effort，且不能遮蔽原始错误。service endpoint design 需要明确 transaction rollback 附近的 failure audit timing。

### Request Identity

CLI 用 flags 表达 actor/request/idempotency metadata。service endpoint 必须从 headers 和 admin identity 中一致地推导这些字段。

### Large Registry Payloads

Import/replace 接受 full registry documents。service endpoint implementation 前必须有 request size limits。

### Hosted Auth Strength

当前 local admin token 足够 local service dogfood，但不是完整 hosted auth model。

### Idempotency Key Enforcement

CLI 允许 optional idempotency keys。service endpoint 应该要求 idempotency key。

## 下一项任务

只进入设计：

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

期望产出：

- endpoint contract
- request/response schema
- auth and idempotency rules
- error mapping
- audit mapping
- explicit non-goals

该 design 被接受前，不应实现 endpoint。

