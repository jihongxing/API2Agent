# Go Control Plane Admin Mutation Idempotency Store Closeout + Phase Review v0

日期：2026-05-31

状态：complete

## 决策

Admin Mutation Idempotency Store slice 可以关闭。

private admin import/replace endpoint 现在已经有 committed registry mutations 的 durable Postgres-backed idempotency semantics：

```text
same scoped key + same request
  -> cached committed response replay

same scoped key + different request
  -> 409 IDEMPOTENCY_KEY_CONFLICT
```

推荐下一项任务：

```text
Go Control Plane Hosted Admin Identity Boundary Design v0
```

这应该先做 design。identity boundary 被接受前，不进入 implementation。

## What Is Now Complete

### Design

已完成：

- persistent idempotency record schema
- key scope：`project_id + actor_id + operation + idempotency_key_hash`
- raw idempotency key hashing
- canonical request fingerprint semantics
- response replay semantics
- same key with different request 的 conflict behavior
- 和 `ReplacePersistentRegistry` 的 transaction boundary
- registry revision 和 admin audit linkage
- retention and cleanup policy
- failure semantics
- implementation test requirements

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_DESIGN.md`

### Implementation

已完成：

- `admin_mutation_idempotency_records` Postgres table
- scoped key hashing 和 hash-prefix storage
- import/replace request fingerprinting
- same-key same-request replay
- same-key different-request conflict detection
- same-transaction idempotency completion
- 链接到 `registry_revisions.id`
- 链接到 `admin_audit_events.id`
- replay metadata updates
- HTTP replay headers
- stable idempotency error mapping
- schema、registry-layer 和 HTTP regression tests

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

已通过 podman-backed Postgres 完成：

- first HTTP import/replace 返回 `201` 和 `noop=false`
- same-key same-request replay 返回 cached `201`
- replay 返回 `Idempotency-Replayed: true`
- replay 返回 `Idempotency-Record-ID: 1`
- same-key different-request reuse 返回 `409 IDEMPOTENCY_KEY_CONFLICT`
- independent same-registry key 返回 `200` 和 `noop=true`
- exported snapshot 使用 `httpbin_public_ip_v1`
- persistent evidence rows 已断言

观测值：

```json
{
  "first_status": 201,
  "replay_status": 201,
  "conflict_status": 409,
  "noop_status": 200,
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 2,
    "idempotency_records": 2,
    "providers": 1
  }
}
```

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_LIVE_POSTGRES_DOGFOOD_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| idempotency record schema 已实现 | passed |
| same-key same-request replay 返回 cached committed response | passed |
| same-key different-request conflict 返回 `409 IDEMPOTENCY_KEY_CONFLICT` | passed |
| 和 registry import/replace 的 transaction linkage 已实现 | passed |
| audit and revision linkage 已实现 | passed |
| raw idempotency key 不存入 persistent idempotency rows | passed |
| live Postgres dogfood 验证 replay 和 conflict semantics | passed |
| public CRUD 继续 out of scope | passed |
| automatic propagation 继续 out of scope | passed |
| vault、billing、marketplace、workflow 和 provider onboarding 继续 out of scope | passed |

## Closeout Judgment

这个 slice 已完成。

Control Plane write path 现在对 retry safety、client timeout after commit、accidental idempotency key reuse 都有 durable answer。实现也继续保持现有 architecture rule：

```text
Control Plane owns mutable registry state.
Data Plane consumes immutable/versioned snapshots.
```

Idempotency replay 不会 publish snapshots、reload Data Plane instances，也不会让 Data Plane 读取 mutable Control Plane tables。

## Remaining Risks

### Hosted Admin Identity 仍然是 Local-Private

service 仍然用 bearer token 认证 private admin requests。

`X-Actor-ID` 仍是 local/private actor hint，不是 hosted identity boundary。

idempotency store 已经有 `project_id` scope，但 v0 在 hosted project identity 存在前填 `control_plane`。

### Project Scope 还不是真实边界

当前 mutation path 是 registry-wide。

还没有 hosted project membership、role、permission 或 tenant boundary。增加更多 mutation endpoints 前，Control Plane 需要明确：

- authenticated admin principal
- project or organization scope
- actor attribution
- permission checks
- audit identity fields
- idempotency project scope

### Automatic Snapshot Propagation 仍然是手动的

Import/replace 继续和 export、publish、Data Plane reload 分离。

这是刻意保留。Automatic propagation 需要单独的 rollout、consistency 和 rollback design。

### Full Registry Replacement 仍然较钝

Full replacement 作为 v0 mutation primitive 可以接受。

在 hosted identity、project scope 和 mutation safety 更清楚之前，granular CRUD 应继续 deferred。

### Retention Cleanup 已设计但未运营化

Records 已有 `expires_at`，但还没有 background cleanup job。

对 local slice 可接受。Hosted deployments 之后需要 cleanup scheduling 和 retention policy controls。

## Still Not Allowed

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

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Hosted Admin Identity Boundary Design v0
```

原因：

- idempotency scope 已经需要真实 `project_id` 和 authenticated `actor_id`
- 当前 `X-Actor-ID` 只是 local/private hint
- future hosted mutations 在增加更多 write surfaces 前需要 permissions
- audit evidence 应绑定稳定 admin principal，而不是任意 header
- hosted readiness 现在更依赖 identity/project boundaries，而不是继续增加 mutation mechanics

预期 design scope：

- authenticated admin principal shape
- project or organization scope
- hosted mode 下替代 local `X-Actor-ID` semantics 的规则
- private admin mutations 的 role/permission checks
- audit identity mapping
- idempotency `project_id` 和 `actor_id` derivation
- local/private compatibility behavior
- 下一项 implementation slice 需要的 tests

该任务不包含：

- public CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime

## Validation

已通过：

```text
python -m py_compile scripts\go_control_plane_idempotency_store_dogfood.py
python scripts\go_control_plane_idempotency_store_dogfood.py --output tmp\go_control_plane_idempotency_store_dogfood.json
go test ./...
```

Go test 目录：

```text
services/control-plane
```
