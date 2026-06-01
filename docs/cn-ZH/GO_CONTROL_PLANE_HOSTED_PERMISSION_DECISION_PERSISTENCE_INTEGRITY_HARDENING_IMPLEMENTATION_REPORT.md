# Go Control Plane Hosted Permission Decision Persistence Integrity Hardening 实现报告 v0

日期：2026-06-02

状态：complete

## 摘要

local hosted admin gateway harness 现在会显式处理 hosted permission decision duplicate。

等价 duplicate decision evidence 会被接受为 no-op，conflicting duplicate evidence 会抛出 `PERMISSION_DECISION_INTEGRITY_CONFLICT`，allowed conflicts 会在 forwarding 前 fail closed。Denied/source-unavailable failures 仍保留原始 fail-closed caller response，同时记录 local evidence。

本次没有新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、policy write APIs、schema migration，或 Data Plane 从 mutable Control Plane tables 读取。

## 已实现

更新文件：

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
tests/test_go_control_plane_hosted_admin_gateway_contract.py
```

gateway dogfood harness 现在包含：

- persisted decision rows 的 canonical controlled-evidence comparison。
- duplicate-equivalent no-op behavior。
- conflicting duplicates 显式返回 `PERMISSION_DECISION_INTEGRITY_CONFLICT`。
- allowed-conflict 在 forwarding 前 fail closed。
- bounded local failure evidence，包含 error type 和 decision id。
- sentinel constraints，会拒绝 allowed decisions 使用 unknown subject/actor/org/policy evidence。
- equivalent duplicate 和 conflicting duplicate decisions 的 live dogfood probes。

回归覆盖现在验证：

- equivalent duplicate persistence 执行一次 insert 和一次 no-op。
- conflicting duplicate evidence 抛出 `PERMISSION_DECISION_INTEGRITY_CONFLICT`。
- allowed sentinel evidence 会被拒绝。
- source-unavailable sentinel normalization 仍可工作。
- missing/invalid public auth decisions 仍保持在 persistence 之外。

## Dogfood Artifact

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
```

观测结果：

- `status=passed`
- `audit_counts.hosted_permission_decisions=15`
- `hosted_permission_decision_rows_after_duplicate_equivalent=15`
- `hosted_permission_decision_rows_after_integrity_conflict=15`
- `integrity_conflict_status=503`
- `integrity_conflict_error_type=PERMISSION_DECISION_INTEGRITY_CONFLICT`
- `audit_rows_after_integrity_conflict=5`
- `permission_decision_duplicate_equivalent_count=1`
- `permission_decision_integrity_conflict_count=1`

live dogfood 证明 equivalent duplicates 不创建新 rows，conflicting duplicates 不修改 existing rows，allowed integrity conflicts 会在 Control Plane audit/idempotency writes 前 fail closed。

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
```

`go test ./...` 的工作目录：

```text
services/control-plane
```

## 下一项建议任务

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Closeout + Phase Review v0
```
