# Go Control Plane Hosted Admin Gateway Permission Source Design v0

Date: 2026-06-01

Status: complete

## Decision

The next Go Control Plane hosted-readiness implementation slice should be:

```text
Go Control Plane Hosted Admin Gateway Permission Source Implementation v0
```

This slice should define and implement a narrow local permission-source contract for the hosted admin gateway harness. The gateway should derive trusted `X-API2Agent-*` role and permission claims from an authenticated public principal and project-scoped policy source before forwarding to the private Control Plane.

The Control Plane should continue treating trusted gateway headers as gateway-issued claims after gateway authentication. The new permission source belongs at the gateway boundary, not inside public Control Plane CRUD.

## Why This Slice Now

The hosted admin path has already proven:

- local/private admin identity
- hosted admin principal shape
- trusted-gateway authenticator
- trusted gateway secret rotation and key-id evidence
- local gateway contract harness
- public trusted-header stripping
- trusted claim injection
- request id and idempotency propagation
- audit and idempotency evidence using trusted gateway principal claims

The remaining gap is permission issuance. The harness currently uses static dogfood policy. The next design should define a permission source that can later be backed by durable hosted policy without starting public CRUD, OAuth/OIDC, marketplace, vault, billing, workflow runtime, or automatic propagation.

## Current Baseline

Existing permission constants:

```text
control_plane.registry.validate
control_plane.registry.import_replace
control_plane.snapshot.export_artifact
control_plane.distribution.publish
control_plane.distribution.read_current
```

Existing trusted gateway headers:

```text
X-API2Agent-Gateway-Authorization
X-API2Agent-Gateway-Key-ID
X-API2Agent-Principal-ID
X-API2Agent-Actor-ID
X-API2Agent-Project-ID
X-API2Agent-Organization-ID
X-API2Agent-Token-ID
X-API2Agent-Roles
X-API2Agent-Permissions
```

Existing Control Plane behavior:

- validates gateway authorization before reading trusted headers
- parses trusted identity, roles, and permissions
- checks endpoint required permission with `AdminPrincipal.HasPermission`
- returns `403 AUTHZ_DENIED` when permissions are missing
- records project/auth/token/gateway metadata in audit rows
- scopes idempotency by trusted project and actor

## Goals

- define a gateway-side permission source boundary
- map public authenticated principals to trusted admin principal claims
- derive project-scoped roles and permissions deterministically
- fail closed before forwarding when permission lookup fails or denies access
- keep Control Plane endpoint permission checks authoritative as a second gate
- record non-secret permission evidence in trusted headers and audit metadata
- preserve current trusted-gateway authenticator behavior
- support local dogfood without real OAuth/OIDC
- leave room for a future persistent hosted permission store

## Non-Goals

Do not implement:

- OAuth/OIDC provider integration
- login/session/user lifecycle
- invitation management
- public project/user/role CRUD
- provider onboarding
- marketplace/provider submission
- credential vault writes
- billing or settlement
- workflow runtime
- production gateway deployment
- automatic snapshot publish/reload
- Data Plane reads from mutable Control Plane tables

## Permission Source Contract

Introduce a gateway-local contract conceptually shaped as:

```text
ResolveGatewayAdminPrincipal(public_request, endpoint_permission)
  -> GatewayPermissionDecision
```

Decision fields:

```text
allowed
deny_reason
subject_id
actor_id
project_id
organization_id
token_id
roles
permissions
policy_source
policy_version
permission_source
resolved_at
```

The implementation can keep this as Python harness data first or a small Go/Python struct where the gateway harness lives. It should not require a database in v0.

## Static v0 Policy Shape

For v0, use a local static policy file or in-memory map in the gateway harness.

Suggested shape:

```json
{
  "principals": [
    {
      "public_token": "dogfood-admin-token",
      "subject_id": "user_admin",
      "actor_id": "user_admin",
      "project_id": "project_alpha",
      "organization_id": "org_alpha",
      "token_id": "token_admin",
      "roles": ["admin"],
      "permissions": [
        "control_plane.registry.validate",
        "control_plane.registry.import_replace",
        "control_plane.snapshot.export_artifact",
        "control_plane.distribution.publish",
        "control_plane.distribution.read_current"
      ],
      "policy_version": "static-v1"
    }
  ]
}
```

The public token is dogfood-only and must not be forwarded to the Control Plane or written to evidence artifacts.

## Trust Boundary

The gateway must:

1. authenticate the public request locally
2. strip caller-supplied `X-API2Agent-*` trusted headers
3. resolve permissions from the permission source
4. check the requested endpoint permission before forwarding
5. inject only gateway-issued trusted headers
6. forward request id and idempotency key
7. replace public `Authorization` with private gateway authorization

The Control Plane must:

1. authenticate the private gateway secret
2. parse trusted headers
3. perform its existing endpoint required-permission check
4. persist audit/idempotency evidence using trusted claims

This creates two gates:

```text
gateway permission source
Control Plane endpoint permission check
```

Both must fail closed.

## Endpoint Permission Mapping

The gateway harness should map public paths and methods to the same permission constants used by Control Plane handlers:

| Method / Path | Required Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |

Unknown public admin paths should fail locally with `404` or `405` and not reach the Control Plane.

## Header Evidence Contract

Continue injecting the existing trusted headers. Add optional non-secret evidence headers only if useful:

```text
X-API2Agent-Permission-Source
X-API2Agent-Policy-Version
```

If added, Control Plane should record these as audit metadata but must not use them for authorization until explicitly implemented. The source of truth remains `X-API2Agent-Permissions` plus endpoint required-permission checks.

For v0, it is acceptable to keep policy evidence in the harness dogfood report rather than adding new Control Plane headers.

## Failure Semantics

Gateway-local failures:

| Condition | HTTP | Error Type | Forward? |
| --- | --- | --- | --- |
| missing public auth | `401` | `PUBLIC_AUTH_REQUIRED` | no |
| invalid public token | `401` | `PUBLIC_AUTH_INVALID` | no |
| permission source unavailable | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| principal missing project scope | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| principal lacks endpoint permission | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| unknown admin route | `404` | `PUBLIC_ROUTE_NOT_FOUND` | no |
| unsupported method | `405` | `PUBLIC_METHOD_NOT_ALLOWED` | no |

Control Plane failures remain:

- `401 AUTH_ERROR` for invalid trusted gateway auth
- `403 AUTHZ_DENIED` for missing trusted permissions
- `503 AUTH_SERVICE_UNAVAILABLE` for platform auth configuration failure

## Audit And Idempotency Evidence

The dogfood report should assert:

- raw public token is absent
- raw gateway secret is absent
- actor/project/organization/token id are trusted gateway outputs
- permission source id or policy version is visible in safe metadata or report evidence
- successful admin audit rows use trusted actor/project
- idempotency rows use trusted project/actor scope
- denied gateway-local requests produce no Control Plane audit/idempotency rows
- Control Plane denied requests preserve existing `AUTHZ_DENIED` behavior

## Implementation Plan

1. Extend the local hosted admin gateway harness with a permission source abstraction.
2. Add a static dogfood permission policy.
3. Resolve public bearer tokens into principal/project/role/permission claims.
4. Derive endpoint required permission from public method/path.
5. Fail locally before forwarding when auth or permission source denies.
6. Inject trusted claims only after permission source approval.
7. Preserve existing trusted header stripping and gateway secret/key-id behavior.
8. Add dogfood assertions for allowed, denied, missing, and spoofed cases.
9. Keep the Control Plane trusted-gateway authenticator unchanged unless optional safe policy evidence headers are added.

## Test Plan

Add or update tests/dogfood checks for:

- admin public token resolves to expected trusted claims
- readonly public token can validate registry but cannot import/replace
- missing public token fails locally and does not reach Control Plane
- invalid public token fails locally and does not reach Control Plane
- permission source denial fails before forwarding
- caller-supplied trusted permissions are stripped before policy resolution
- gateway-injected permissions match the static policy
- Control Plane still denies if the gateway injects insufficient permission
- audit metadata and idempotency scope use trusted claims
- raw public token and raw gateway secret are absent from report artifacts

## Dogfood Plan

Run a local hosted admin gateway contract dogfood with:

1. admin token -> registry validate succeeds
2. admin token -> import/replace succeeds
3. readonly token -> registry validate succeeds
4. readonly token -> import/replace fails locally with `403 PUBLIC_AUTHZ_DENIED`
5. spoofed trusted headers from public caller are stripped
6. missing public token fails locally with `401 PUBLIC_AUTH_REQUIRED`
7. broken permission source fails locally with `503 PERMISSION_SOURCE_UNAVAILABLE`
8. forced insufficient trusted permission reaches Control Plane and returns `403 AUTHZ_DENIED`
9. Postgres audit/idempotency evidence remains trusted-claim based

## Acceptance Criteria

- permission-source contract is documented and implemented in the local gateway harness
- static dogfood policy maps public principals to trusted roles and permissions
- gateway derives endpoint required permissions before forwarding
- gateway denies unauthorized public requests before Control Plane forwarding
- Control Plane endpoint permission check remains the second authoritative gate
- audit and idempotency evidence remains secret-safe and trusted-claim based
- no OAuth/OIDC, public CRUD, marketplace, provider onboarding, vault, billing, workflow runtime, automatic propagation, or Data Plane mutable-table reads are added

## Next Recommended Task

```text
Go Control Plane Hosted Admin Gateway Permission Source Implementation v0
```
