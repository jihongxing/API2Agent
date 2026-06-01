# Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood Closeout + Phase Review v0

日期：2026-06-02

状态：complete

## 决策

Hosted Permission Store Read Model Live Postgres Dogfood slice 可以关闭。

仓库现在已经用真实 local Postgres database、实际 Control Plane schema、seeded hosted permission rows、pgx lookup、fail-closed cases、zero decision persistence 和 secret-safe artifact output 证明了 hosted permission read model。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Design v0
```

该任务应设计 hosted admin gateway 如何把 internal read model 用作 permission source。它必须保持为 design task，不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation，或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Read Model

已完成：

- hosted permission tables 上的 internal Go read model
- repeatable-read/read-only transaction semantics
- active policy version lookup
- 通过 external subject reference 查 subject
- project membership lookup
- active role and grant lookup
- gateway-compatible decision evidence
- missing membership、suspended membership、revoked/missing permission、no active policy 和 ambiguous active policy fail closed
- v0 不持久化 hosted decisions

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_CLOSEOUT_PHASE_REVIEW.md`

### Live Postgres Dogfood

已完成：

- local Postgres 16 container startup
- 从 `services/control-plane/schema/postgres/001_persistent_registry_store.sql` apply schema
- 通过 `seed-postgres` seed harness project
- seed hosted subject、membership、role、binding、grant 和 policy version
- 通过 internal read model 使用真实 pgx DSN lookup
- 生成 redacted artifact

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_LIVE_POSTGRES_DOGFOOD_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| 使用真实 local Postgres database | passed |
| apply 实际 Control Plane schema | passed |
| seed hosted permission rows | passed |
| internal read model 通过 pgx 访问真实 DSN | passed |
| allowed admin decision 返回 `200` 和 permission evidence | passed |
| readonly missing permission 以 `403 PUBLIC_AUTHZ_DENIED` fail closed | passed |
| missing membership 以 `403 PUBLIC_AUTHZ_DENIED` fail closed | passed |
| suspended membership 以 `403 PUBLIC_AUTHZ_DENIED` fail closed | passed |
| revoked grant 以 `403 PUBLIC_AUTHZ_DENIED` fail closed | passed |
| no active policy 以 `503 PERMISSION_SOURCE_UNAVAILABLE` fail closed | passed |
| ambiguous active policy 以 `503 PERMISSION_SOURCE_UNAVAILABLE` fail closed | passed |
| policy source/version/fingerprint/decision id evidence 存在 | passed |
| artifact output redacts DSN password、public bearer tokens 和 gateway secret | passed |
| v0 中 `hosted_permission_decisions` 保持为空 | passed |
| gateway runtime wiring 保持 deferred | passed |
| 未新增 public CRUD、OAuth/OIDC、production gateway、marketplace、vault、billing、workflow 或 automatic propagation scope | passed |

## Dogfood Evidence

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-read-model-live-postgres/report.json
```

观察结果：

- `status=passed`
- `hosted_subjects=5`
- `hosted_project_memberships=4`
- `hosted_roles=4`
- `hosted_role_bindings=6`
- `hosted_permission_grants=9`
- ambiguous-policy case 前 `hosted_policy_versions=1`
- ambiguous-policy case 后 `hosted_policy_versions=2`
- `hosted_permission_decisions=0`
- `secret_safe_evidence=true`
- admin import/replace allowed，policy fingerprint 为 `sha256:hosted-permission-store-fixture-v1`
- readonly import/replace 因 missing permission 本地 denied
- missing membership、suspended membership、revoked grant、no active policy 和 ambiguous active policy 全部 fail closed

## Validation

已通过：

```text
go test ./cmd/api2agent-hosted-permission-read-model-dogfood ./internal/registry -run HostedPermission
go test ./...
python -m py_compile scripts/go_control_plane_hosted_permission_read_model_dogfood.py
python scripts/go_control_plane_hosted_permission_read_model_dogfood.py --output .dogfood/go-control-plane-hosted-permission-read-model-live-postgres/report.json
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

这个 dogfood slice 已完成。

live proof 移除了 scripted read-model tests 之后的主要不确定性：schema、constraints、seeded rows、SQL queries、pgx driver 和 decision evidence 可以在真实 Postgres database 中协同工作。

实现仍然刻意没有接入 gateway runtime request handling。这个边界仍是正确的。下一步应该是 runtime wiring design，明确 gateway 如何获得 public principal context、调用 read model、把 decision evidence 映射为 trusted headers、处理 unavailable/stale policy，并保留 Control Plane second gate。

## Remaining Risks

### No Gateway Runtime Wiring Yet

local gateway contract harness 仍使用 local/static permission source。internal read model 尚未在 gateway request handling 中调用。

### No Decision Persistence Yet

read model 返回 decision evidence，但不插入 `hosted_permission_decisions`。

### No Seed Or Migration Lifecycle Beyond Dogfood

dogfood 使用 direct seed SQL。Production migration ordering、rollback behavior、seed lifecycle 和 policy promotion 仍是未来工作。

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
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Design v0
```

原因：

- gateway permission-source contract 已存在
- local harness 已证明 gateway semantics
- hosted permission schema 已存在
- internal read model 已存在
- real Postgres dogfood 已证明 SQL path
- 下一项风险是如何把 gateway 接到 read model，同时不削弱 fail-closed behavior、trusted-header safety、Control Plane second-gate authority 或 non-goal boundaries

预期范围：

- 设计 hosted read model 的 gateway runtime permission-source interface。
- 定义 public principal input、external subject reference handling、project context、token id evidence、timeout/unavailable behavior 和 stale/ambiguous policy handling。
- 定义 trusted header mapping from read-model decisions。
- 定义 runtime wiring 所需 tests 和 dogfood。
- decision persistence、production deployment、OAuth/OIDC、public CRUD 和 policy management 保持 out of scope。

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
