# Go Control Plane Hosted Permission Policy Mutation Boundary Design v0

日期：2026-06-02

状态：complete

## 决策

在把 seeded hosted permission rows 变成 mutable policy state 之前，先设计 hosted permission policy mutation boundary。

下一项 implementation 应保持 local/private，只证明 hosted subjects、memberships、roles、role bindings、permission grants 和 policy versions 的 mutation semantics。不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、Data Plane 从 mutable Control Plane tables 读取、customer-facing decision history，或 public policy write API。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness v0
```

该任务应实现 local contract helpers 和 tests，用于 draft policy mutation、review、promotion、rollback、idempotency、audit、conflict handling 和 gateway read-model compatibility。

## 为什么现在做这个设计

Hosted permission lane 已经证明：

- durable permission-store schema
- internal read model over hosted permission tables
- seeded rows 的 live Postgres permission lookup
- gateway runtime wiring to the read model
- request-time permission decision persistence
- decision evidence duplicate/conflict integrity
- production-shaped decision persistence behavior
- retention/history metadata 和 redacted local history queries

剩余 hosted-readiness gap 是 policy data 仍然是 seed 的。Roles、grants、memberships 和 policy versions 需要安全 mutation lifecycle，然后才能考虑后续 customer-facing identity、history、export 或 administration surfaces。

## 目标

- 定义 hosted permission policy rows 的 mutation ownership boundary
- 定义 activation 前的 staged/draft policy changes
- 定义 active policy versions 的 review 和 promotion semantics
- 定义不重写 decision evidence 的 rollback semantics
- 定义 idempotency、conflict 和 concurrency behavior
- 定义 mutation attempts 和 promotions 的 audit evidence
- 定义 gateway/read-model compatibility requirements
- 定义 local/private contract harness 的 implementation 和 dogfood evidence

## 非目标

不要启动：

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation、login 或 session lifecycle
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish 或 reload
- public policy write APIs
- Data Plane 从 mutable Control Plane tables 读取
- real production gateway deployment
- customer-facing decision history endpoint
- legal-hold customer API
- customer export 或 deletion API

## 边界

Hosted permission mutation 是 trusted gateway claims 和 Control Plane second-gate checks 后面的 private Control Plane operation：

```text
trusted hosted admin request
  -> private policy mutation service
  -> staged mutation validation
  -> policy draft / policy version rows
  -> audited review and promotion
  -> active policy version
  -> gateway read model consumes coherent active policy
```

Gateway 继续拥有 request-time permission lookup。Data Plane 继续消费 immutable/versioned execution snapshots，不能读取 mutable hosted permission tables。

V0 mutation 应实现为 local contract helpers 或 private internal endpoints。Public product surfaces 仍然 deferred。

## Mutable Entities

Mutation boundary 覆盖这些 hosted permission-store entities：

| Entity | Mutation stance |
| --- | --- |
| `hosted_subjects` | V0 中只能从 trusted local/test principals 创建或更新 status。Public identity lifecycle deferred。 |
| `hosted_project_memberships` | 可以在 project/organization scope 内 add、suspend 或 revoke。 |
| `hosted_roles` | 可以为 project/organization policy source 创建或 disable。Platform roles 仍然仅 operator/internal。 |
| `hosted_role_bindings` | 可以为 subject/project/role tuple add 或 revoke。 |
| `hosted_permission_grants` | 可以为 role 和 scope type add 或 revoke。 |
| `hosted_policy_versions` | 拥有 draft、active、superseded、revoked、promoted 和 rollback policy state。 |

Hosted permission decision rows 不是 mutable policy state。它们是 append-only evidence，在 policy rollback 时不能被重写。

## Operation Set

Local contract harness 应证明这些 conceptual operations：

| Operation | Purpose |
| --- | --- |
| `policy_mutation.begin_draft` | 从当前 active policy version 打开 scoped draft。 |
| `policy_mutation.apply_patch` | 将 subject、membership、role、binding 或 grant changes 应用到 draft。 |
| `policy_mutation.validate_draft` | 检查 policy invariants，但不激活 draft。 |
| `policy_mutation.request_review` | 冻结 draft 进入 promotion review。 |
| `policy_mutation.promote` | 原子激活 reviewed policy version。 |
| `policy_mutation.rollback` | 从历史 active policy version 派生 rollback version 并 promote。 |
| `policy_mutation.cancel_draft` | 将未使用 draft 标记为 abandoned。 |

这些名字是 contract labels，不是 public endpoint paths。

## Draft And Promotion Lifecycle

Policy versions 应通过窄状态机流转：

```text
draft -> review_requested -> active
active -> superseded
draft -> abandoned
active -> rollback_candidate -> active
```

规则：

- 每个 policy source 只能有一个 active policy version
- draft changes 不影响 gateway read decisions
- promotion 必须与 audit evidence 原子提交
- promotion 必须计算 deterministic `policy_fingerprint`
- supersede active policy 时必须保留 previous version，用于 rollback evidence
- rollback 创建从 prior state 派生的新 active version，而不是原地修改历史 rows
- mixed-version reads 必须在 gateway/read model 中 fail closed

## Policy Fingerprint

Active policy fingerprint 必须基于 effective permission graph deterministic 计算：

- 与 policy source 相关的 active subjects
- active memberships
- active roles
- active role bindings
- active permission grants
- active policy source 和 policy version

必须排除：

- raw public tokens
- idempotency keys
- request ids
- audit ids
- draft-only notes
- 不改变 effective authorization 的 timestamps

Fingerprint format 保持：

```text
sha256:<hex>
```

## Idempotency

Policy mutation idempotency 应沿用现有 admin mutation pattern：

```text
project_id + actor_id + operation + idempotency_key_hash
```

Request fingerprint 是 canonical mutation intent，不是 raw HTTP body。

最小 request fingerprint fields：

```json
{
  "version": "hosted-permission-policy-mutation-v0",
  "operation": "policy_mutation.promote",
  "policy_source": "hosted_permission_store",
  "project_id": "project_alpha",
  "organization_id": "org_alpha",
  "base_policy_version": "permission-policy-v7",
  "draft_policy_version": "permission-policy-v8-draft",
  "mutation_patch_fingerprint": "sha256:..."
}
```

规则：

- same scoped key 加 same request fingerprint 返回 committed outcome
- same scoped key 加 different request fingerprint 返回 `IDEMPOTENCY_KEY_CONFLICT`
- raw `Idempotency-Key` 不能存储
- idempotency records 在适用时必须关联 audit evidence 和 promoted policy version
- canonical fingerprint 创建前失败的 validation 不需要 durable idempotency outcome

## Conflict Semantics

Mutation service 必须拒绝：

- 从 stale base policy version promotion
- 一个 policy source 出现两个 active policies
- 同一 subject/project/role 的 duplicate active role binding
- 同一 role/permission/scope type 的 duplicate active grant
- membership、binding 或 grant changes 越出 trusted project scope
- project-scoped mutation 试图写 platform scope
- disabled role 或 revoked membership activation
- promotion 时 policy fingerprint mismatch

推荐 stable conflict types：

| Condition | Error type |
| --- | --- |
| stale base policy | `POLICY_VERSION_CONFLICT` |
| duplicate active role binding | `POLICY_BINDING_CONFLICT` |
| duplicate active permission grant | `POLICY_GRANT_CONFLICT` |
| scope escape | `POLICY_SCOPE_VIOLATION` |
| invalid status transition | `POLICY_STATE_CONFLICT` |
| idempotency mismatch | `IDEMPOTENCY_KEY_CONFLICT` |

## Authorization

V0 authorization 仍然基于 private trusted-gateway。

Required permissions 应显式定义：

| Operation family | Required permission |
| --- | --- |
| validate draft | `control_plane.permission_policy.validate` |
| create or patch draft | `control_plane.permission_policy.draft_write` |
| request review | `control_plane.permission_policy.request_review` |
| promote policy | `control_plane.permission_policy.promote` |
| rollback policy | `control_plane.permission_policy.rollback` |
| cancel draft | `control_plane.permission_policy.cancel_draft` |

Project-scoped actors 只能 mutate 自己的 project policy surface。Platform/operator roles 只能在 private/internal contexts 管理 platform policy sources。

Control Plane second gate 必须在 mutation work 开始前检查 trusted gateway permissions 和 project scope。

## Audit Evidence

每个到达 canonical mutation intent 的 accepted mutation attempt 都应创建 secret-safe audit evidence。

Audit metadata 应包含：

- actor id
- subject id when available
- project id
- organization id
- operation
- policy source
- base policy version
- draft policy version
- promoted policy version when applicable
- previous active policy version
- resulting policy fingerprint
- mutation patch fingerprint
- idempotency key hash and prefix
- request id
- outcome

Audit metadata 不能包含：

- raw public bearer tokens
- raw gateway secrets
- raw session tokens
- OAuth access 或 refresh tokens
- plaintext API keys
- raw idempotency key
- 可能包含 user-supplied notes 或 external identifiers 的 full request body

## Gateway Read-Model Compatibility

Promotion 后，现有 read model 必须能解析 coherent active policy view：

- 每个 policy source 一个 active `hosted_policy_versions` row
- project 内可见 active membership 和 binding rows
- active grants 映射到 endpoint permissions
- permission decisions 中有 deterministic policy version 和 fingerprint
- revoked membership 或 grants 在 promotion 后 deny future decisions
- stale 或 mixed-version reads fail closed

Promotion 不触发 automatic snapshot publish/reload。它只影响 hosted gateway authorization。

## Rollback

Rollback 是 policy mutation，不是 table rewind。

规则：

- rollback 创建新的 active policy version，其 effective graph 匹配某个 previous active version
- previous active version 变为 superseded
- rollback 必须创建 audit evidence，并关联 source 和 target versions
- persisted permission decisions 保持 immutable，继续引用 decision time 使用的 policy version/fingerprint
- rollback 必须支持 idempotency 并处理 conflict

## Local Contract Harness Requirements

下一项 implementation 应证明：

- 从 active seeded policy 创建 draft
- patch membership、role binding 和 grant changes
- validation 拒绝 scope escape 和 duplicate active grants/bindings
- review/promotion 激活且仅激活一个 policy version
- gateway read model 能观察 promoted permissions
- revoked 或 removed grants 在 promotion 后 deny
- stale-base promotion deterministic conflict
- rollback 以新的 active version 恢复 prior effective permission graph
- idempotent replay 返回 original mutation outcome
- idempotency conflict 不 mutate policy rows
- audit rows 写入 secret-safe metadata
- Data Plane 不读取 mutable permission tables

## Dogfood Evidence Requirements

后续 local/private dogfood artifact 应报告：

- promotion 前后的 active policy version
- promotion 前后的 active policy fingerprint
- draft validation status
- promotion status
- rollback status
- idempotency replay count
- idempotency conflict status
- scope-violation status
- stale-base conflict status
- gateway decision before promotion
- gateway decision after promotion
- gateway decision after rollback
- audit row count delta
- raw tokens、raw idempotency keys 和 gateway secrets 不存在

建议 artifact path：

```text
.dogfood/go-control-plane-hosted-permission-policy-mutation-boundary/report.json
```

## Acceptance Criteria

该 design 完成条件：

- hosted permission policy rows 的 mutation ownership 已文档化
- draft/review/promotion/rollback lifecycle 已明确
- idempotency、audit、conflict 和 authorization semantics 已明确
- gateway read-model compatibility 已定义
- local contract harness 和 dogfood requirements 已定义
- public CRUD、OAuth/OIDC、production deployment、vault、billing、marketplace、workflow、automatic propagation、policy write APIs、customer-facing decision history 和 Data Plane mutable reads 保持 deferred

## 完成度估计

Hosted permission policy mutation boundary design lane：

```text
100%
```

Hosted Control Plane phase：

```text
73%
```

这是估算。该 design 降低了 policy lifecycle ambiguity，但 hosted policy mutation 仍需要 contract harness、local implementation proof、live dogfood、closeout、public identity lifecycle、customer-facing history/export/delete、production gateway deployment、production operations、vault/billing/marketplace/workflow surfaces，并继续明确约束 Data Plane mutable-read decisions。

## 下一项任务

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness v0
```

下一项任务只应实现 local/private mutation contract harness 和 tests。不要暴露 public policy write APIs，也不要启动 public role management。
