# Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Closeout + Phase Review v0

日期：2026-05-31

状态：complete

## 决策

Hosted Admin Trusted Gateway Service Dogfood slice 可以关闭。

Go Control Plane 已经通过真实 service process 证明 hosted admin authenticator：

```text
api2agent-controlplane serve
  -> hosted identity mode
  -> trusted_gateway authenticator
  -> trusted X-API2Agent-* claims
  -> endpoint permission check
  -> Postgres audit and idempotency evidence
```

推荐下一项任务：

```text
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0
```

该任务应先设计 production gateway boundary，不应提前实现真实 public edge、OAuth/OIDC integration、public CRUD、provider onboarding、vault、billing、marketplace、workflow runtime 或 automatic propagation。

## What Is Now Complete

### Authenticator Implementation

已完成：

- `trusted_gateway` hosted admin authenticator mode
- internal gateway authorization header
- trusted claim header parsing
- endpoint execution 前的 permission checks
- hosted/trusted-gateway serve mode 不需要 local/private `--admin-token`
- fail-closed invalid mode handling
- local/private compatibility

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_IMPLEMENTATION_REPORT.md`

### Service Dogfood

已完成：

- build `api2agent-controlplane`
- 用 `--admin-identity-mode hosted` 启动 service
- 用 `--admin-authenticator trusted_gateway` 启动 service
- 用 `--trusted-gateway-secret` 启动 service
- 刻意不传 `--admin-token`
- 验证 public `/healthz`
- 通过 HTTP 验证 trusted gateway validation success
- 验证 missing gateway auth 返回 `401 AUTH_ERROR`
- 验证 missing permission 返回 `403 AUTHZ_DENIED`
- 验证 trusted gateway import/replace 返回 `201`
- 验证 Postgres audit rows 包含 trusted principal evidence
- 验证 idempotency row 使用 trusted gateway project 和 actor scope
- 验证 gateway secret 不进入 audit metadata

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`

### Dogfood Fix

第一次 dogfood run 发现一个 integration gap：Postgres import/replace audit metadata 没有包含完整 hosted principal evidence。

已修复：

- `registry.ImportReplaceOptions` 现在携带 subject、project、organization、auth method、token id 和 local/private status。
- HTTP import/replace 会把 resolved `AdminPrincipal` 映射进这些 options。
- Postgres import/replace audit metadata 会在存在时持久化 hosted principal evidence。
- Regression tests 覆盖 hosted/trusted-gateway import/replace evidence propagation。

这正是本次 dogfood 应该捕捉的问题。

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| service 能以 hosted/trusted-gateway mode 启动 | passed |
| hosted/trusted-gateway service start 不需要 `--admin-token` | passed |
| `/healthz` 保持 public | passed |
| trusted gateway headers 可以调用 `POST /v1/admin/registry/validate` | passed |
| public `Authorization` 和 `X-Actor-ID` 不会覆盖 trusted claims | passed |
| missing gateway authorization 返回 `401 AUTH_ERROR` | passed |
| missing endpoint permission 返回 `403 AUTHZ_DENIED` | passed |
| trusted gateway import/replace 返回 `201` | passed |
| audit rows 使用 trusted actor 和 principal metadata | passed |
| audit metadata 不包含 gateway secret | passed |
| idempotency row 使用 trusted gateway project 和 actor scope | passed |
| idempotency row 链接到 registry revision 和 admin audit event | passed |
| local/private behavior 保持兼容 | passed |
| 未增加 public CRUD、vault、billing、marketplace、workflow、provider onboarding 或 automatic propagation | passed |

## Validation

已通过：

```text
python -m py_compile scripts\go_control_plane_hosted_admin_gateway_dogfood.py
python scripts\go_control_plane_hosted_admin_gateway_dogfood.py --output tmp\go_control_plane_hosted_admin_gateway_dogfood.json
go test ./...
```

Go test 目录：

```text
services/control-plane
```

## Closeout Judgment

这个 dogfood slice 已完成。

现在仓库已有足够证据说明 Control Plane 侧 hosted trusted-gateway admin path 按设计工作：

- 只有先通过 gateway authentication，claims 才会被信任
- public identity headers 不会变成 admin identity
- endpoint permissions 会 gate mutation/validation behavior
- audit 和 idempotency evidence 来自 trusted claims
- service 可以在 hosted/trusted-gateway mode 下不依赖 local private admin token

Hosted admin integration 现在应该先暂停，不要扩大 product surface。下一项工作应收窄 gateway 本身的 production boundary，而不是增加 public registry APIs。

## Remaining Risks

### 还没有真实 Gateway

dogfood 只是模拟 gateway output。Production edge 仍需要 concrete contract 来处理 user authentication、header stripping、trusted claim issuance、request forwarding 和 failure behavior。

### Secret Rotation 仍缺失

Control Plane 当前接受一个配置的 gateway secret。Hosted deployment 需要 rotation、overlap windows、revocation 和 operational policy。

### Permission Issuance 仍在外部

Control Plane 会检查 permissions，但不会 issue permissions。Production gateway 或 identity service 必须定义 permission claims 如何 derive 和 constrain。

### Header Stripping 仍是 Assumption

Control Plane 会忽略 public identity headers，但真实 gateway 仍需要明确的 strip-and-rewrite contract，覆盖所有 trusted `X-API2Agent-*` headers。

### Project Scope 还不是 Tenant-Partitioned Mutation

`ProjectID` 会 scope audit 和 idempotency records，但 registry import/replace 仍是 full-registry replacement。Tenant-partitioned mutation 仍是 future work。

### 没有增加 Automatic Propagation

Import/replace 继续和 snapshot export、publish、Data Plane reload 分离。这个分离仍是刻意保留。

## Still Not Allowed

不要启动：

- public registry CRUD APIs
- provider self-onboarding
- marketplace provider submission
- credential vault writes
- plaintext secret storage
- billing or settlement state
- workflow engine support
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0
```

原因：

- Control Plane trusted-gateway behavior 已实现并完成 dogfood。
- 剩余最高风险区域在 Control Plane 外部的 production boundary。
- 先做 design 可以定义 gateway contract，而不提前实现 OAuth、public CRUD、onboarding 或 marketplace surface。
- 在真实 hosted edge 之前，应先明确 secret rotation、trusted header stripping、permission issuance 和 deployment observability。

预期 design scope：

- gateway-to-Control-Plane trust boundary
- required public header stripping and trusted header rewrite rules
- gateway secret rotation and revocation policy
- permission claim issuance assumptions
- request identity and audit evidence contract
- gateway/auth service outages 的 failure semantics
- deployment and observability expectations
- 后续 implementation slice 的 test 和 dogfood requirements

不包含：

- OAuth/OIDC provider implementation
- real public gateway deployment
- public registry CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime
