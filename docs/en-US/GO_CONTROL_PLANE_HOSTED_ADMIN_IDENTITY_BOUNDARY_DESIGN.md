# Go Control Plane Hosted Admin Identity Boundary Design v0

Date: 2026-05-31

Status: complete

## Decision

Define a hosted admin identity boundary for private Control Plane mutation endpoints before adding more write surfaces.

The boundary introduces a resolved admin principal shape that the HTTP layer can pass into registry mutations, audit writes, and idempotency scope derivation.

This is a design task only. It does not implement a hosted identity provider, user database, organization model, public CRUD API, or new mutation endpoint.

Recommended next task after this design is accepted:

```text
Go Control Plane Hosted Admin Identity Boundary Implementation v0
```

## Why This Is Next

The current private admin API is safe enough for local dogfood, but it is not a hosted identity model:

- `Authorization: Bearer <admin-token>` proves only possession of a shared local token.
- `X-Actor-ID` is caller supplied and must not be trusted in hosted mode.
- idempotency records currently default `project_id` to `control_plane`.
- admin audit rows need stable principal attribution before more mutation endpoints exist.
- future permission checks must exist before public or hosted write surfaces expand.

## Goals

- define the admin principal fields used by the Control Plane
- define local/private compatibility behavior
- define hosted-mode actor and project derivation
- define endpoint permission names
- define audit identity mapping
- define idempotency `project_id` and `actor_id` derivation
- define stable auth/authz error mapping
- name implementation tests for a later slice

## Non-Goals

- no public registry CRUD APIs
- no hosted user signup, login, invitation, or UI
- no OAuth/OIDC integration implementation
- no provider self-onboarding
- no marketplace provider submission
- no credential vault writes
- no plaintext secret storage
- no billing or settlement state
- no workflow engine
- no automatic snapshot export, publish, or Data Plane reload
- no Data Plane reads from mutable Control Plane tables

## Modes

The Control Plane should support two explicit admin identity modes.

| Mode | Purpose | Actor source | Project source |
| --- | --- | --- | --- |
| `local_private` | current local dogfood and private service use | `X-Actor-ID` or `admin` after bearer token auth | `control_plane` |
| `hosted` | future hosted Control Plane | authenticated principal | authenticated principal or trusted gateway claims |

The mode must be explicit service configuration. Hosted behavior must not be inferred from the presence of arbitrary headers.

## Admin Principal Shape

The HTTP layer should resolve requests into:

```go
type AdminPrincipal struct {
    SubjectID    string
    ActorID      string
    ProjectID    string
    OrganizationID string
    AuthMethod   string
    TokenID      string
    Roles        []string
    Permissions  []string
    LocalPrivate bool
}
```

Field meaning:

| Field | Required | Meaning |
| --- | --- | --- |
| `SubjectID` | hosted yes, local optional | Stable authenticated subject, for example user/service-account id. |
| `ActorID` | yes | Audit actor and idempotency actor scope. |
| `ProjectID` | yes | Mutation and idempotency project scope. |
| `OrganizationID` | hosted optional | Tenant grouping above project. |
| `AuthMethod` | yes | `local_admin_token`, `hosted_admin_token`, `trusted_gateway`, or later provider-specific method. |
| `TokenID` | optional | Non-secret token/session identifier for audit correlation. |
| `Roles` | optional | Coarse labels such as `control_plane_admin`. |
| `Permissions` | yes | Fine-grained permission names checked by endpoint. |
| `LocalPrivate` | yes | True only for local/private compatibility mode. |

`ActorID` must be stable and must not contain raw bearer tokens, raw API keys, emails unless explicitly normalized, or provider secrets.

## Local Private Compatibility

Current local behavior remains valid in `local_private` mode:

- `Authorization: Bearer <admin-token>` is required.
- missing or invalid bearer token returns `401 AUTH_ERROR`.
- `X-Actor-ID` may override the local actor id.
- blank `X-Actor-ID` defaults to `admin`.
- `ProjectID` defaults to `control_plane`.
- `AuthMethod` is `local_admin_token`.
- `Permissions` include all current private admin endpoint permissions.

This keeps existing dogfood scripts and local service use working.

Local compatibility must be explicit. A hosted deployment must not enable `X-Actor-ID` trust by accident.

## Hosted Mode Rules

In `hosted` mode:

- `X-Actor-ID` is not trusted as identity.
- public clients cannot set `ProjectID`, `ActorID`, roles, or permissions through arbitrary headers.
- the Control Plane receives identity from one of:
  - an in-process hosted admin token verifier, or
  - a trusted gateway that strips public identity headers and injects verified internal claims
- the resolved principal must include `ActorID`, `ProjectID`, and endpoint permissions before a mutation handler runs.

If a hosted request includes `X-Actor-ID`, the service should either ignore it or record it as untrusted request metadata. It must not become `ActorID`.

If trusted gateway headers are used later, they must use an internal namespace such as:

```text
X-API2Agent-Principal-ID
X-API2Agent-Project-ID
X-API2Agent-Organization-ID
X-API2Agent-Permissions
```

Those headers are only valid after gateway verification and public-header stripping. They are not accepted from the public edge directly.

## Permission Names

Use fine-grained permission strings.

| Endpoint | Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |

For v0, a local private admin token grants all of these permissions.

Hosted mode must check the required permission before parsing or executing mutation bodies where possible.

## HTTP Error Mapping

Use the existing error envelope.

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| Missing/invalid credentials | 401 | `AUTH_ERROR` | caller | false |
| Valid principal lacks permission | 403 | `AUTHZ_DENIED` | caller | false |
| Principal has no project scope | 403 | `AUTHZ_DENIED` | caller | false |
| Trusted gateway identity header is malformed | 401 | `AUTH_ERROR` | caller | false |
| Identity verifier unavailable | 503 | `AUTH_SERVICE_UNAVAILABLE` | platform | true |

Do not return `404` to hide private admin endpoints in local/private mode. These endpoints are already behind admin auth and currently use explicit auth errors.

## Audit Mapping

Admin audit events should use:

```text
actor_id = principal.ActorID
```

Required audit metadata additions:

- `principal_subject_id`
- `project_id`
- `organization_id` when available
- `auth_method`
- `token_id` when available
- `local_private=true|false`

Existing action/resource/outcome/error fields remain unchanged.

Hosted mode must not write caller-supplied `X-Actor-ID` as the audit actor.

## Idempotency Mapping

`registry.ImportReplaceOptions` already has:

```go
ProjectID string
ActorID   string
```

Identity resolution must populate:

```text
ProjectID = principal.ProjectID
ActorID   = principal.ActorID
```

Local/private compatibility:

```text
ProjectID = control_plane
ActorID   = X-Actor-ID or admin
```

Hosted mode:

```text
ProjectID = authenticated project scope
ActorID   = authenticated principal actor id
```

This keeps idempotency records scoped to the tenant/project and authenticated actor, not a caller supplied actor header.

## Handler Shape

Recommended HTTP seam:

```go
type AdminAuthenticator interface {
    ResolveAdminPrincipal(r *http.Request, requiredPermission string) (registry.AdminPrincipal, error)
}
```

The handler should:

1. Check method.
2. Resolve principal and permission.
3. Validate request identity headers such as `X-Request-ID` and `Idempotency-Key`.
4. Parse and validate body.
5. Pass principal-derived `ProjectID` and `ActorID` into registry-layer options.

For endpoints that only write service-level audit evidence, the same principal should feed audit rows.

## Registry Package Shape

The registry package can own the shared struct to avoid HTTP-only identity types leaking inconsistently:

```go
type AdminPrincipal struct {
    SubjectID      string
    ActorID        string
    ProjectID      string
    OrganizationID string
    AuthMethod     string
    TokenID        string
    Roles          []string
    Permissions    []string
    LocalPrivate   bool
}
```

`ImportReplaceOptions` should continue to carry only the fields the mutation primitive needs:

- `ProjectID`
- `ActorID`
- `RequestID`
- `IdempotencyKey`
- `Source`

Do not pass raw auth tokens into registry-layer mutation options.

## Security Rules

- Hosted mode must fail closed if identity cannot be resolved.
- Hosted mode must not trust `X-Actor-ID`.
- Hosted mode must not trust public `X-Project-ID` or `X-Organization-ID`.
- Trusted gateway headers must be stripped at the edge before injection.
- Raw bearer tokens must not be written to audit, idempotency records, or error messages.
- Permission denial must occur before mutation side effects.
- Request replay must use idempotency scope derived from the resolved principal.

## Tests Required For Implementation

HTTP/auth tests:

- local mode still accepts bearer admin token
- local mode maps blank `X-Actor-ID` to `admin`
- local mode maps nonblank `X-Actor-ID` to actor id
- hosted mode ignores or rejects caller-supplied `X-Actor-ID`
- hosted mode requires a resolved principal
- hosted mode returns `403 AUTHZ_DENIED` when permission is missing
- hosted mode passes principal `ProjectID` and `ActorID` into `ImportReplaceOptions`
- malformed trusted gateway identity returns `401 AUTH_ERROR`

Audit/idempotency tests:

- admin audit actor comes from resolved principal
- audit metadata includes project and auth method
- idempotency scope uses principal project and actor
- same idempotency key can be reused independently by different project scopes
- raw auth tokens are absent from audit and idempotency metadata

Regression tests:

- local dogfood behavior remains compatible
- private admin import/replace still requires `X-Request-ID`
- private admin import/replace still requires `Idempotency-Key`
- file-store mutation remains unavailable
- no snapshot export, publish, or Data Plane reload is added

## Acceptance Criteria

This design is accepted when:

- admin principal shape is documented
- local/private compatibility behavior is documented
- hosted-mode identity trust rules are documented
- endpoint permission names are documented
- audit identity mapping is documented
- idempotency identity mapping is documented
- error mapping is documented
- implementation tests are named
- public CRUD, vault, billing, marketplace, workflow, provider onboarding, and automatic propagation remain out of scope
