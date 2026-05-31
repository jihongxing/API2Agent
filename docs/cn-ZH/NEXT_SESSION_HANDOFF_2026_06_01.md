# 下一次会话交接 - 2026-06-01

准备日期：2026-05-31

## 当前状态

当前 milestone 已关闭：

```text
Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0
```

项目已经证明了这条本地 production-shaped chain：

```text
private admin HTTP import/replace
  -> persistent Postgres registry replacement
  -> snapshot artifact export
  -> distribution publish
  -> manual Data Plane reload
  -> Data Plane execution with replaced provider
```

关键 closeout 参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/ROADMAP.md`
- `docs/cn-ZH/IMPLEMENTATION_PLAN.md`

## 明天第一项任务

从这里开始：

```text
Go Control Plane Admin Mutation Idempotency Store Design v0
```

这是 design task。设计被接受前，不进入 implementation。

## 为什么下一项是它

private admin import/replace endpoint 已经要求 `Idempotency-Key`，但系统还没有持久化 idempotency records。

当前 registry fingerprint no-op behavior 对 local dogfood 足够，但 hosted/private admin mutations 需要明确语义：

- same key + same request replay
- same key + different request conflict
- client timeout after server success
- response replay
- audit linkage
- retention and cleanup

## 建议明天先读

设计前先读这些文件：

- `services/control-plane/internal/httpapi/service.go`
- `services/control-plane/internal/httpapi/service_test.go`
- `services/control-plane/internal/registry/postgres_import_replace.go`
- `services/control-plane/internal/registry/postgres_audit.go`
- `services/control-plane/schema/postgres/001_persistent_registry_store.sql`
- `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`

## Design Scope

设计应定义：

- persistent idempotency record schema
- key scope：actor/project/operation/key
- request fingerprint semantics
- response replay semantics
- same key with a different request 的 conflict behavior
- 和 `ReplacePersistentRegistry` 的 transaction boundary
- 与 registry revision / admin audit event evidence 的 linkage
- expiration/retention policy
- failure semantics
- 后续 implementation slice 需要的 tests

## 不要启动

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

## 验证基线

交接前最近一次已完成验证：

```text
python scripts/go_control_plane_import_replace_snapshot_propagation_dogfood.py --output tmp/go_control_plane_import_replace_snapshot_propagation_dogfood.json
go test ./...
```

Go test 目录：

```text
services/control-plane
services/data-plane
```

## 建议明天流程

1. 先重读 closeout doc。
2. inspect 当前 import/replace endpoint 和 Postgres mutation code。
3. 起草 `Go Control Plane Admin Mutation Idempotency Store Design v0`。
4. design 写完后再更新 roadmap 和 implementation plan。
5. design 被接受前不进入 implementation。
