# Go Control Plane Hosted Permission Decision Persistence 实现报告 v0

日期：2026-06-02

状态：complete

## 摘要

local hosted admin gateway harness 现在会把非 secret hosted permission decision evidence 写入 `hosted_permission_decisions`。

写入时机是在 gateway 解析 hosted permission decision 之后、allowed request 转发到 private Control Plane 之前。missing 或 invalid public auth、unknown routes、unsupported methods 仍是 gateway-local failures，不创建 hosted decision rows。

本次没有新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、policy write APIs，或 Data Plane 从 mutable Control Plane tables 读取。

## 已实现

更新文件：

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
tests/test_go_control_plane_hosted_admin_gateway_contract.py
```

gateway dogfood harness 现在包含：

- `HostedPermissionDecisionPersistence`，用于 append-only 写入 `hosted_permission_decisions` 的 local persistence helper。
- secret-safe metadata：decision status、error type、permission source、request id、method、path、gateway key id 和 persistence version。
- source-unavailable decisions 使用的 sentinel subject 与 policy-version seed data，用于 read model 无法返回完整 evidence 的场景。
- 针对 `PUBLIC_AUTH_REQUIRED` 和 `PUBLIC_AUTH_INVALID` 的 persistence skip guard。
- allowed-decision persistence failure 会在 forwarding 前返回 `503 PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`。
- denied/source-unavailable persistence failure 会保留原始 fail-closed caller response，并记录 failure evidence。
- live dogfood 断言 row counts、status counts、required-permission counts、sentinel evidence、readonly mutation denials 和 secret leakage。

回归覆盖现在验证：

- persistence SQL 是 secret-safe，并包含预期 metadata。
- source-unavailable decisions 会把缺失 row fields 归一化为 sentinel values。
- missing/invalid public auth decisions 会被跳过，而 authenticated source-unavailable decisions 会被持久化。

## Dogfood Artifact

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
```

观测结果：

- `status=passed`
- `audit_counts.hosted_permission_decisions=15`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`
- `permission_decision_rows_after_invalid_public_auth=0`
- `persistence_unavailable_status=503`
- `persistence_unavailable_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- decision status counts：`200=7`、`403=5`、`503=3`
- required permission counts：`validate=9`、`import_replace=2`、`project_partition_replace=4`

Gateway-local auth failures 没有创建 Control Plane audit rows 或 hosted decision rows。Allowed decision persistence failure 会在 forwarding 前 fail closed。持久化后的 decision rows 不包含 public bearer tokens、caller `Authorization`/`Cookie` material 或 trusted gateway secret。

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
```

`go test ./...` 的工作目录：

```text
services/control-plane
```

## 下一项建议任务

```text
Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0
```
