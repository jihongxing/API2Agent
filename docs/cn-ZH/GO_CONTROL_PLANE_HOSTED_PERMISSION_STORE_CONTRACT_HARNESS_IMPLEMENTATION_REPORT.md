# Go Control Plane Hosted Permission Store Contract Harness Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

hosted admin gateway contract harness 现在会先通过 durable permission-store-shaped local read model 解析 public principals，然后才 forward 到 private Control Plane。

这没有新增 production permission database、public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic snapshot publish/reload 或 Data Plane mutable Control Plane table reads。

## 已实现

- 将 direct static token-to-permission lookup 替换为 local hosted permission store fixture。
- 增加 store-shaped entities：
  - `PublicPrincipal`
  - `HostedSubject`
  - `HostedProjectMembership`
  - `HostedRoleBinding`
  - `HostedPermissionGrant`
  - `HostedPermissionStore`
- gateway decisions 现在通过以下路径解析：

```text
public principal
  -> hosted subject
  -> project membership
  -> role bindings
  -> permission grants
  -> gateway permission decision
```

- 增加 non-secret permission evidence：
  - `policy_source`
  - `policy_version`
  - `policy_fingerprint`
  - `decision_id`
  - `required_permission`
- 增加只作为 metadata forward 的 evidence headers：
  - `X-API2Agent-Permission-Source`
  - `X-API2Agent-Policy-Version`
  - `X-API2Agent-Policy-Fingerprint`
  - `X-API2Agent-Permission-Decision-ID`
- 保持 trusted gateway header stripping 和 gateway-issued trusted claim injection。
- 保持 Control Plane endpoint permission checks 作为第二道 authorization gate。
- 保持 project-scoped partition mutation permission：

```text
control_plane.registry.project_partition_replace
```

## Failure Semantics

harness 现在证明这些 gateway-local fail-closed behavior：

- missing public authorization：`401 PUBLIC_AUTH_REQUIRED`
- invalid public principal：`401 PUBLIC_AUTH_INVALID`
- permission store unavailable：`503 PERMISSION_SOURCE_UNAVAILABLE`
- missing project membership：`403 PUBLIC_AUTHZ_DENIED`
- suspended project membership：`403 PUBLIC_AUTHZ_DENIED`
- revoked permission grant：`403 PUBLIC_AUTHZ_DENIED`
- stale policy view：`503 PERMISSION_SOURCE_UNAVAILABLE`
- endpoint permission absence：`403 PUBLIC_AUTHZ_DENIED`
- unknown route：`404 PUBLIC_ROUTE_NOT_FOUND`
- unsupported method：`405 PUBLIC_METHOD_NOT_ALLOWED`

Gateway-local denials 不会被 forward，也不会创建 Control Plane audit 或 idempotency rows。

## Contract Tests

已覆盖：

- admin principal 通过 hosted permission store fixture 解析
- readonly principal 可以 validate，但不能 import/replace
- missing public auth 和 invalid public auth 本地失败
- permission source unavailable 本地失败
- missing membership 本地失败
- suspended membership 本地失败
- revoked permission removes access
- stale policy view fail closed
- forwarded headers strip caller-controlled identity 并注入 trusted claims
- safe policy evidence headers 被注入
- 当前六个 hosted admin routes 都映射到显式 permissions

## Dogfood Evidence

现有 live dogfood script 现在记录：

- hosted permission source id
- policy version
- policy fingerprint
- decision ids
- required permissions
- unavailable-store、missing-membership、suspended-membership、revoked-permission 和 stale-policy statuses
- gateway-local denials 后 Control Plane audit row counts 不变
- insufficient trusted permissions 的 Control Plane second-gate denial
- secret-safe audit/idempotency evidence

Raw public tokens、gateway secrets、session tokens 和 vault material 仍不会出现在 report artifacts 中。

Live dogfood artifact：

```text
.dogfood/go-control-plane-hosted-permission-store-contract-harness/report.json
```

观测结果：

- `status=passed`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `import_status=201`
- `audit_counts.registry_revisions=3`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-store-contract-harness/report.json
```

Go test 目录：

```text
services/control-plane
```

## 保持不做的事项

未新增 production permission store schema、public role CRUD、user CRUD、invitation flow、OAuth/OIDC provider integration、session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic snapshot propagation、registry behavior change 或 Data Plane mutable table read。

## 下一项建议任务

```text
Go Control Plane Hosted Permission Store Contract Harness Closeout + Phase Review v0
```
