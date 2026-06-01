# Go Control Plane Hosted Permission Store Read Model Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Hosted Permission Store Read Model implementation slice 可以关闭。

仓库现在有了 internal Go read model，可以用 repeatable-read/read-only transaction semantics 从 hosted permission tables 解析 hosted permission decisions。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood v0
```

该任务应在真实 local Postgres database 中 seed hosted permission tables，并证明同样的 allow/deny evidence 可以在实际 schema 和 SQL 上工作。不要接入 production gateway runtime，不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault material writes、billing、workflow runtime、automatic propagation，或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Design And Contract

本 slice 之前已完成：

- durable permission-store entity model
- gateway lookup request/decision contract
- hosted admin routes 的 endpoint permission mapping
- unavailable、ambiguous、stale、missing、revoked 或 denied policy 的 fail-closed semantics
- policy source/version/fingerprint/decision evidence requirements
- secret-safe evidence expectations

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`

### Schema

本 slice 之前已完成：

- `hosted_subjects`
- `hosted_project_memberships`
- `hosted_roles`
- `hosted_role_bindings`
- `hosted_permission_grants`
- `hosted_policy_versions`
- `hosted_permission_decisions`

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_CLOSEOUT_PHASE_REVIEW.md`

### Read Model

已在以下文件完成：

```text
services/control-plane/internal/registry/hosted_permission_store.go
```

read model 现在会：

- 要求显式 DB。
- 启动 repeatable-read、read-only transaction。
- 只接受一个 active hosted policy version。
- 通过 external subject reference 解析 hosted subject。
- 为请求 project 解析 project membership。
- 解析 active role bindings 和 active hosted roles。
- 解析 active permission grants。
- 返回 gateway-compatible local decision，包含 identity、roles、permissions、required permission、policy source/version/fingerprint、decision id 和 resolved time。
- 对 missing membership、inactive membership、missing permission、missing active policy 和 ambiguous active policy fail closed。
- v0 不持久化 `hosted_permission_decisions`。

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| hosted permission tables 上存在 internal Go read model | passed |
| lookup 使用 repeatable-read/read-only transaction semantics | passed |
| active policy version 是 decision evidence 的一部分 | passed |
| ambiguous/no active policy 以 `503 PERMISSION_SOURCE_UNAVAILABLE` fail closed | passed |
| hosted subject lookup 通过 external subject reference 解析 | passed |
| missing/inactive subject fail closed | passed |
| project membership 针对 requested project 解析 | passed |
| missing membership 以 `403 PUBLIC_AUTHZ_DENIED` fail closed | passed |
| suspended membership 以 `403 PUBLIC_AUTHZ_DENIED` fail closed | passed |
| active roles 和 permission grants 被解析 | passed |
| revoked/missing required permission fail closed | passed |
| decision shape 与 gateway contract evidence 兼容 | passed |
| raw public tokens、gateway secrets、OAuth tokens、refresh tokens 和 plaintext material 不进入 decision evidence | passed |
| read model v0 不写 hosted decision rows | passed |
| gateway runtime wiring 保持 deferred | passed |
| 未新增 public CRUD、OAuth/OIDC、production gateway、marketplace、vault、billing、workflow 或 automatic propagation scope | passed |

## Validation

已通过：

```text
go test ./internal/registry -run HostedPermission
go test ./...
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
git diff --check
git diff --cached --check
```

Go test 工作目录：

```text
services/control-plane
```

Python test 和 diff-check 工作目录：

```text
repository root
```

## Closeout Judgment

这个 implementation slice 已完成。

read model 已证明 Go code 可以从 hosted permission schema 解析 hosted permission decision shape，同时保留 gateway contract、fail-closed behavior、transaction consistency 和 secret-safe evidence boundary。

实现刻意保持 internal，并且没有接到 hosted gateway runtime。这是正确的 v0 boundary：先证明 private lookup layer，再进入 live seeded database proof、runtime integration、decision persistence 或 public management surfaces。

## Remaining Risks

### No Live Postgres Read-Model Dogfood Yet

当前 proof 使用 scripted SQL driver。SQL shape 仍需要用 seeded hosted permission rows 在真实 local Postgres dogfood 中验证。

### No Gateway Runtime Wiring Yet

local gateway contract harness 仍使用 local/static permission source。Go read model 尚未被 gateway request handling 使用。

### No Decision Persistence Yet

read model 返回 decision evidence，但不插入 `hosted_permission_decisions`。

### No Seed Or Migration Lifecycle Beyond The Draft Schema

仓库仍使用单一 draft schema 做 local dogfood。Migration ordering、rollback behavior 和 production deployment lifecycle 仍是未来工作。

### No Policy Write Path

Hosted policy、role、grant 和 membership mutation 仍是 out of scope。仍没有 public 或 internal policy management API。

### No Real Public Identity Lifecycle

OAuth/OIDC、login、session、invitation 和 external subject lifecycle 仍是未来工作。

### No Production Gateway Deployment

Production routing、TLS、private network enforcement、observability、rate limits、rollout 和 operational hardening 仍是未来工作。

### Provider Ownership Still Needs Hardening

Project-scoped registry mutation 已受约束，但 provider ownership 在 v0 仍基于 metadata。

## Still Not Allowed

不要开始：

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation/login/session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood v0
```

原因：

- schema 已存在
- Go read model 已存在
- package tests 已用 scripted rows 证明 behavior
- 下一项风险是真实 Postgres schema、constraints、seeded rows 和 SQL queries 是否在 local dogfood 中表现一致

预期范围：

- 在 local Postgres dogfood database 中 seed hosted permission tables。
- 用真实 Postgres 调用 internal read model。
- 证明 allowed decision evidence，以及 missing membership、suspended membership、revoked/missing permission、no/ambiguous active policy fail closed。
- 断言 evidence 不包含 raw public tokens 或 gateway secrets。
- gateway runtime wiring 和 decision persistence 继续 deferred。

Out of scope：

- public CRUD
- OAuth/OIDC
- invitation/session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- vault writes
- billing
- workflow runtime
- automatic publish/reload
- Data Plane mutable Control Plane table reads
