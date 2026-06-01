# Go Control Plane Hosted Admin Gateway Permission Source Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Hosted Admin Gateway Permission Source implementation slice can close.

The repository now proves the hosted admin gateway permission-source boundary in the local dogfood harness:

```text
public dogfood bearer token
  -> gateway-local permission source
  -> GatewayPermissionDecision
  -> endpoint permission mapping
  -> local deny before forwarding when unauthorized
  -> gateway-issued trusted X-API2Agent-* claims
  -> Control Plane trusted-gateway authenticator
  -> Control Plane endpoint permission check
  -> Postgres audit/idempotency evidence
```

Recommended next task:

```text
Go Control Plane Tenant-Partitioned Registry Mutation Design v0
```

That task should design how hosted project identity constrains registry mutation scope. It should not implement OAuth/OIDC, public CRUD, invitation/login/session lifecycle, provider onboarding, marketplace, vault, billing, workflow runtime, production gateway deployment, automatic propagation, or Data Plane reads from mutable Control Plane tables.

## What Is Now Complete

### Design

Completed:

- gateway-side permission source contract
- static dogfood policy shape
- public principal to trusted role/permission mapping
- endpoint permission mapping for five existing admin endpoints
- fail-closed gateway-local auth/authz semantics
- Control Plane second-gate expectations
- secret-safe audit/idempotency evidence requirements
- local dogfood plan and non-goals

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_DESIGN.md`

### Implementation

Completed:

- explicit `GatewayPermissionDecision` data in the local gateway harness
- static dogfood permission source with `policy_source`, `policy_version`, roles, project scope, and permissions
- public bearer token resolution into trusted project-scoped admin claims
- gateway-local consumption of public `Authorization`
- caller-supplied public/trusted identity header stripping
- gateway-issued trusted header injection only after permission-source approval
- endpoint mapping for:
  - `POST /v1/admin/registry/validate`
  - `POST /v1/admin/registry/import-replace`
  - `POST /v1/admin/snapshots/export-artifact`
  - `GET /v1/admin/distribution/current`
  - `POST /v1/admin/distribution/publish`
- typed gateway-local failures:
  - `PUBLIC_AUTH_REQUIRED`
  - `PUBLIC_AUTH_INVALID`
  - `PERMISSION_SOURCE_UNAVAILABLE`
  - `PUBLIC_AUTHZ_DENIED`
  - `PUBLIC_ROUTE_NOT_FOUND`
  - `PUBLIC_METHOD_NOT_ALLOWED`
- forced insufficient trusted-permission proof that the Control Plane still returns `403 AUTHZ_DENIED`
- regression tests for permission decisions, failure typing, trusted header injection, public header stripping, and endpoint permission mapping

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| permission-source contract is documented | passed |
| permission-source contract is implemented in the local gateway harness | passed |
| static dogfood policy maps public principals to trusted roles and permissions | passed |
| gateway derives endpoint required permissions before forwarding | passed |
| gateway denies unauthorized public requests before Control Plane forwarding | passed |
| gateway-local denial creates no Control Plane audit/idempotency rows | passed |
| Control Plane endpoint permission check remains the second authoritative gate | passed |
| forced insufficient trusted permissions return Control Plane `403 AUTHZ_DENIED` | passed |
| audit and idempotency evidence remains trusted-claim based | passed |
| raw public tokens and gateway secret are absent from evidence artifacts | passed |
| static policy is clearly dogfood-only and not production auth | passed |
| no OAuth/OIDC, public CRUD, marketplace, provider onboarding, vault, billing, workflow runtime, automatic propagation, or Data Plane mutable-table reads were added | passed |

## Dogfood Evidence

Live dogfood artifact:

```text
.dogfood/go-control-plane-hosted-admin-gateway-permission-source/report.json
```

Observed:

- `status=passed`
- `admin_audit_events=3`
- `idempotency_records=1`
- missing public auth returned `401 PUBLIC_AUTH_REQUIRED`
- invalid public auth returned `401 PUBLIC_AUTH_INVALID`
- permission source unavailable returned `503 PERMISSION_SOURCE_UNAVAILABLE`
- readonly validate succeeded
- readonly import/replace failed locally with `403 PUBLIC_AUTHZ_DENIED`
- unsupported path failed locally with `404 PUBLIC_ROUTE_NOT_FOUND`
- unsupported method failed locally with `405 PUBLIC_METHOD_NOT_ALLOWED`
- forced insufficient trusted permissions reached the Control Plane and returned `403 AUTHZ_DENIED`
- gateway-local denied paths did not create Control Plane audit/idempotency rows
- audit rows and idempotency rows used trusted gateway principal/project/actor/token evidence
- raw public tokens and gateway secret were absent from audit, idempotency, and report evidence

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-admin-gateway-permission-source/report.json
git diff --check
```

Go test directory:

```text
services/control-plane
```

## Closeout Judgment

This implementation slice is complete.

The permission source v0 satisfies the design acceptance criteria as a local hosted gateway proof:

- public credentials are interpreted only at the gateway boundary
- trusted role and permission claims are gateway-issued, not caller-supplied
- endpoint permission mapping happens before private forwarding
- local auth/authz failures fail closed and do not touch Control Plane audit/idempotency state
- the Control Plane remains authoritative as a second gate after trusted-gateway authentication
- secret/token evidence remains redacted from dogfood artifacts

The static permission source is enough for v0 because the purpose of this slice is the trust-boundary proof, not production hosted authorization. It must remain described as dogfood-only until a durable hosted permission store and real public identity lifecycle are designed.

## Remaining Risks

### Static Permission Source Only

The policy is in the local dogfood harness. It proves shape, mapping, failure semantics, and evidence, but it is not durable hosted authorization.

### No Real Public Identity Lifecycle

There is still no OAuth/OIDC provider, login, session, invitation, public user lifecycle, or public role-management surface.

### Tenant-Partitioned Mutation Is Still Unresolved

Trusted `project_id` scopes audit and idempotency rows, but registry import/replace remains full-registry replacement. The next highest-risk design gap is constraining hosted mutation scope by tenant/project.

### No Production Gateway Deployment

The gateway remains local dogfood tooling. Production routing, TLS, WAF/rate limits, private network enforcement, observability, and operational rollout are future work.

### Durable Permission Store Is Future Work

A persistent hosted permission store is still needed before real product authorization. That design should follow tenant mutation boundaries so it does not imply public role CRUD before mutation scope is safe.

### No Automatic Propagation Was Added

Import/replace remains separated from snapshot export, distribution publish, and Data Plane reload.

## Still Not Allowed

Do not start:

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation/login/session lifecycle
- real production gateway deployment
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Tenant-Partitioned Registry Mutation Design v0
```

Why:

- hosted identity, trusted gateway auth, gateway contract behavior, and gateway permission-source issuance are now proven locally
- the largest remaining hosted risk is that a project-scoped principal can still drive full-registry replacement once authorized
- tenant-partitioned mutation design can define project/provider/capability ownership boundaries without adding public CRUD
- durable permission storage and production gateway deployment will be safer after mutation scope is explicit

Expected design scope:

- tenant/project ownership model for registry entities
- allowed mutation envelope for hosted admin import/replace or future narrower mutation APIs
- audit/idempotency scope for tenant-partitioned changes
- conflict and cross-tenant rejection semantics
- snapshot export/publish boundaries after scoped mutation
- migration path from full-registry replacement to tenant-scoped mutation
- test and dogfood requirements for a later implementation slice

Out of scope:

- OAuth/OIDC implementation
- public CRUD implementation
- production gateway deployment
- provider onboarding
- marketplace
- credential vault
- billing
- workflow runtime
- automatic publish/reload
- Data Plane mutable Control Plane table reads
