# Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Control Plane registry package 现在有一个 local contract helper，用于 tenant-partitioned mutation validation。

这不会暴露新的 HTTP endpoint，也不会改变 production import/replace behavior。它证明了后续 hosted project mutation endpoint 在 replace registry rows 前必须满足的 partition diff rules。

## 已实现

- 增加 `ValidateProjectPartitionMutation(current, proposed, projectID)`。
- 增加 `ProjectPartitionMutationDecision` evidence，包含：
  - `partition_project_id`
  - `operation=registry.project_partition_replace`
  - changed object counts
  - rejected object counts
  - stable violation records
  - proposed/previous registry fingerprints
  - partition diff fingerprint
  - snapshot-boundary-change marker
- 增加 stable partition violation error behavior：
  - `REGISTRY_PARTITION_VIOLATION`
  - `scope=caller`
  - `retryable=false`
- 保持 existing full-registry validation before partition decisions。
- missing project scope 继续 fail-closed 为 `AUTHZ_DENIED`。
- 没有 `metadata.owner_project_id` 的 provider rows 被视为 platform-owned。
- 只有 ownership metadata 匹配 principal project 时，才允许 project-owned provider changes。
- 拒绝 provider ownership transfer。
- 拒绝 global capability、routing policy 和 snapshot config changes。
- 增加 project-isolated partition requests 的 idempotency fingerprint coverage。

## Contract Tests

已覆盖：

- same-project project row update passes
- same-project API key metadata update passes
- same-project credential metadata update passes
- caller-owned provider metadata update passes
- other project row change fails
- other project API key deletion fails
- other project credential metadata change fails
- platform credential metadata change fails
- global capability change fails
- global routing policy change fails
- active snapshot config change fails
- platform-owned provider change fails
- provider ownership transfer fails
- new provider without ownership fails
- invalid proposed registry fails before partition mutation
- missing project scope fails with `AUTHZ_DENIED`
- same raw idempotency key is isolated by project scope

## Validation

已通过：

```text
go test ./internal/registry
```

Go test 目录：

```text
services/control-plane
```

## 保持不做的事项

未新增 public CRUD、public project/user/role CRUD、OAuth/OIDC integration、invitation/login/session lifecycle、production gateway deployment、durable hosted permission store、provider onboarding workflow、marketplace、vault、billing、workflow runtime、automatic snapshot export/publish/reload 或 Data Plane mutable table reads。

## 下一项建议任务

```text
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness Closeout + Phase Review v0
```
