# Go Control Plane Hosted Admin Identity Boundary Closeout + Phase Review v0

Date: 2026-05-31

Status: complete

## Decision

The Hosted Admin Identity Boundary slice can close.

The Go Control Plane now has a hosted-ready identity boundary for existing private admin endpoints:

```text
request
  -> resolved AdminPrincipal
  -> endpoint permission check
  -> principal-derived audit identity
  -> principal-derived idempotency scope
```

Recommended next task:

```text
Go Control Plane Hosted Admin Authenticator Integration Design v0
```

That should be a design task. Do not add public CRUD, hosted user login, provider onboarding, vault, billing, marketplace, workflow runtime, or automatic snapshot propagation in that slice.

## What Is Now Complete

### Design

Completed:

- admin principal shape
- local/private compatibility rules
- hosted-mode trust boundary
- endpoint permission names
- auth/authz error mapping
- audit identity mapping
- idempotency project/actor derivation
- implementation test requirements

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_DESIGN.md`

### Implementation

Completed:

- `registry.AdminPrincipal`
- stable permission constants for current admin endpoints
- `httpapi.AdminAuthenticator` seam
- explicit identity modes:
  - `local_private`
  - `hosted`
- local/private bearer-token principal resolution
- local/private `X-Actor-ID` compatibility
- hosted fail-closed behavior when no authenticator is injected
- permission checks before endpoint body parsing and mutation side effects
- audit rows using `principal.ActorID`
- audit metadata for subject, project, organization, auth method, token id, and local/private mode
- import/replace idempotency scope using principal-derived `ProjectID` and `ActorID`
- service flag/env wiring for `--admin-identity-mode` / `API2AGENT_CONTROL_PLANE_ADMIN_IDENTITY_MODE`

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| local/private behavior remains compatible | passed |
| local/private blank actor defaults to `admin` | passed |
| local/private nonblank `X-Actor-ID` maps to actor id | passed |
| local/private project scope is `control_plane` | passed |
| hosted mode does not trust caller-supplied `X-Actor-ID` | passed |
| hosted mode does not use public project/organization headers as identity | passed |
| missing permission returns `403 AUTHZ_DENIED` before mutation | passed |
| hosted mode without authenticator returns `503 AUTH_SERVICE_UNAVAILABLE` | passed |
| malformed hosted identity can return `401 AUTH_ERROR` | passed |
| audit actor comes from resolved principal | passed |
| audit metadata records project and auth method | passed |
| import/replace idempotency scope uses principal project and actor | passed |
| no public CRUD, vault, billing, marketplace, workflow, provider onboarding, or automatic propagation is added | passed |

## Validation

Passed:

```text
go test ./...
```

Directory:

```text
services/control-plane
```

## Closeout Judgment

This slice is complete.

The Control Plane now has the correct internal boundary for hosted identity, even though it does not yet have a real hosted verifier. That distinction matters:

- the HTTP layer no longer treats authorization as a raw boolean
- admin actions now run under a principal
- permissions are checked at the endpoint boundary
- audit and idempotency no longer depend on arbitrary public actor headers in hosted mode
- local/private dogfood remains compatible

The implementation is enough to prevent the next write surfaces from growing around the wrong identity abstraction.

## Remaining Risks

### No Real Hosted Verifier Exists Yet

`AdminAuthenticator` is a seam, not a hosted identity product.

There is no OAuth/OIDC verifier, hosted admin token verifier, user/session store, trusted gateway deployment, or invitation/login model.

### Hosted Mode Cannot Be Used By The Standalone CLI Server Yet

The `serve` command can select `--admin-identity-mode hosted`, but the standalone binary does not inject a hosted authenticator. That correctly fails closed.

A later embedding or server configuration slice must decide how a real hosted authenticator is wired.

### Project Scope Is Still Identity Metadata, Not Registry Partitioning

`ProjectID` now scopes idempotency records, but the registry mutation primitive is still full-registry replacement.

There is no tenant-partitioned registry mutation model yet.

### Permission Source Is Not Implemented

Endpoint permissions are checked, but v0 only receives permissions from the resolved principal.

The next design must define how hosted permissions are issued, verified, refreshed, and audited.

### Trusted Gateway Headers Are Not Implemented

The design named internal gateway headers, but this implementation intentionally does not accept any public or gateway identity headers by itself.

That should remain deferred until gateway stripping and trust boundaries are designed.

## Still Not Allowed

Do not start:

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

The next highest-signal task is:

```text
Go Control Plane Hosted Admin Authenticator Integration Design v0
```

Why:

- the Control Plane has an authenticator seam, but no concrete hosted identity source
- hosted mode currently fails closed without an injected authenticator
- permissions need an issuance and verification model before more hosted write surfaces exist
- trusted gateway headers require a stripping/injection trust model before implementation
- audit metadata now has fields for subject, project, org, auth method, and token id, but their source must be specified

Expected design scope:

- choose v0 hosted identity source:
  - in-process hosted admin token verifier, or
  - trusted gateway claims, or
  - both with explicit deployment modes
- define trusted internal header names and public-header stripping assumptions
- define token/session id audit behavior without storing secrets
- define permission issuance and check semantics
- define project and organization claim requirements
- define local/private compatibility rules
- define failure semantics and tests for the later implementation slice

Out of scope for that task:

- public CRUD
- end-user signup/login UI
- OAuth provider integration implementation
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime
