# Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring 实现报告 v0

日期：2026-06-02

状态：complete

## 摘要

local hosted admin gateway harness 现在可以把 internal hosted permission read model 作为 permission source 使用。

本 slice 仍保持 public auth 为 local/dogfood scope：gateway 把 public principal 映射为非 secret 的 hosted subject ref，通过一个很小的 local Go lookup helper 调用 `HostedPermissionReadModel.Resolve`，再把 read-model decision 转成 private Control Plane 已使用的 gateway-issued trusted headers。static fixture mode 仍保留为 focused unit-test fallback。

没有新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、decision persistence，或 Data Plane mutable Control Plane table reads。

## 已实现

新增 local lookup helper：

```text
services/control-plane/cmd/api2agent-hosted-permission-gateway-lookup/main.go
```

该 helper 会：

- 使用 pgx 打开 Postgres DSN。
- 接收 public-principal evidence、external subject ref、project context、token id、required permission 和 resolved-at。
- 调用 `registry.NewHostedPermissionReadModel(db).Resolve`。
- 输出 gateway-compatible JSON decision。
- 不接收 raw public bearer tokens。

更新 hosted admin gateway dogfood harness：

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
```

harness 现在包含：

- `GatewayPermissionSource` protocol。
- 给现有测试使用的 `StaticFixturePermissionSource`。
- 给 live Postgres dogfood 使用的 `HostedReadModelPermissionSource`。
- live gateway dogfood database 中的 hosted permission seed rows。
- trusted header injection 前的 read-model-backed gateway decisions。
- missing membership、suspended membership、revoked grant、no active policy、ambiguous active policy、readonly denial、Control Plane second gate、audit/idempotency safety 和 zero decision persistence 的 live checks。

同时更新了 Postgres schema，使 hosted permission project references 为 deferrable。这样 registry import/replace 可以在同一事务里删除并重插同一个 project，同时保留 hosted permission rows 作为独立 read-side boundary。

## Dogfood Artifact

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-read-model-gateway-runtime-wiring/report.json
```

观察结果：

- `status=passed`
- `missing_public_auth_status=401`
- `invalid_public_auth_status=401`
- `permission_source_unavailable_status=503`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `ambiguous_policy_status=503`
- `readonly_validate_status=200`
- `readonly_import_status=403`
- `readonly_partition_status=403`
- `insufficient_forward_status=403`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `import_status=201`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`
- `audit_counts.hosted_permission_decisions=0`

gateway-local failures 没有创建 Control Plane audit 或 idempotency rows。trusted-header spoofing、public bearer tokens 和 gateway secrets 没有泄漏到 audit/idempotency/report evidence。

## 验证

已通过：

```text
gofmt -w services/control-plane/cmd/api2agent-hosted-permission-gateway-lookup/main.go
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./cmd/api2agent-hosted-permission-gateway-lookup ./internal/registry -run HostedPermission
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-read-model-gateway-runtime-wiring/report.json
```

## 下一项建议任务

```text
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Closeout + Phase Review v0
```
