# Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Closeout + Phase Review v0

Date: 2026-05-31

Status: complete

## Decision

The Hosted Admin Trusted Gateway Service Dogfood slice can close.

The Go Control Plane has now proven the hosted admin authenticator through a real service process:

```text
api2agent-controlplane serve
  -> hosted identity mode
  -> trusted_gateway authenticator
  -> trusted X-API2Agent-* claims
  -> endpoint permission check
  -> Postgres audit and idempotency evidence
```

Recommended next task:

```text
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0
```

That task should design the production gateway boundary before implementing any real public edge, OAuth/OIDC integration, public CRUD, provider onboarding, vault, billing, marketplace, workflow runtime, or automatic propagation.

## What Is Now Complete

### Authenticator Implementation

Completed:

- `trusted_gateway` hosted admin authenticator mode
- internal gateway authorization header
- trusted claim header parsing
- permission checks before endpoint execution
- hosted/trusted-gateway serve mode without local/private `--admin-token`
- fail-closed invalid mode handling
- local/private compatibility

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_IMPLEMENTATION_REPORT.md`

### Service Dogfood

Completed:

- built `api2agent-controlplane`
- started service with `--admin-identity-mode hosted`
- started service with `--admin-authenticator trusted_gateway`
- started service with `--trusted-gateway-secret`
- intentionally omitted `--admin-token`
- verified public `/healthz`
- verified trusted gateway validation success over HTTP
- verified missing gateway auth returns `401 AUTH_ERROR`
- verified missing permission returns `403 AUTHZ_DENIED`
- verified trusted gateway import/replace returns `201`
- verified Postgres audit rows include trusted principal evidence
- verified idempotency row uses trusted gateway project and actor scope
- verified gateway secret is absent from audit metadata

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`

### Dogfood Fix

The first dogfood run found an integration gap: Postgres import/replace audit metadata did not include full hosted principal evidence.

Fixed:

- `registry.ImportReplaceOptions` now carries subject, project, organization, auth method, token id, and local/private status.
- HTTP import/replace maps the resolved `AdminPrincipal` into those options.
- Postgres import/replace audit metadata persists the hosted principal evidence when present.
- Regression tests cover hosted/trusted-gateway import/replace evidence propagation.

This is exactly the kind of issue this dogfood was meant to catch.

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| service starts in hosted/trusted-gateway mode | passed |
| hosted/trusted-gateway service start does not require `--admin-token` | passed |
| `/healthz` remains public | passed |
| trusted gateway headers can call `POST /v1/admin/registry/validate` | passed |
| public `Authorization` and `X-Actor-ID` do not override trusted claims | passed |
| missing gateway authorization returns `401 AUTH_ERROR` | passed |
| missing endpoint permission returns `403 AUTHZ_DENIED` | passed |
| trusted gateway import/replace returns `201` | passed |
| audit rows use trusted actor and principal metadata | passed |
| audit metadata does not contain gateway secret | passed |
| idempotency row uses trusted gateway project and actor scope | passed |
| idempotency row links to registry revision and admin audit event | passed |
| local/private behavior remains compatible | passed |
| no public CRUD, vault, billing, marketplace, workflow, provider onboarding, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile scripts\go_control_plane_hosted_admin_gateway_dogfood.py
python scripts\go_control_plane_hosted_admin_gateway_dogfood.py --output tmp\go_control_plane_hosted_admin_gateway_dogfood.json
go test ./...
```

Go test directory:

```text
services/control-plane
```

## Closeout Judgment

This dogfood slice is complete.

The repository now has enough evidence to say the Control Plane side of the hosted trusted-gateway admin path works as designed:

- gateway authentication is enforced before claims are trusted
- public identity headers do not become admin identity
- endpoint permissions gate mutation/validation behavior
- audit and idempotency evidence are derived from trusted claims
- the service can run in hosted/trusted-gateway mode without a local private admin token

The hosted admin integration should now pause before building broader product surface. The next work should narrow the production boundary around the gateway itself, not add public registry APIs.

## Remaining Risks

### No Real Gateway Exists Yet

The dogfood simulated gateway output. A production edge still needs a concrete contract for user authentication, header stripping, trusted claim issuance, request forwarding, and failure behavior.

### Secret Rotation Is Still Absent

The Control Plane accepts one configured gateway secret. A hosted deployment needs rotation, overlap windows, revocation, and operational policy.

### Permission Issuance Is Still External

The Control Plane checks permissions but does not issue them. A production gateway or identity service must define how permission claims are derived and constrained.

### Header Stripping Is Still An Assumption

The Control Plane ignores public identity headers, but a real gateway still needs an explicit strip-and-rewrite contract for all trusted `X-API2Agent-*` headers.

### Project Scope Is Not Tenant-Partitioned Mutation

`ProjectID` scopes audit and idempotency records, but registry import/replace remains full-registry replacement. Tenant-partitioned mutation remains future work.

### No Automatic Propagation Was Added

Import/replace remains separated from snapshot export, publish, and Data Plane reload. That separation remains intentional.

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
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0
```

Why:

- Control Plane trusted-gateway behavior is implemented and dogfooded.
- The remaining highest-risk area is the production boundary outside the Control Plane.
- A design pass can define the gateway contract without prematurely implementing OAuth, public CRUD, onboarding, or marketplace surface.
- Secret rotation, trusted header stripping, permission issuance, and deployment observability should be specified before any real hosted edge is built.

Expected design scope:

- gateway-to-Control-Plane trust boundary
- required public header stripping and trusted header rewrite rules
- gateway secret rotation and revocation policy
- permission claim issuance assumptions
- request identity and audit evidence contract
- failure semantics for gateway/auth service outages
- deployment and observability expectations
- test and dogfood requirements for a later implementation slice

Out of scope for that task:

- OAuth/OIDC provider implementation
- real public gateway deployment
- public registry CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime
