# Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness Closeout + Phase Review v0

日期：2026-06-02

状态：complete

## 决策

Hosted Permission Policy Mutation Boundary Contract Harness implementation slice 可以关闭。

仓库现在已经证明 hosted permission policy rows 的 local/private mutation contract：

```text
private hosted policy mutation request
  -> draft policy graph
  -> validation and review state
  -> idempotency and conflict checks
  -> promotion to a new active policy version
  -> gateway-compatible permission decision evidence
  -> rollback as a new active version
  -> secret-safe mutation audit evidence
```

推荐下一项任务：

```text
Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation Design v0
```

该任务应设计 policy mutation rows 的 durable/private implementation boundary，但不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、public policy write APIs、customer-facing decision history、legal-hold customer APIs、customer export/delete APIs，或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Design

已完成：

- hosted subjects、memberships、roles、role bindings、permission grants 和 policy versions 的 private mutation ownership
- draft/review/promotion/rollback lifecycle
- idempotency、audit、conflict、authorization 和 gateway read-model compatibility semantics
- local contract harness requirements
- 明确的 non-goals 和 deferred public surfaces

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_POLICY_MUTATION_BOUNDARY_DESIGN.md`

### Contract Harness

已完成：

- local/private `HostedPermissionPolicyMutationHarness`
- draft creation 和 validation helpers
- review request 和 promotion helpers
- rollback helper 会创建新的 active version，而不是重写历史
- 基于 effective permission graph 的 deterministic policy fingerprints
- promotion 前、promotion 后、rollback 后的 gateway-compatible permission decisions
- idempotency replay 和 idempotency conflict behavior
- stale-base、duplicate-grant 和 platform-scope violation checks
- secret-safe mutation audit evidence
- in-process dogfood report helper

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_POLICY_MUTATION_BOUNDARY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| draft mutation 在 promotion 前不影响 gateway decisions | passed |
| validation 能检测 duplicate active grants | passed |
| validation 拒绝 platform-scope escape | passed |
| review state 在 promotion 前有表示 | passed |
| promotion 激活新的 policy version | passed |
| previous active policy version 变为 superseded | passed |
| stale-base promotion 以 `POLICY_VERSION_CONFLICT` 失败 | passed |
| deterministic fingerprint 随 effective permission graph 变化 | passed |
| gateway-compatible decision 能观察 promoted grant | passed |
| rollback 创建新的 active rollback version | passed |
| rollback 移除 promoted grant access，且不重写 historical evidence | passed |
| idempotent replay 返回 replay evidence，且不创建第二个 mutation outcome | passed |
| idempotency key conflict 被拒绝，且不 mutate active policy rows | passed |
| persisted permission decisions 保持在 mutation scope 之外 | passed |
| audit metadata 排除 raw idempotency keys、tokens、gateway secrets、OAuth tokens、plaintext API keys 和 vault material | passed |
| 未新增 public CRUD、OAuth/OIDC、invitation/session、production gateway、marketplace、vault、billing、workflow、automatic propagation、public policy write API 或 Data Plane mutable-read scope | passed |

## Dogfood 证据

In-process dogfood helper：

```text
RunHostedPermissionPolicyMutationBoundaryDogfood()
```

测试中观察到：

- `status=passed`
- `draft_validation_status=passed`
- `promotion_status=passed`
- `rollback_status=passed`
- `idempotency_replay_count=1`
- `idempotency_conflict_status=IDEMPOTENCY_KEY_CONFLICT`
- `scope_violation_status=POLICY_SCOPE_VIOLATION`
- `stale_base_conflict_status=POLICY_VERSION_CONFLICT`
- `gateway_decision_before_promotion=denied`
- `gateway_decision_after_promotion=allowed`
- `gateway_decision_after_rollback=denied`
- 没有 raw idempotency key、raw token 或 gateway secret leakage

## 验证

Implementation slice 中已通过：

```text
go test ./internal/registry -run "TestHostedPermissionPolicyMutation"
go test ./internal/registry
go test ./...
```

Go test 目录：

```text
services/control-plane
```

Closeout validation：

```text
git diff --check
```

## 阶段完成度

这个 local/private contract harness closeout lane 对 v0 是 100% complete。

更大的 Hosted Control Plane phase completion 现在估算为 74%。

估算只小幅推进，因为 policy mutation semantics 已被接受为 local contract proof，但 durable private persistence、transaction boundaries、service wiring、live Postgres dogfood 和 production gateway rollout 仍是未来工作。

## Closeout Judgment

这个 implementation slice 已完成。

Local harness 证明了预期 policy mutation boundary，以及 durable implementation 必须保留的 safety properties：drafts 隔离、promotion 显式、rollback 为 append-style、idempotency deterministic、conflicts fail closed、gateway 只观察 promoted policy，并且 audit evidence 保持 secret-safe。

该 harness 不是 public policy management API，也不是 production authorization system。它足以作为 v0，因为它在 durable/private implementation design 开始前关闭了 mutation semantics 问题。

## Remaining Risks

### No Durable Mutation Store Yet

Drafts、policy mutation audit、idempotency records 和 policy version promotion 仍是 local harness state。下一项任务应设计 durable private storage 和 transaction ownership。

### No Private Service Endpoint Yet

目前没有 hosted service endpoint 用于 policy mutation。Endpoint shape、trusted-gateway authorization、transaction behavior 和 response evidence 仍是设计工作。

### No Live Postgres Dogfood Yet

当前 proof 是 in-process Go。Durable Postgres rows、migrations、constraints 和 live dogfood 仍是未来切片。

### Propagation Remains Manual/Deferred

Promotion 证明了 read-model compatibility，但没有实现 automatic snapshot publish、gateway reload、cache invalidation 或 production propagation。

### Public Product Surfaces Are Still Deferred

Public role CRUD、user/project management、OAuth/OIDC、invitations、sessions、customer-facing history、export/delete 和 legal-hold customer APIs 仍然 out of scope。

### Production Gateway Integration Remains Future Work

Local gateway-compatible decision proof 之后还必须进入 service wiring、observability、timeout behavior、rollout controls 和 production deployment。

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
- automatic snapshot publish、reload、cache invalidation 或 propagation
- public policy write APIs
- customer-facing decision history
- legal-hold customer API
- customer export/delete API
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation Design v0
```

原因：

- local/private mutation contract proof 已接受
- 下一项风险是 durable transaction ownership，而不是 public API shape
- durable design 可以保留 draft/review/promotion/rollback、idempotency、conflict、audit 和 gateway read-model compatibility semantics
- 工作可以保持 private/internal，避免 public CRUD、OAuth/OIDC、production gateway rollout、marketplace、vault、billing、workflow 和 automatic propagation

预期范围：

- 设计 policy drafts、policy versions、mutation audit 和 idempotency records 的 durable tables 或 row ownership
- 定义 validation、promotion 和 rollback 的 private transaction boundaries
- 将 conflict 和 idempotency semantics 映射到 durable storage
- 定义 secret-safe response 和 audit evidence
- 记录未来 implementation slice 的 live Postgres dogfood criteria

Out of scope：

- public CRUD
- OAuth/OIDC
- invitation/session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- vault writes
- billing
- workflow runtime
- automatic propagation
- public policy write APIs
- customer-facing decision history/export/delete/legal-hold APIs
- Data Plane mutable Control Plane table reads
