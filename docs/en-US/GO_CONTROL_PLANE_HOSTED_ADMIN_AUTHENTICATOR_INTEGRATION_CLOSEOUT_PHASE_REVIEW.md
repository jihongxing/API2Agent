# Go Control Plane Hosted Admin Authenticator Integration Closeout + Phase Review v0

Date: 2026-05-31

Status: complete

## Decision

The Hosted Admin Authenticator Integration implementation slice can close.

The Go Control Plane now has a concrete hosted admin identity source for existing private admin endpoints:

```text
trusted gateway secret
  -> trusted X-API2Agent-* claims
  -> AdminPrincipal
  -> endpoint permission check
  -> principal-derived audit and idempotency identity
```

Recommended next task:

```text
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0
```

That dogfood should run the local Control Plane service in hosted/trusted-gateway mode and exercise real HTTP requests against the service process.

## What Is Now Complete

### Design

Completed:

- `trusted_gateway` selected as the v0 hosted authenticator mode
- gateway authentication header defined
- trusted claim headers defined
- public-header stripping assumptions documented
- principal mapping documented
- claim validation and permission parsing documented
- audit and idempotency mapping documented
- auth/authz error semantics documented
- implementation tests named

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_DESIGN.md`

### Implementation

Completed:

- `TrustedGatewayAuthenticator`
- `AdminAuthenticatorModeTrustedGateway`
- `AdminAuthenticatorModeLocalPrivate`
- `Handler.AdminAuthenticatorMode`
- `Handler.TrustedGatewaySecret`
- `--admin-authenticator`
- `API2AGENT_CONTROL_PLANE_ADMIN_AUTHENTICATOR`
- `--trusted-gateway-secret`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET`
- hosted/trusted-gateway serve mode without local/private `--admin-token`
- gateway authorization validation
- trusted claim parsing and validation
- role/permission parsing
- constant-time comparison over gateway-secret hashes
- fail-closed invalid mode combinations
- HTTP regression tests

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| trusted gateway authenticator is implemented | passed |
| hosted/trusted-gateway mode requires a gateway secret | passed |
| missing gateway authorization returns `401 AUTH_ERROR` | passed |
| wrong gateway secret returns `401 AUTH_ERROR` | passed |
| malformed trusted claims return `401 AUTH_ERROR` | passed |
| missing endpoint permission returns `403 AUTHZ_DENIED` | passed |
| trusted claims map to `AdminPrincipal` | passed |
| actor defaults to principal id when actor claim is absent | passed |
| public identity headers remain untrusted | passed |
| audit actor comes from trusted gateway principal | passed |
| audit metadata includes subject, project, organization, auth method, token id, and `local_private=false` | passed |
| gateway secret is absent from audit metadata | passed |
| import/replace idempotency scope uses trusted gateway project and actor | passed |
| local/private default behavior remains compatible | passed |
| hosted/trusted-gateway `serve` does not require local/private admin token | passed |
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

This implementation slice is complete.

The Control Plane is no longer limited to an abstract hosted authenticator seam. It can now resolve a hosted admin principal from a trusted gateway request in a fail-closed way. The core hosted-auth boundary is still intentionally narrow:

- no public identity header is trusted without gateway authorization
- no raw gateway secret enters audit metadata
- no hosted user/login/OAuth system is introduced
- no new mutation surface is added

That is the right amount of implementation for this stage.

## Remaining Risks

### Not Yet Dogfooded As A Running Service

The behavior is covered by Go tests, but the hosted/trusted-gateway flags and headers have not yet been exercised through a running `api2agent-controlplane serve` process.

The next task should start the service and call it over HTTP with trusted gateway headers.

### No Real Gateway Exists Yet

The Control Plane can validate a gateway secret and claims, but the repository does not include a real public edge or gateway that authenticates users and strips public headers.

The dogfood should simulate gateway output only. A production gateway remains a later deployment concern.

### Secret Rotation Is Not Implemented

Only one gateway secret is configured.

Hosted deployments will need rotation, overlap windows, revocation, and secret storage policy.

### Permission Issuance Is Still External

The Control Plane checks permissions, but it does not issue or persist them.

The trusted gateway is responsible for generating permission claims.

### Project Scope Is Still Mutation Metadata

`ProjectID` now scopes idempotency and audit metadata, but registry mutation is still full-registry replacement.

Tenant-partitioned registry mutation remains future work.

### No Automatic Propagation Was Added

Import/replace remains separated from snapshot export, publish, and Data Plane reload.

That separation remains intentional.

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
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0
```

Why:

- the authenticator is implemented and unit-tested
- runtime flag wiring should be exercised through the real service process
- hosted/trusted-gateway mode should be proven without `--admin-token`
- audit metadata and import/replace identity scope should be verified through HTTP
- auth failure behavior should be observed through real HTTP responses

Expected dogfood scope:

- start Control Plane service in hosted/trusted-gateway mode
- call `POST /v1/admin/registry/validate` with trusted gateway headers
- call at least one admin endpoint without gateway auth and verify `401 AUTH_ERROR`
- call at least one admin endpoint with missing permission and verify `403 AUTHZ_DENIED`
- if Postgres is available, call import/replace and verify principal-derived `project_id` / `actor_id` in idempotency records
- verify no local/private admin token is required in hosted/trusted-gateway mode
- verify local/private mode remains documented but unchanged

Out of scope for that task:

- real external gateway deployment
- OAuth/OIDC provider integration
- public CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime
