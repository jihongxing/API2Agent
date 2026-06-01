# Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness Implementation Report v0

日期：2026-06-02

状态：complete

## 摘要

Control Plane registry package 现在有了 local/private hosted permission policy mutation contract harness。

该 harness 证明了 hosted permission policy rows 的 draft、validation、review、promotion、rollback、idempotency、conflict、audit 和 gateway read-model compatibility semantics，同时不暴露 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、customer-facing decision history、public policy write APIs，或 Data Plane 从 mutable Control Plane tables 读取。

## 已实现

新增：

```text
services/control-plane/internal/registry/hosted_permission_policy_mutation.go
services/control-plane/internal/registry/hosted_permission_policy_mutation_test.go
```

Harness 建模：

- hosted subjects
- hosted project memberships
- hosted roles
- hosted role bindings
- hosted permission grants
- hosted policy versions
- policy drafts
- policy mutation audit events
- idempotency records

## Contract Helpers

新增 local/private helper：

```text
HostedPermissionPolicyMutationHarness
```

它支持：

- `BeginDraft`
- `BeginStaleDraftForContract`
- `ValidateDraft`
- `RequestReview`
- `PromoteDraft`
- `RollbackPolicy`
- `ResolvePermission`
- `RunHostedPermissionPolicyMutationBoundaryDogfood`

这些是 local Go contract helpers，不是 public endpoint paths。

## 已证明语义

Harness 证明：

- draft changes 在 promotion 前不影响 read decisions
- promotion 会激活新 policy version
- prior active policy versions 会变成 superseded
- policy fingerprints 基于 effective permission graph deterministic 计算
- gateway-compatible permission decisions 能观察 promoted grants
- rollback 创建新的 active rollback version，而不是重写 historical policy evidence
- persisted permission decisions 不属于 mutation scope
- stale-base promotion 返回 `POLICY_VERSION_CONFLICT`
- duplicate active grant validation 返回 `POLICY_GRANT_CONFLICT`
- platform-scope escape 返回 `POLICY_SCOPE_VIOLATION`
- same idempotency key 加 same canonical request 返回 replay evidence
- same idempotency key 加 different canonical request 返回 `IDEMPOTENCY_KEY_CONFLICT`
- audit metadata 不包含 raw idempotency keys、raw tokens、gateway secrets、OAuth tokens、plaintext API keys 或 vault material

## Dogfood Report Helper

新增 in-process report helper：

```text
RunHostedPermissionPolicyMutationBoundaryDogfood()
```

它报告：

- promotion 前的 active policy version
- promotion 前的 active policy fingerprint
- draft validation status
- promotion status
- idempotency replay count
- idempotency conflict status
- scope-violation status
- stale-base conflict status
- rollback status
- gateway decision before promotion
- gateway decision after promotion
- gateway decision after rollback
- audit row count
- secret leakage checks

测试中 observed：

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

## 测试

新增测试覆盖：

- promotion updates read-model-compatible decision evidence
- idempotency replay 不创建第二个 mutation/audit outcome
- idempotency conflict 不 mutate active policy rows
- scope-escape validation fails
- duplicate active grant validation fails
- stale-base promotion deterministic failure
- rollback 创建新的 active version 并移除 promoted grant access
- dogfood report passes 且保持 secret-safe

## 验证

已通过：

```text
go test ./internal/registry -run "TestHostedPermissionPolicyMutation"
go test ./internal/registry
go test ./...
```

Go test 目录：

```text
services/control-plane
```

## 保持非目标

没有新增 public CRUD、public user/project/role management、OAuth/OIDC integration、invitation/login/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、public policy write APIs、customer-facing decision history、legal-hold customer API、customer export/delete API，或 Data Plane mutable table read。

## 下一项推荐任务

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness Closeout + Phase Review v0
```

该 closeout 应判断 local/private mutation contract proof 是否足以关闭，然后再进入后续 durable/private implementation slice。
