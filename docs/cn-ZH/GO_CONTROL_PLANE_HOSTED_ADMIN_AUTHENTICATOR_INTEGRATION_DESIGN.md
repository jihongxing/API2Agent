# Go Control Plane Hosted Admin Authenticator Integration Design v0

日期：2026-05-31

状态：complete

## 决策

Go Control Plane 第一版具体 hosted identity integration 采用 trusted-gateway admin authenticator。

Control Plane 只有在内部 gateway authentication secret 验证通过后，才接受 hosted admin identity claims。Public clients 不能直接设置 actor、project、organization、role 或 permission claims。

该 design 被接受后的推荐下一项任务：

```text
Go Control Plane Hosted Admin Authenticator Integration Implementation v0
```

## Why This Is Next

Control Plane 现在已经有：

- `registry.AdminPrincipal`
- endpoint permission checks
- principal-derived audit identity
- principal-derived import/replace idempotency scope
- hosted mode 在没有 authenticator 时 fail closed

缺失的一块是具体 hosted identity source。最小安全来源是 trusted gateway：

1. 在 Control Plane 外部认证 external caller；
2. strip public identity headers；
3. inject verified internal claims；
4. 用 internal secret 向 Control Plane 认证自己。

## Goals

- 定义第一版 hosted `AdminAuthenticator` implementation mode
- 定义 required configuration
- 定义 trusted gateway headers
- 定义 public-header stripping assumptions
- 定义 claim validation 和 permission parsing
- 定义 principal mapping
- 定义 auth/authz failure semantics
- 定义 audit 和 secret-handling rules
- 命名 implementation tests

## Non-Goals

- no public registry CRUD APIs
- no end-user signup, login, invitation, or UI
- no OAuth/OIDC implementation in the Control Plane
- no user database or session store
- no provider onboarding
- no marketplace provider submission
- no credential vault writes
- no plaintext secret storage
- no billing or settlement state
- no workflow engine
- no automatic snapshot export, publish, or Data Plane reload
- no Data Plane reads from mutable Control Plane tables

## Integration Mode

增加一个 hosted authenticator mode：

```text
trusted_gateway
```

这个 mode 只有在以下条件都成立时有效：

```text
AdminIdentityMode = hosted
AdminAuthenticatorMode = trusted_gateway
TrustedGatewaySecret is non-empty
```

Local/private mode 保持不变，继续使用现有 local admin token authenticator。

## Configuration

推荐 service flags 和 environment variables：

| Purpose | Flag | Environment |
| --- | --- | --- |
| identity mode | `--admin-identity-mode` | `API2AGENT_CONTROL_PLANE_ADMIN_IDENTITY_MODE` |
| authenticator mode | `--admin-authenticator` | `API2AGENT_CONTROL_PLANE_ADMIN_AUTHENTICATOR` |
| trusted gateway secret | `--trusted-gateway-secret` | `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET` |

允许的 authenticator modes：

| Mode | Valid identity mode | Meaning |
| --- | --- | --- |
| empty | `local_private` | 使用 local bearer admin token behavior |
| `local_private` | `local_private` | 显式 local bearer admin token behavior |
| `trusted_gateway` | `hosted` | 验证 gateway secret 后信任 internal gateway claims |

非法组合必须 fail closed。

## Trusted Gateway Authentication

Gateway 使用以下 header 向 Control Plane 认证自己：

```text
X-API2Agent-Gateway-Authorization: Bearer <trusted-gateway-secret>
```

规则：

- missing gateway authorization 返回 `401 AUTH_ERROR`
- malformed gateway authorization 返回 `401 AUTH_ERROR`
- wrong gateway secret 返回 `401 AUTH_ERROR`
- server-side `TrustedGatewaySecret` 缺失返回 `503 AUTH_SERVICE_UNAVAILABLE`
- gateway secret 绝不能写入 audit metadata、idempotency metadata、logs 或 errors
- implementation 应使用 fixed hashes 做 constant-time comparison

普通 public `Authorization` header 在 trusted-gateway mode 下不由 Control Plane 使用。它属于 public edge 或 gateway。

## Trusted Claim Headers

Gateway secret 验证通过后，Control Plane 可以读取这些 internal headers：

| Header | Required | Maps To |
| --- | --- | --- |
| `X-API2Agent-Principal-ID` | yes | `AdminPrincipal.SubjectID` |
| `X-API2Agent-Actor-ID` | optional | `AdminPrincipal.ActorID` |
| `X-API2Agent-Project-ID` | yes | `AdminPrincipal.ProjectID` |
| `X-API2Agent-Organization-ID` | optional | `AdminPrincipal.OrganizationID` |
| `X-API2Agent-Token-ID` | optional | `AdminPrincipal.TokenID` |
| `X-API2Agent-Roles` | optional | `AdminPrincipal.Roles` |
| `X-API2Agent-Permissions` | yes | `AdminPrincipal.Permissions` |

`X-API2Agent-Actor-ID` 缺失时，`ActorID` 默认等于 `SubjectID`。

Resolved principal 必须使用：

```text
AuthMethod = trusted_gateway
LocalPrivate = false
```

## Header Trust Boundary

Public edge 必须在 inject trusted claims 前 strip 所有带 internal prefix 的 incoming headers：

```text
X-API2Agent-*
```

Control Plane 仍然必须在读取任何 claim header 前要求有效的 `X-API2Agent-Gateway-Authorization`。

Public caller headers 继续不可信：

- `X-Actor-ID`
- `X-Project-ID`
- `X-Organization-ID`
- `X-API2Agent-*` without valid gateway authorization

它们不能成为 `ActorID`、`ProjectID`、`OrganizationID`、roles 或 permissions。

## Claim Validation

Required claims：

- `X-API2Agent-Principal-ID`
- `X-API2Agent-Project-ID`
- `X-API2Agent-Permissions`

Validation rules：

- trim surrounding whitespace
- reject empty required claims
- reject claims over a conservative length limit
- reject control characters
- reject permission entries that are empty after trimming
- roles 和 permissions 用 comma split
- trim 每个 role 和 permission
- unknown permission names 作为 strings 保留，但如果缺少 endpoint required permission，handler 会 deny

推荐保守 limits：

| Value | Limit |
| --- | ---: |
| subject, actor, project, organization, token id | 256 bytes |
| each role or permission | 256 bytes |
| total roles | 32 |
| total permissions | 128 |
| raw header value | 8192 bytes |

Malformed claims 返回：

```text
401 AUTH_ERROR caller retryable=false
```

Valid gateway auth 但缺少 endpoint permission 返回：

```text
403 AUTHZ_DENIED caller retryable=false
```

现有 handler-level permission check 继续作为最终 enforcement point。

## Principal Mapping

给定 trusted gateway claims，构造：

```go
registry.AdminPrincipal{
    SubjectID:      principalID,
    ActorID:        actorIDOrPrincipalID,
    ProjectID:      projectID,
    OrganizationID: organizationID,
    AuthMethod:     registry.AdminAuthMethodTrustedGateway,
    TokenID:        tokenID,
    Roles:          roles,
    Permissions:    permissions,
    LocalPrivate:   false,
}
```

不要把 raw public access tokens 或 gateway secrets 放入 `AdminPrincipal`。

## Audit Mapping

保留现有 audit mapping：

```text
actor_id = principal.ActorID
```

Audit metadata 应包含：

- `principal_subject_id`
- `project_id`
- `organization_id` when present
- `auth_method=trusted_gateway`
- `token_id` when present
- `local_private=false`

不要写入：

- gateway secret
- public bearer token
- raw cookies
- raw authorization headers

## Idempotency Mapping

保留现有 mapping：

```text
ProjectID = principal.ProjectID
ActorID = principal.ActorID
```

这意味着同一个 `Idempotency-Key` 会按以下 scope 独立：

```text
project_id + actor_id + operation + idempotency_key_hash
```

## HTTP Error Mapping

使用现有 error envelope。

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| trusted gateway mode lacks server-side secret | 503 | `AUTH_SERVICE_UNAVAILABLE` | platform | true |
| missing gateway authorization | 401 | `AUTH_ERROR` | caller | false |
| malformed gateway authorization | 401 | `AUTH_ERROR` | caller | false |
| wrong gateway secret | 401 | `AUTH_ERROR` | caller | false |
| missing required trusted claim | 401 | `AUTH_ERROR` | caller | false |
| malformed trusted claim | 401 | `AUTH_ERROR` | caller | false |
| principal lacks endpoint permission | 403 | `AUTHZ_DENIED` | caller | false |

Error messages 不能包含 secrets 或 raw authorization header values。

## Implementation Shape

建议 HTTP package 增加：

```go
type TrustedGatewayAuthenticator struct {
    GatewaySecret string
}

func (a TrustedGatewayAuthenticator) ResolveAdminPrincipal(
    r *http.Request,
    requiredPermission string,
) (registry.AdminPrincipal, error)
```

推荐 handler wiring：

```text
AdminIdentityMode=hosted
AdminAuthenticatorMode=trusted_gateway
  -> Handler.Authenticator = TrustedGatewayAuthenticator{GatewaySecret: secret}
```

不要把 gateway parsing 放到 registry-layer code。Registry code 应继续只接收 `AdminPrincipal` 和 mutation options。

## Tests Required For Implementation

HTTP/authenticator tests：

- trusted gateway mode without server-side secret returns `503 AUTH_SERVICE_UNAVAILABLE`
- missing gateway authorization returns `401 AUTH_ERROR`
- wrong gateway secret returns `401 AUTH_ERROR`
- malformed gateway authorization returns `401 AUTH_ERROR`
- missing principal id returns `401 AUTH_ERROR`
- missing project id returns `401 AUTH_ERROR`
- missing permissions returns `401 AUTH_ERROR`
- malformed role/permission list returns `401 AUTH_ERROR`
- valid gateway claims resolve `AdminPrincipal`
- actor defaults to principal id when actor header is absent
- explicit actor header maps to `ActorID`
- public `X-Actor-ID`, `X-Project-ID`, and `X-Organization-ID` are ignored
- required endpoint permission is enforced before mutation

Audit/idempotency tests：

- audit actor comes from trusted gateway principal
- audit metadata includes subject, project, organization, auth method, token id, and `local_private=false`
- gateway secret is absent from audit metadata
- import/replace options use trusted gateway project and actor
- same idempotency key can be reused independently across two trusted gateway projects

Runtime wiring tests：

- `--admin-authenticator trusted_gateway` requires `--admin-identity-mode hosted`
- hosted/trusted-gateway mode requires `--trusted-gateway-secret`
- local/private default remains compatible
- invalid mode combinations fail closed

Regression tests：

- no public CRUD is added
- no snapshot export/publish/reload coupling is added
- Data Plane still consumes immutable snapshots only
- local bearer-token behavior remains unchanged

## Acceptance Criteria

这个 design 被接受的条件：

- trusted gateway 被选为 v0 hosted authenticator integration mode
- gateway authentication 和 claim headers 已文档化
- public-header stripping 和 internal-header trust assumptions 已文档化
- principal mapping 已文档化
- permission parsing 和 enforcement semantics 已文档化
- audit 和 idempotency mappings 已文档化
- error mapping 已文档化
- implementation tests 已命名
- public CRUD、vault、billing、marketplace、workflow、provider onboarding 和 automatic propagation 继续 out of scope
