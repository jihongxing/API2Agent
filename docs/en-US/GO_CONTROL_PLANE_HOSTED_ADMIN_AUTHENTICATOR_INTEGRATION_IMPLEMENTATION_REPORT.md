# Go Control Plane Hosted Admin Authenticator Integration Implementation Report v0

Date: 2026-05-31

Status: complete

## Summary

Implemented the first concrete hosted admin authenticator integration for the Go Control Plane.

The implementation adds a `trusted_gateway` authenticator mode. In hosted mode, the Control Plane now accepts trusted `X-API2Agent-*` identity claims only after validating an internal gateway authorization secret.

This implementation does not add public CRUD, hosted signup/login, OAuth/OIDC verification, provider onboarding, vault, billing, marketplace, workflow runtime, automatic snapshot propagation, or Data Plane reads from mutable Control Plane tables.

## What Changed

- Added `AdminAuthenticatorModeTrustedGateway`.
- Added `TrustedGatewayAuthenticator`.
- Added service fields:
  - `AdminAuthenticatorMode`
  - `TrustedGatewaySecret`
- Added service flags and environment variables:
  - `--admin-authenticator`
  - `API2AGENT_CONTROL_PLANE_ADMIN_AUTHENTICATOR`
  - `--trusted-gateway-secret`
  - `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET`
- Scoped the `serve` command's `--admin-token` requirement to local/private authenticator mode.
- Added internal gateway authorization header:

```text
X-API2Agent-Gateway-Authorization: Bearer <trusted-gateway-secret>
```

- Added trusted claim headers:
  - `X-API2Agent-Principal-ID`
  - `X-API2Agent-Actor-ID`
  - `X-API2Agent-Project-ID`
  - `X-API2Agent-Organization-ID`
  - `X-API2Agent-Token-ID`
  - `X-API2Agent-Roles`
  - `X-API2Agent-Permissions`
- Added claim validation, comma-separated role/permission parsing, conservative length limits, and control-character rejection.
- Added constant-time comparison over gateway-secret hashes.
- Kept local/private default behavior unchanged.

## Runtime Behavior

Trusted gateway mode is enabled by configuring:

```text
--admin-identity-mode hosted
--admin-authenticator trusted_gateway
--trusted-gateway-secret <secret>
```

Invalid combinations fail closed with:

```text
503 AUTH_SERVICE_UNAVAILABLE
```

Gateway auth failures and malformed claims return:

```text
401 AUTH_ERROR
```

Valid gateway identity without the endpoint permission returns:

```text
403 AUTHZ_DENIED
```

## Principal Mapping

Trusted gateway claims map to:

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

If `X-API2Agent-Actor-ID` is absent, `ActorID` defaults to `SubjectID`.

Public `X-Actor-ID`, `X-Project-ID`, and `X-Organization-ID` headers remain untrusted and do not affect the resolved principal.

## Tests Added

- trusted gateway validation writes audit identity from trusted claims
- public identity headers are ignored in trusted gateway mode
- trusted gateway import/replace passes principal project and actor into mutation options
- actor defaults to principal id when actor claim is absent
- missing server-side gateway secret returns `503 AUTH_SERVICE_UNAVAILABLE`
- missing gateway authorization returns `401 AUTH_ERROR`
- malformed gateway authorization returns `401 AUTH_ERROR`
- wrong gateway secret returns `401 AUTH_ERROR`
- missing principal id returns `401 AUTH_ERROR`
- missing project id returns `401 AUTH_ERROR`
- missing permissions returns `401 AUTH_ERROR`
- malformed permissions returns `401 AUTH_ERROR`
- missing endpoint permission returns `403 AUTHZ_DENIED`
- invalid admin authenticator mode combinations fail closed
- gateway secret is absent from audit metadata
- hosted/trusted-gateway serve mode does not require the local/private admin token

## Validation

Passed:

```text
go test ./...
```

Directory:

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Hosted Admin Authenticator Integration Closeout + Phase Review v0
```

The closeout should review trusted-gateway semantics, local/private compatibility, residual hosted-auth risks, and the next gate before adding more hosted write surfaces.
