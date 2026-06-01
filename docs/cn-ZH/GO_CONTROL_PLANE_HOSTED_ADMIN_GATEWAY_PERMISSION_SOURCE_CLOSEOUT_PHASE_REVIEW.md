# Go Control Plane Hosted Admin Gateway Permission Source Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Hosted Admin Gateway Permission Source implementation slice 可以关闭。

仓库现在已经在 local dogfood harness 中证明 hosted admin gateway permission-source boundary：

```text
public dogfood bearer token
  -> gateway-local permission source
  -> GatewayPermissionDecision
  -> endpoint permission mapping
  -> unauthorized 时本地 deny before forwarding
  -> gateway-issued trusted X-API2Agent-* claims
  -> Control Plane trusted-gateway authenticator
  -> Control Plane endpoint permission check
  -> Postgres audit/idempotency evidence
```

推荐下一项任务：

```text
Go Control Plane Tenant-Partitioned Registry Mutation Design v0
```

该任务应设计 hosted project identity 如何约束 registry mutation scope。不要实现 OAuth/OIDC、public CRUD、invitation/login/session lifecycle、provider onboarding、marketplace、vault、billing、workflow runtime、production gateway deployment、automatic propagation，或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Design

已完成：

- gateway-side permission source contract
- static dogfood policy shape
- public principal 到 trusted role/permission 的映射
- 5 个现有 admin endpoints 的 endpoint permission mapping
- fail-closed gateway-local auth/authz semantics
- Control Plane second-gate expectations
- secret-safe audit/idempotency evidence requirements
- local dogfood plan 和 non-goals

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_DESIGN.md`

### Implementation

已完成：

- local gateway harness 中的显式 `GatewayPermissionDecision` data
- static dogfood permission source，包含 `policy_source`、`policy_version`、roles、project scope 和 permissions
- public bearer token 解析为 trusted project-scoped admin claims
- public `Authorization` 只在 gateway 本地消费
- caller-supplied public/trusted identity headers 被 strip
- permission-source approval 后才注入 gateway-issued trusted headers
- endpoint mapping 覆盖：
  - `POST /v1/admin/registry/validate`
  - `POST /v1/admin/registry/import-replace`
  - `POST /v1/admin/snapshots/export-artifact`
  - `GET /v1/admin/distribution/current`
  - `POST /v1/admin/distribution/publish`
- typed gateway-local failures：
  - `PUBLIC_AUTH_REQUIRED`
  - `PUBLIC_AUTH_INVALID`
  - `PERMISSION_SOURCE_UNAVAILABLE`
  - `PUBLIC_AUTHZ_DENIED`
  - `PUBLIC_ROUTE_NOT_FOUND`
  - `PUBLIC_METHOD_NOT_ALLOWED`
- forced insufficient trusted-permission proof，证明 Control Plane 仍返回 `403 AUTHZ_DENIED`
- regression tests 覆盖 permission decisions、failure typing、trusted header injection、public header stripping 和 endpoint permission mapping

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| permission-source contract 已文档化 | passed |
| permission-source contract 已在 local gateway harness 实现 | passed |
| static dogfood policy 将 public principals 映射为 trusted roles 和 permissions | passed |
| gateway 在 forwarding 前推导 endpoint required permissions | passed |
| gateway 在触达 Control Plane 前 deny unauthorized public requests | passed |
| gateway-local denial 不创建 Control Plane audit/idempotency rows | passed |
| Control Plane endpoint permission check 仍是第二道 authoritative gate | passed |
| forced insufficient trusted permissions 返回 Control Plane `403 AUTHZ_DENIED` | passed |
| audit 和 idempotency evidence 仍基于 trusted claims | passed |
| raw public tokens 和 gateway secret 未出现在 evidence artifacts | passed |
| static policy 被明确标记为 dogfood-only，不是 production auth | passed |
| 未新增 OAuth/OIDC、public CRUD、marketplace、provider onboarding、vault、billing、workflow runtime、automatic propagation 或 Data Plane mutable-table reads | passed |

## Dogfood 证据

Live dogfood artifact：

```text
.dogfood/go-control-plane-hosted-admin-gateway-permission-source/report.json
```

观察结果：

- `status=passed`
- `admin_audit_events=3`
- `idempotency_records=1`
- missing public auth 返回 `401 PUBLIC_AUTH_REQUIRED`
- invalid public auth 返回 `401 PUBLIC_AUTH_INVALID`
- permission source unavailable 返回 `503 PERMISSION_SOURCE_UNAVAILABLE`
- readonly validate 成功
- readonly import/replace 在本地返回 `403 PUBLIC_AUTHZ_DENIED`
- unsupported path 在本地返回 `404 PUBLIC_ROUTE_NOT_FOUND`
- unsupported method 在本地返回 `405 PUBLIC_METHOD_NOT_ALLOWED`
- forced insufficient trusted permissions 到达 Control Plane，并返回 `403 AUTHZ_DENIED`
- gateway-local denied paths 未创建 Control Plane audit/idempotency rows
- audit rows 和 idempotency rows 使用 trusted gateway principal/project/actor/token evidence
- raw public tokens 和 gateway secret 未出现在 audit、idempotency 或 report evidence

## Validation

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-admin-gateway-permission-source/report.json
git diff --check
```

Go test 目录：

```text
services/control-plane
```

## Closeout Judgment

这个 implementation slice 已完成。

Permission source v0 满足 design acceptance criteria，是一个 local hosted gateway proof：

- public credentials 只在 gateway boundary 被解释
- trusted role 和 permission claims 由 gateway 签发，不来自 caller-supplied headers
- endpoint permission mapping 在 private forwarding 前发生
- local auth/authz failures fail closed，且不触达 Control Plane audit/idempotency state
- Control Plane 在 trusted-gateway authentication 后仍作为第二道 gate 保持权威
- dogfood artifacts 中的 secret/token evidence 保持 redacted

Static permission source 足以作为 v0，因为这个 slice 的目的在于 trust-boundary proof，而不是 production hosted authorization。在 durable hosted permission store 和真实 public identity lifecycle 设计前，它必须继续被描述为 dogfood-only。

## Remaining Risks

### Static Permission Source Only

Policy 位于 local dogfood harness。它证明了 shape、mapping、failure semantics 和 evidence，但不是 durable hosted authorization。

### No Real Public Identity Lifecycle

目前仍没有 OAuth/OIDC provider、login、session、invitation、public user lifecycle 或 public role-management surface。

### Tenant-Partitioned Mutation Is Still Unresolved

Trusted `project_id` 会 scope audit 和 idempotency rows，但 registry import/replace 仍是 full-registry replacement。下一项最高风险设计缺口是按 tenant/project 约束 hosted mutation scope。

### No Production Gateway Deployment

Gateway 仍是 local dogfood tooling。Production routing、TLS、WAF/rate limits、private network enforcement、observability 和 operational rollout 仍是未来工作。

### Durable Permission Store Is Future Work

真实 product authorization 之前仍需要 persistent hosted permission store。该设计应在 tenant mutation boundaries 之后进行，避免在 mutation scope 安全之前暗示 public role CRUD。

### No Automatic Propagation Was Added

Import/replace 仍与 snapshot export、distribution publish 和 Data Plane reload 分离。

## Still Not Allowed

不要开始：

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

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Tenant-Partitioned Registry Mutation Design v0
```

原因：

- hosted identity、trusted gateway auth、gateway contract behavior 和 gateway permission-source issuance 已在本地证明
- 最大剩余 hosted risk 是 project-scoped principal 一旦被授权，仍可驱动 full-registry replacement
- tenant-partitioned mutation design 可以先定义 project/provider/capability ownership boundaries，而不增加 public CRUD
- mutation scope 明确之后，再设计 durable permission storage 和 production gateway deployment 会更稳

预期 design scope：

- registry entities 的 tenant/project ownership model
- hosted admin import/replace 或未来更窄 mutation APIs 的 allowed mutation envelope
- tenant-partitioned changes 的 audit/idempotency scope
- conflict 和 cross-tenant rejection semantics
- scoped mutation 后的 snapshot export/publish boundaries
- 从 full-registry replacement 迁移到 tenant-scoped mutation 的路径
- 后续 implementation slice 的 test 和 dogfood requirements

Out of scope：

- OAuth/OIDC implementation
- public CRUD implementation
- production gateway deployment
- provider onboarding
- marketplace
- credential vault
- billing
- workflow runtime
- automatic publish/reload
- Data Plane mutable Control Plane table reads
