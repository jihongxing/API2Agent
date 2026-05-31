# Go Control Plane Hosted Admin Gateway Contract Harness Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Hosted Admin Gateway Contract Harness implementation slice can close.

The repository now has a local, dogfood-only gateway harness that proves the hosted admin trust boundary over real HTTP:

```text
public dogfood request
  -> local gateway harness
  -> public auth stub
  -> trusted header stripping
  -> static trusted claim injection
  -> Control Plane trusted-gateway auth
  -> private admin endpoint
  -> Postgres audit/idempotency evidence
```

Recommended next task:

```text
Go Control Plane Hosted Admin Gateway Permission Source Design v0
```

That task should design how a future hosted gateway derives trusted roles and permissions from an authenticated principal/project policy source. It should not implement OAuth/OIDC, public CRUD, marketplace, vault, billing, workflow runtime, provider onboarding, automatic snapshot propagation, or Data Plane reads from mutable Control Plane tables.

## What Is Now Complete

### Design

Completed:

- local gateway harness responsibilities
- static public auth and identity policy
- public header stripping matrix
- trusted claim injection rules
- request id and idempotency propagation
- negative spoofing cases
- dogfood evidence requirements

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_DESIGN.md`

### Implementation

Completed:

- `scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py`
- standard-library `ThreadingHTTPServer` local gateway harness
- public bearer token policy stubs
- safe request header preservation
- caller-supplied `X-API2Agent-*` stripping
- public identity, cookie, proxy auth, and public `Authorization` stripping
- trusted gateway authorization and key-id injection
- static principal, actor, project, organization, token, role, and permission injection
- local `401`, `404`, and `405` gateway failures
- Control Plane propagated `403 AUTHZ_DENIED`
- live Postgres audit/idempotency evidence checks

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| local gateway harness is implemented as dogfood-only tooling | passed |
| `/healthz` works through the harness | passed |
| public admin auth can call registry validation through the harness | passed |
| caller-supplied trusted headers are stripped | passed |
| harness-injected trusted claims reach the Control Plane | passed |
| caller-supplied gateway authorization is replaced | passed |
| missing public auth fails locally with `401` | passed |
| local public auth failure creates no Control Plane audit rows | passed |
| readonly public auth returns Control Plane `403 AUTHZ_DENIED` | passed |
| admin import/replace through the harness returns `201` | passed |
| audit rows use harness-injected identity | passed |
| idempotency row uses harness-injected project and actor | passed |
| audit metadata includes harness gateway key id | passed |
| raw public bearer tokens and raw gateway secret are absent from evidence/report artifacts | passed |
| no public CRUD, vault, billing, marketplace, workflow, provider onboarding, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile scripts\go_control_plane_hosted_admin_gateway_contract_dogfood.py
```

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
python scripts\go_control_plane_hosted_admin_gateway_contract_dogfood.py --output tmp\go_control_plane_hosted_admin_gateway_contract_dogfood.json
```

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The highest-risk gateway contract gap has moved from unproven to dogfooded:

- public callers cannot override trusted `X-API2Agent-*` identity or permission claims through the harness
- public `Authorization` is consumed locally and does not reach the Control Plane
- request correlation and idempotency headers survive the gateway hop
- Control Plane authorization remains authoritative for endpoint permissions
- audit and idempotency evidence reflects harness-issued trusted identity
- secret/token evidence remains redacted from report artifacts

The implementation is intentionally not a production gateway. It is a contract proof that lets the project move to the next hosted-readiness gap without pretending static dogfood auth is real public auth.

## Remaining Risks

### Static Public Auth Only

The harness uses static dogfood bearer tokens. There is still no OAuth/OIDC, login, session, invitation, or user lifecycle model.

### Static Permission Policy Only

Roles and permissions are hard-coded in the harness. The next design should define a permission source boundary for deriving trusted gateway claims from authenticated principal/project policy.

### No Production Gateway Deployment

The harness is local dogfood tooling. Production routing, TLS, WAF/rate limits, gateway observability, private network enforcement, and secret distribution remain future work.

### Tenant-Partitioned Mutation Is Still Future Work

Project identity scopes audit and idempotency evidence, but registry import/replace is still full-registry replacement.

### No Automatic Propagation Was Added

Import/replace remains separate from snapshot export, publish, and Data Plane reload.

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
