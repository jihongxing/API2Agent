# Go Control Plane Hosted Admin Authenticator Integration Design v0

Date: 2026-05-31

Status: complete

## Decision

Use a trusted-gateway admin authenticator as the first concrete hosted identity integration for the Go Control Plane.

The Control Plane will accept hosted admin identity claims only when an internal gateway authentication secret is valid. Public clients must not be able to set actor, project, organization, role, or permission claims directly.

Recommended next task after this design is accepted:

```text
Go Control Plane Hosted Admin Authenticator Integration Implementation v0
```

## Why This Is Next

The Control Plane now has:

- `registry.AdminPrincipal`
- endpoint permission checks
- principal-derived audit identity
- principal-derived import/replace idempotency scope
- hosted mode that fails closed without an authenticator

The missing piece is a concrete hosted identity source. The smallest safe source is a trusted gateway that:

1. authenticates the external caller outside the Control Plane,
2. strips public identity headers,
3. injects verified internal claims,
4. authenticates itself to the Control Plane with an internal secret.

## Goals

- define the first hosted `AdminAuthenticator` implementation mode
- define required configuration
- define trusted gateway headers
- define public-header stripping assumptions
- define claim validation and permission parsing
- define principal mapping
- define auth/authz failure semantics
- define audit and secret-handling rules
- name implementation tests

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

Add one hosted authenticator mode:

```text
trusted_gateway
```

This mode is valid only when:

```text
AdminIdentityMode = hosted
AdminAuthenticatorMode = trusted_gateway
TrustedGatewaySecret is non-empty
```

Local/private mode remains unchanged and continues to use the existing local admin token authenticator.

## Configuration

Recommended service flags and environment variables:

| Purpose | Flag | Environment |
| --- | --- | --- |
| identity mode | `--admin-identity-mode` | `API2AGENT_CONTROL_PLANE_ADMIN_IDENTITY_MODE` |
| authenticator mode | `--admin-authenticator` | `API2AGENT_CONTROL_PLANE_ADMIN_AUTHENTICATOR` |
| trusted gateway secret | `--trusted-gateway-secret` | `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET` |

Allowed authenticator modes:

| Mode | Valid identity mode | Meaning |
| --- | --- | --- |
| empty | `local_private` | use local bearer admin token behavior |
| `local_private` | `local_private` | explicit local bearer admin token behavior |
| `trusted_gateway` | `hosted` | verify gateway secret, then trust internal gateway claims |

Invalid combinations must fail closed.

## Trusted Gateway Authentication

The gateway authenticates itself to the Control Plane with:

```text
X-API2Agent-Gateway-Authorization: Bearer <trusted-gateway-secret>
```

Rules:

- missing gateway authorization returns `401 AUTH_ERROR`
- malformed gateway authorization returns `401 AUTH_ERROR`
- wrong gateway secret returns `401 AUTH_ERROR`
- missing server-side `TrustedGatewaySecret` returns `503 AUTH_SERVICE_UNAVAILABLE`
- the gateway secret must never be written to audit metadata, idempotency metadata, logs, or errors
- comparison should be constant-time over fixed hashes in implementation

The normal public `Authorization` header is not used by the Control Plane in trusted-gateway mode. It belongs to the public edge or gateway.

## Trusted Claim Headers

After verifying the gateway secret, the Control Plane may read these internal headers:

| Header | Required | Maps To |
| --- | --- | --- |
| `X-API2Agent-Principal-ID` | yes | `AdminPrincipal.SubjectID` |
| `X-API2Agent-Actor-ID` | optional | `AdminPrincipal.ActorID` |
| `X-API2Agent-Project-ID` | yes | `AdminPrincipal.ProjectID` |
| `X-API2Agent-Organization-ID` | optional | `AdminPrincipal.OrganizationID` |
| `X-API2Agent-Token-ID` | optional | `AdminPrincipal.TokenID` |
| `X-API2Agent-Roles` | optional | `AdminPrincipal.Roles` |
| `X-API2Agent-Permissions` | yes | `AdminPrincipal.Permissions` |

`ActorID` defaults to `SubjectID` when `X-API2Agent-Actor-ID` is absent.

The resolved principal must use:

```text
AuthMethod = trusted_gateway
LocalPrivate = false
```

## Header Trust Boundary

The public edge must strip all incoming headers with the internal prefix before injecting trusted claims:

```text
X-API2Agent-*
```

The Control Plane must still defend itself by requiring `X-API2Agent-Gateway-Authorization` before reading any claim header.

Public caller headers remain untrusted:

- `X-Actor-ID`
- `X-Project-ID`
- `X-Organization-ID`
- `X-API2Agent-*` without valid gateway authorization

They must not become `ActorID`, `ProjectID`, `OrganizationID`, roles, or permissions.

## Claim Validation

Required claims:

- `X-API2Agent-Principal-ID`
- `X-API2Agent-Project-ID`
- `X-API2Agent-Permissions`

Validation rules:

- trim surrounding whitespace
- reject empty required claims
- reject claims over a conservative length limit
- reject control characters
- reject permission entries that are empty after trimming
- split roles and permissions by comma
- trim each role and permission
- preserve unknown permission names as strings, but the handler will deny if the required endpoint permission is absent

Recommended conservative limits:

| Value | Limit |
| --- | ---: |
| subject, actor, project, organization, token id | 256 bytes |
| each role or permission | 256 bytes |
| total roles | 32 |
| total permissions | 128 |
| raw header value | 8192 bytes |

Malformed claims return:

```text
401 AUTH_ERROR caller retryable=false
```

Valid gateway auth but missing endpoint permission returns:

```text
403 AUTHZ_DENIED caller retryable=false
```

The existing handler-level permission check remains the final enforcement point.

## Principal Mapping

Given trusted gateway claims, construct:

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

Do not pass raw public access tokens or gateway secrets into `AdminPrincipal`.

## Audit Mapping

The existing audit mapping is retained:

```text
actor_id = principal.ActorID
```

Audit metadata should include:

- `principal_subject_id`
- `project_id`
- `organization_id` when present
- `auth_method=trusted_gateway`
- `token_id` when present
- `local_private=false`

Do not write:

- gateway secret
- public bearer token
- raw cookies
- raw authorization headers

## Idempotency Mapping

The existing mapping is retained:

```text
ProjectID = principal.ProjectID
ActorID = principal.ActorID
```

This means the same `Idempotency-Key` is scoped independently by:

```text
project_id + actor_id + operation + idempotency_key_hash
```

## HTTP Error Mapping

Use the existing error envelope.

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| trusted gateway mode lacks server-side secret | 503 | `AUTH_SERVICE_UNAVAILABLE` | platform | true |
| missing gateway authorization | 401 | `AUTH_ERROR` | caller | false |
| malformed gateway authorization | 401 | `AUTH_ERROR` | caller | false |
| wrong gateway secret | 401 | `AUTH_ERROR` | caller | false |
| missing required trusted claim | 401 | `AUTH_ERROR` | caller | false |
| malformed trusted claim | 401 | `AUTH_ERROR` | caller | false |
| principal lacks endpoint permission | 403 | `AUTHZ_DENIED` | caller | false |

Error messages must not include secrets or raw authorization header values.

## Implementation Shape

Recommended HTTP package additions:

```go
type TrustedGatewayAuthenticator struct {
    GatewaySecret string
}

func (a TrustedGatewayAuthenticator) ResolveAdminPrincipal(
    r *http.Request,
    requiredPermission string,
) (registry.AdminPrincipal, error)
```

Recommended handler wiring:

```text
AdminIdentityMode=hosted
AdminAuthenticatorMode=trusted_gateway
  -> Handler.Authenticator = TrustedGatewayAuthenticator{GatewaySecret: secret}
```

Do not put gateway parsing in registry-layer code. Registry code should continue to receive only `AdminPrincipal` and mutation options.

## Tests Required For Implementation

HTTP/authenticator tests:

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

Audit/idempotency tests:

- audit actor comes from trusted gateway principal
- audit metadata includes subject, project, organization, auth method, token id, and `local_private=false`
- gateway secret is absent from audit metadata
- import/replace options use trusted gateway project and actor
- same idempotency key can be reused independently across two trusted gateway projects

Runtime wiring tests:

- `--admin-authenticator trusted_gateway` requires `--admin-identity-mode hosted`
- hosted/trusted-gateway mode requires `--trusted-gateway-secret`
- local/private default remains compatible
- invalid mode combinations fail closed

Regression tests:

- no public CRUD is added
- no snapshot export/publish/reload coupling is added
- Data Plane still consumes immutable snapshots only
- local bearer-token behavior remains unchanged

## Acceptance Criteria

This design is accepted when:

- trusted gateway is selected as the v0 hosted authenticator integration mode
- gateway authentication and claim headers are documented
- public-header stripping and internal-header trust assumptions are documented
- principal mapping is documented
- permission parsing and enforcement semantics are documented
- audit and idempotency mappings are documented
- error mapping is documented
- implementation tests are named
- public CRUD, vault, billing, marketplace, workflow, provider onboarding, and automatic propagation remain out of scope
