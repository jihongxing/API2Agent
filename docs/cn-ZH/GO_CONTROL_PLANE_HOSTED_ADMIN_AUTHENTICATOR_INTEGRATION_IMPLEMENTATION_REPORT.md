# Go Control Plane Hosted Admin Authenticator Integration Implementation Report v0

日期：2026-05-31

状态：complete

## Summary

已经为 Go Control Plane 实现第一版具体 hosted admin authenticator integration。

本实现增加 `trusted_gateway` authenticator mode。Hosted mode 下，Control Plane 只有在验证 internal gateway authorization secret 后，才接受 trusted `X-API2Agent-*` identity claims。

本实现不增加 public CRUD、hosted signup/login、OAuth/OIDC verification、provider onboarding、vault、billing、marketplace、workflow runtime、automatic snapshot propagation 或 Data Plane reads from mutable Control Plane tables。

## What Changed

- 增加 `AdminAuthenticatorModeTrustedGateway`。
- 增加 `TrustedGatewayAuthenticator`。
- 增加 service fields：
  - `AdminAuthenticatorMode`
  - `TrustedGatewaySecret`
- 增加 service flags 和 environment variables：
  - `--admin-authenticator`
  - `API2AGENT_CONTROL_PLANE_ADMIN_AUTHENTICATOR`
  - `--trusted-gateway-secret`
  - `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET`
- 将 `serve` command 的 `--admin-token` requirement 收窄到 local/private authenticator mode。
- 增加 internal gateway authorization header：

```text
X-API2Agent-Gateway-Authorization: Bearer <trusted-gateway-secret>
```

- 增加 trusted claim headers：
  - `X-API2Agent-Principal-ID`
  - `X-API2Agent-Actor-ID`
  - `X-API2Agent-Project-ID`
  - `X-API2Agent-Organization-ID`
  - `X-API2Agent-Token-ID`
  - `X-API2Agent-Roles`
  - `X-API2Agent-Permissions`
- 增加 claim validation、comma-separated role/permission parsing、conservative length limits 和 control-character rejection。
- 增加 gateway-secret hashes 的 constant-time comparison。
- 保持 local/private default behavior 不变。

## Runtime Behavior

Trusted gateway mode 通过以下配置启用：

```text
--admin-identity-mode hosted
--admin-authenticator trusted_gateway
--trusted-gateway-secret <secret>
```

非法组合 fail closed：

```text
503 AUTH_SERVICE_UNAVAILABLE
```

Gateway auth failures 和 malformed claims 返回：

```text
401 AUTH_ERROR
```

Valid gateway identity 但缺少 endpoint permission 返回：

```text
403 AUTHZ_DENIED
```

## Principal Mapping

Trusted gateway claims 映射为：

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

如果 `X-API2Agent-Actor-ID` 缺失，`ActorID` 默认等于 `SubjectID`。

Public `X-Actor-ID`、`X-Project-ID` 和 `X-Organization-ID` headers 继续不可信，不影响 resolved principal。

## Tests Added

- trusted gateway validation 使用 trusted claims 写 audit identity
- public identity headers 在 trusted gateway mode 下被忽略
- trusted gateway import/replace 将 principal project 和 actor 传入 mutation options
- actor claim 缺失时 actor 默认等于 principal id
- missing server-side gateway secret 返回 `503 AUTH_SERVICE_UNAVAILABLE`
- missing gateway authorization 返回 `401 AUTH_ERROR`
- malformed gateway authorization 返回 `401 AUTH_ERROR`
- wrong gateway secret 返回 `401 AUTH_ERROR`
- missing principal id 返回 `401 AUTH_ERROR`
- missing project id 返回 `401 AUTH_ERROR`
- missing permissions 返回 `401 AUTH_ERROR`
- malformed permissions 返回 `401 AUTH_ERROR`
- missing endpoint permission 返回 `403 AUTHZ_DENIED`
- invalid admin authenticator mode combinations fail closed
- gateway secret 不进入 audit metadata
- hosted/trusted-gateway serve mode 不要求 local/private admin token

## Validation

已通过：

```text
go test ./...
```

目录：

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Hosted Admin Authenticator Integration Closeout + Phase Review v0
```

closeout 应 review trusted-gateway semantics、local/private compatibility、remaining hosted-auth risks，以及增加更多 hosted write surfaces 前的下一道 gate。
