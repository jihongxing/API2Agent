# Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Live Dogfood + Closeout v0

日期：2026-06-01

状态：complete

## 决策

Tenant-Partitioned Registry Mutation Private Endpoint implementation slice 可以关闭。

Live dogfood 已通过，环境包含真实 Control Plane service process、local hosted gateway harness 和 live Postgres。

## Dogfood Artifact

```text
.dogfood/go-control-plane-tenant-partition-private-endpoint/report.json
```

观测结果：

- `status=passed`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `partition_violation_error_type=REGISTRY_PARTITION_VIOLATION`
- `readonly_partition_status=403`
- `readonly_partition_error_type=PUBLIC_AUTHZ_DENIED`
- `registry_revisions=3`
- `admin_audit_events=5`
- `idempotency_records=2`

## Evidence

dogfood 证明：

- hosted gateway 将 `POST /v1/admin/registry/project-partition/replace` 映射到 `control_plane.registry.project_partition_replace`
- readonly public policy 在 gateway-local 被拒绝，不转发
- trusted gateway admin policy 携带 project-scoped claims 到达 Control Plane
- same-project partition mutation 成功
- idempotency replay 返回 `200` 且 `replayed=true`
- cross-project/global mutation 被 Control Plane 拒绝为 `403 REGISTRY_PARTITION_VIOLATION`
- partition success audit 包含 `partition_project_id`、`partition_diff_fingerprint` 和 changed counts
- partition failure audit 包含 failure outcome 和 partition evidence
- idempotency rows 分别按 `registry.project_partition_replace` 和 `registry.import_replace` scoped
- audit/idempotency evidence 不包含 raw public tokens、gateway secrets 或 spoofed trusted identity

## Validation

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-tenant-partition-private-endpoint/report.json
git diff --check
```

Go test directory：

```text
services/control-plane
```

## Closeout Judgment

该 endpoint 满足 v0 design：

- method/path 已实现
- trusted-gateway-only principal requirement 已强制
- local/private principals 被拒绝
- broad import/replace permission 不足以通过
- project scope 只来自 trusted principal
- partition validation 在 registry-layer write transaction 内执行
- partition violations 不会变成 public CRUD semantics
- audit 和 idempotency evidence 已持久化
- snapshot export、publish 和 Data Plane reload 仍然是 manual

## Remaining Risks

- Provider ownership 在 v0 仍基于 metadata。
- Durable hosted permission storage 仍是 future work。
- Production gateway deployment 仍是 future work。
- Project row mutation policy 仍然有意保持 narrow，public project-management surfaces 前应重新审视。
- Full import/replace 仍存在于 operator administration，必须继续避免进入 hosted public mutation path。

## Still Not Allowed

不要启动：

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation/login/session lifecycle
- real production gateway deployment
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Recommended Next Task

```text
Go Control Plane Hosted Permission Store Design v0
```

既然 project-scoped mutation 已被约束并完成 dogfood，下一项 hosted-readiness gap 是设计 durable permission store，用它替换 static dogfood permission source，同时不要过早加入 public role CRUD。
