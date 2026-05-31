# Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0

Date: 2026-05-31

Status: complete

## Decision

The Hosted Admin Trusted Gateway Production Boundary implementation slice can close.

The Control Plane now supports a production-shaped trusted-gateway boundary:

```text
active gateway secret set
  -> gateway bearer auth
  -> optional gateway key id
  -> trusted admin claims
  -> endpoint permission check
  -> secret-safe audit and idempotency evidence
```

Recommended next task:

```text
Go Control Plane Hosted Admin Gateway Contract Harness Design v0
```

That task should design a local gateway contract harness that proves header stripping and trusted claim injection without implementing OAuth/OIDC, public CRUD, provider onboarding, vault, billing, marketplace, workflow runtime, or automatic propagation.

## What Is Now Complete

### Production Boundary Design

Completed:

- gateway-to-Control-Plane trust boundary
- trusted header strip/rewrite rules
- gateway authentication and secret rotation policy
- permission claim issuance assumptions
- audit/idempotency evidence contract
- failure semantics
- deployment and observability expectations
- implementation tests and dogfood requirements

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_DESIGN.md`

### Implementation

Completed:

- `--trusted-gateway-secrets`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRETS`
- legacy `--trusted-gateway-secret` compatibility
- rotation-compatible active secret set parsing
- active secret de-duplication
- fail-closed no-active-secret behavior
- constant-time matching over active secret hashes
- `--trusted-gateway-key-id`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_KEY_ID`
- `X-API2Agent-Gateway-Key-ID`
- `registry.AdminPrincipal.GatewayKeyID`
- `registry.ImportReplaceOptions.GatewayKeyID`
- audit metadata `gateway_key_id`
- import/replace audit metadata `gateway_key_id`
- regression tests

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`

### Dogfood

Completed:

- hosted/trusted-gateway service starts without `--admin-token`
- old and new active secrets both work during rotation overlap
- service restarts with only the new secret
- removed old secret returns `401 AUTH_ERROR`
- new secret can still run import/replace
- audit metadata includes non-secret `gateway_key_id`
- audit metadata excludes old and new raw gateway secrets
- idempotency scope remains trusted project plus trusted actor

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| accepted production boundary semantics are implemented | passed |
| legacy single gateway secret remains compatible | passed |
| multiple active gateway secrets are accepted | passed |
| removed old gateway secret is rejected | passed |
| no active gateway secret fails closed | passed |
| optional gateway key id is parsed as non-secret evidence | passed |
| configured gateway key id is used when request key id is absent | passed |
| audit metadata includes `gateway_key_id` when present | passed |
| import/replace audit metadata includes `gateway_key_id` when present | passed |
| raw gateway secrets are absent from audit metadata | passed |
| idempotency scope remains trusted project plus trusted actor | passed |
| local/private behavior remains compatible | passed |
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

Passed:

```text
python -m py_compile scripts\go_control_plane_hosted_admin_gateway_dogfood.py
python scripts\go_control_plane_hosted_admin_gateway_dogfood.py --output tmp\go_control_plane_hosted_admin_gateway_dogfood.json
```

## Closeout Judgment

This implementation slice is complete.

The Control Plane now has the production-side mechanics it needs for a trusted gateway:

- active secret overlap supports no-downtime rotation
- old secret removal can be proven
- key id evidence can be recorded without exposing raw secrets
- audit and idempotency remain based on trusted claims
- local/private mode remains unchanged

The remaining highest-risk gap is no longer inside the Control Plane authenticator. It is the gateway contract itself: a real or local gateway layer must prove public headers are stripped and trusted headers are rewritten before requests reach the Control Plane.

## Remaining Risks

### No Gateway Contract Harness Yet

The live dogfood still calls the Control Plane directly with simulated gateway headers. It does not run a gateway process that strips caller-supplied `X-API2Agent-*` headers and injects trusted claims.

### No Real Public Auth Yet

OAuth/OIDC, sessions, invitations, login, and user lifecycle remain intentionally unimplemented.

### Permission Source Remains External

The Control Plane checks endpoint permissions but still does not derive them from identity/project policy.

### Deployment Boundary Is Not Enforced By Infrastructure

The repository documents that admin endpoints should be private behind the gateway, but it does not include deployment infrastructure that enforces this.

### Tenant-Partitioned Mutation Is Still Future Work

Project identity scopes audit and idempotency, but registry import/replace remains full-registry replacement.

### No Automatic Propagation Was Added

Import/replace remains separated from snapshot export, publish, and Data Plane reload.

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
Go Control Plane Hosted Admin Gateway Contract Harness Design v0
```

Why:

- Control Plane-side trusted-gateway mechanics are complete.
- The current dogfood simulates gateway output directly.
- A gateway contract harness can prove the missing edge behavior without implementing real public auth.
- It can keep the scope narrow: strip public trusted headers, inject trusted claims, forward request id, and call the Control Plane.

Expected design scope:

- local gateway harness responsibilities
- public header stripping matrix
- static test identity and permission policy
- trusted claim injection rules
- gateway secret and key-id forwarding
- request id propagation
- negative cases for spoofed public headers
- dogfood steps over gateway-to-Control-Plane HTTP

Out of scope for that task:

- OAuth/OIDC provider implementation
- production gateway deployment
- public registry CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime
