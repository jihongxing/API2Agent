# Go Control Plane Hosted Admin Authenticator Integration Closeout + Phase Review v0

日期：2026-05-31

状态：complete

## 决策

Hosted Admin Authenticator Integration implementation slice 可以关闭。

Go Control Plane 现在已经为现有 private admin endpoints 提供具体 hosted admin identity source：

```text
trusted gateway secret
  -> trusted X-API2Agent-* claims
  -> AdminPrincipal
  -> endpoint permission check
  -> principal-derived audit and idempotency identity
```

推荐下一项任务：

```text
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0
```

该 dogfood 应用 hosted/trusted-gateway mode 启动 local Control Plane service，并对真实 service process 发 HTTP requests。

## What Is Now Complete

### Design

已完成：

- `trusted_gateway` 被选为 v0 hosted authenticator mode
- gateway authentication header 已定义
- trusted claim headers 已定义
- public-header stripping assumptions 已文档化
- principal mapping 已文档化
- claim validation 和 permission parsing 已文档化
- audit 和 idempotency mapping 已文档化
- auth/authz error semantics 已文档化
- implementation tests 已命名

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_DESIGN.md`

### Implementation

已完成：

- `TrustedGatewayAuthenticator`
- `AdminAuthenticatorModeTrustedGateway`
- `AdminAuthenticatorModeLocalPrivate`
- `Handler.AdminAuthenticatorMode`
- `Handler.TrustedGatewaySecret`
- `--admin-authenticator`
- `API2AGENT_CONTROL_PLANE_ADMIN_AUTHENTICATOR`
- `--trusted-gateway-secret`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET`
- hosted/trusted-gateway serve mode 不需要 local/private `--admin-token`
- gateway authorization validation
- trusted claim parsing and validation
- role/permission parsing
- gateway-secret hashes 的 constant-time comparison
- fail-closed invalid mode combinations
- HTTP regression tests

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| trusted gateway authenticator 已实现 | passed |
| hosted/trusted-gateway mode 要求 gateway secret | passed |
| missing gateway authorization 返回 `401 AUTH_ERROR` | passed |
| wrong gateway secret 返回 `401 AUTH_ERROR` | passed |
| malformed trusted claims 返回 `401 AUTH_ERROR` | passed |
| missing endpoint permission 返回 `403 AUTHZ_DENIED` | passed |
| trusted claims 映射到 `AdminPrincipal` | passed |
| actor claim 缺失时 actor 默认等于 principal id | passed |
| public identity headers 保持不可信 | passed |
| audit actor 来自 trusted gateway principal | passed |
| audit metadata 包含 subject、project、organization、auth method、token id 和 `local_private=false` | passed |
| gateway secret 不进入 audit metadata | passed |
| import/replace idempotency scope 使用 trusted gateway project 和 actor | passed |
| local/private default behavior 保持兼容 | passed |
| hosted/trusted-gateway `serve` 不要求 local/private admin token | passed |
| 未增加 public CRUD、vault、billing、marketplace、workflow、provider onboarding 或 automatic propagation | passed |

## Validation

已通过：

```text
go test ./...
```

目录：

```text
services/control-plane
```

## Closeout Judgment

这个 implementation slice 已完成。

Control Plane 已经不只是拥有抽象 hosted authenticator seam。它现在可以用 fail-closed 方式从 trusted gateway request 解析 hosted admin principal。核心 hosted-auth boundary 仍然刻意保持狭窄：

- 没有 gateway authorization 时，不信任 public identity header
- raw gateway secret 不进入 audit metadata
- 没有引入 hosted user/login/OAuth system
- 没有增加新的 mutation surface

这是当前阶段合适的实现范围。

## Remaining Risks

### 还没有作为 Running Service Dogfood

行为已有 Go tests 覆盖，但 hosted/trusted-gateway flags 和 headers 还没有通过运行中的 `api2agent-controlplane serve` process 验证。

下一项任务应该启动 service，并用 trusted gateway headers 通过 HTTP 调用。

### 还没有真实 Gateway

Control Plane 可以验证 gateway secret 和 claims，但仓库里还没有真实 public edge 或 gateway 来认证用户并 strip public headers。

dogfood 只应模拟 gateway output。Production gateway 仍是之后的 deployment concern。

### Secret Rotation 尚未实现

当前只配置一个 gateway secret。

Hosted deployments 之后需要 rotation、overlap windows、revocation 和 secret storage policy。

### Permission Issuance 仍在外部

Control Plane 会检查 permissions，但不会 issue 或 persist permissions。

Trusted gateway 负责生成 permission claims。

### Project Scope 仍是 Mutation Metadata

`ProjectID` 现在会 scope idempotency 和 audit metadata，但 registry mutation 仍是 full-registry replacement。

Tenant-partitioned registry mutation 仍是 future work。

### 没有增加 Automatic Propagation

Import/replace 继续和 snapshot export、publish、Data Plane reload 分离。

这个分离仍然是刻意保留。

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
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0
```

原因：

- authenticator 已实现并有 unit tests
- runtime flag wiring 应通过真实 service process 验证
- hosted/trusted-gateway mode 应证明不需要 `--admin-token`
- audit metadata 和 import/replace identity scope 应通过 HTTP 验证
- auth failure behavior 应通过真实 HTTP responses 观察

预期 dogfood scope：

- 以 hosted/trusted-gateway mode 启动 Control Plane service
- 带 trusted gateway headers 调用 `POST /v1/admin/registry/validate`
- 不带 gateway auth 调用至少一个 admin endpoint，并验证 `401 AUTH_ERROR`
- 缺少 permission 调用至少一个 admin endpoint，并验证 `403 AUTHZ_DENIED`
- 如果 Postgres 可用，调用 import/replace 并验证 idempotency records 中的 principal-derived `project_id` / `actor_id`
- 验证 hosted/trusted-gateway mode 不要求 local/private admin token
- 验证 local/private mode 保持文档化且未改变

该任务不包含：

- real external gateway deployment
- OAuth/OIDC provider integration
- public CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime
