# Go Control Plane Hosted Admin Identity Boundary Closeout + Phase Review v0

日期：2026-05-31

状态：complete

## 决策

Hosted Admin Identity Boundary slice 可以关闭。

Go Control Plane 现在已经为现有 private admin endpoints 具备 hosted-ready identity boundary：

```text
request
  -> resolved AdminPrincipal
  -> endpoint permission check
  -> principal-derived audit identity
  -> principal-derived idempotency scope
```

推荐下一项任务：

```text
Go Control Plane Hosted Admin Authenticator Integration Design v0
```

这应该是 design task。该 slice 不增加 public CRUD、hosted user login、provider onboarding、vault、billing、marketplace、workflow runtime 或 automatic snapshot propagation。

## What Is Now Complete

### Design

已完成：

- admin principal shape
- local/private compatibility rules
- hosted-mode trust boundary
- endpoint permission names
- auth/authz error mapping
- audit identity mapping
- idempotency project/actor derivation
- implementation test requirements

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_DESIGN.md`

### Implementation

已完成：

- `registry.AdminPrincipal`
- current admin endpoints 的稳定 permission constants
- `httpapi.AdminAuthenticator` seam
- 显式 identity modes：
  - `local_private`
  - `hosted`
- local/private bearer-token principal resolution
- local/private `X-Actor-ID` compatibility
- hosted mode 没有 injected authenticator 时 fail closed
- 在 endpoint body parsing 和 mutation side effects 前做 permission checks
- audit rows 使用 `principal.ActorID`
- audit metadata 记录 subject、project、organization、auth method、token id 和 local/private mode
- import/replace idempotency scope 使用 principal-derived `ProjectID` 和 `ActorID`
- service flag/env wiring：`--admin-identity-mode` / `API2AGENT_CONTROL_PLANE_ADMIN_IDENTITY_MODE`

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| local/private behavior 保持兼容 | passed |
| local/private blank actor 默认是 `admin` | passed |
| local/private nonblank `X-Actor-ID` 映射为 actor id | passed |
| local/private project scope 是 `control_plane` | passed |
| hosted mode 不信任 caller-supplied `X-Actor-ID` | passed |
| hosted mode 不把 public project/organization headers 当作 identity | passed |
| missing permission 在 mutation 前返回 `403 AUTHZ_DENIED` | passed |
| hosted mode 没有 authenticator 时返回 `503 AUTH_SERVICE_UNAVAILABLE` | passed |
| malformed hosted identity 可以返回 `401 AUTH_ERROR` | passed |
| audit actor 来自 resolved principal | passed |
| audit metadata 记录 project 和 auth method | passed |
| import/replace idempotency scope 使用 principal project 和 actor | passed |
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

这个 slice 已完成。

Control Plane 现在有了正确的 hosted identity 内部边界，虽然还没有真实 hosted verifier。这个区别很重要：

- HTTP layer 不再把 authorization 当作 raw boolean
- admin actions 现在运行在 principal 下
- permissions 在 endpoint boundary 被检查
- audit 和 idempotency 在 hosted mode 下不再依赖 arbitrary public actor headers
- local/private dogfood 保持兼容

这已经足够避免后续 write surfaces 围绕错误 identity abstraction 生长。

## Remaining Risks

### 还没有真实 Hosted Verifier

`AdminAuthenticator` 是 seam，不是 hosted identity product。

目前没有 OAuth/OIDC verifier、hosted admin token verifier、user/session store、trusted gateway deployment 或 invitation/login model。

### Standalone CLI Server 还不能真正使用 Hosted Mode

`serve` command 可以选择 `--admin-identity-mode hosted`，但 standalone binary 不注入 hosted authenticator。它会正确 fail closed。

后续 embedding 或 server configuration slice 必须决定真实 hosted authenticator 如何 wiring。

### Project Scope 仍是 Identity Metadata，不是 Registry Partitioning

`ProjectID` 现在会 scope idempotency records，但 registry mutation primitive 仍然是 full-registry replacement。

还没有 tenant-partitioned registry mutation model。

### Permission Source 尚未实现

Endpoint permissions 已检查，但 v0 只从 resolved principal 接收 permissions。

下一项 design 必须定义 hosted permissions 如何 issue、verify、refresh 和 audit。

### Trusted Gateway Headers 尚未实现

design 命名了 internal gateway headers，但这次 implementation 刻意不直接接受 public 或 gateway identity headers。

这应该等 gateway stripping 和 trust boundaries 被设计后再实现。

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
Go Control Plane Hosted Admin Authenticator Integration Design v0
```

原因：

- Control Plane 已有 authenticator seam，但还没有具体 hosted identity source
- hosted mode 当前在没有 injected authenticator 时 fail closed
- 增加更多 hosted write surfaces 前，permissions 需要 issuance and verification model
- trusted gateway headers 在 implementation 前需要 stripping/injection trust model
- audit metadata 已有 subject、project、org、auth method 和 token id 字段，但需要指定来源

预期 design scope：

- 选择 v0 hosted identity source：
  - in-process hosted admin token verifier，或
  - trusted gateway claims，或
  - 两者都支持但 deployment modes 明确
- 定义 trusted internal header names 和 public-header stripping assumptions
- 定义 token/session id audit behavior，且不存 secrets
- 定义 permission issuance and check semantics
- 定义 project and organization claim requirements
- 定义 local/private compatibility rules
- 定义后续 implementation slice 的 failure semantics 和 tests

该任务不包含：

- public CRUD
- end-user signup/login UI
- OAuth provider integration implementation
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime
