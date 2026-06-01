# Go Control Plane Hosted Permission Store Contract Harness Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

The hosted admin gateway contract harness now resolves public principals through a durable permission-store-shaped local read model before forwarding to the private Control Plane.

This does not add a production permission database, public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic snapshot publish/reload, or Data Plane mutable Control Plane table reads.

## Implemented

- Replaced direct static token-to-permission lookup with a local hosted permission store fixture.
- Added store-shaped entities:
  - `PublicPrincipal`
  - `HostedSubject`
  - `HostedProjectMembership`
  - `HostedRoleBinding`
  - `HostedPermissionGrant`
  - `HostedPermissionStore`
- Resolved gateway decisions through:

```text
public principal
  -> hosted subject
  -> project membership
  -> role bindings
  -> permission grants
  -> gateway permission decision
```

- Added non-secret permission evidence:
  - `policy_source`
  - `policy_version`
  - `policy_fingerprint`
  - `decision_id`
  - `required_permission`
- Added evidence headers forwarded only as metadata:
  - `X-API2Agent-Permission-Source`
  - `X-API2Agent-Policy-Version`
  - `X-API2Agent-Policy-Fingerprint`
  - `X-API2Agent-Permission-Decision-ID`
- Preserved trusted gateway header stripping and gateway-issued trusted claim injection.
- Preserved Control Plane endpoint permission checks as the second authorization gate.
- Preserved project-scoped partition mutation permission:

```text
control_plane.registry.project_partition_replace
```

## Failure Semantics

The harness now proves gateway-local fail-closed behavior for:

- missing public authorization: `401 PUBLIC_AUTH_REQUIRED`
- invalid public principal: `401 PUBLIC_AUTH_INVALID`
- permission store unavailable: `503 PERMISSION_SOURCE_UNAVAILABLE`
- missing project membership: `403 PUBLIC_AUTHZ_DENIED`
- suspended project membership: `403 PUBLIC_AUTHZ_DENIED`
- revoked permission grant: `403 PUBLIC_AUTHZ_DENIED`
- stale policy view: `503 PERMISSION_SOURCE_UNAVAILABLE`
- endpoint permission absence: `403 PUBLIC_AUTHZ_DENIED`
- unknown route: `404 PUBLIC_ROUTE_NOT_FOUND`
- unsupported method: `405 PUBLIC_METHOD_NOT_ALLOWED`

Gateway-local denials are not forwarded and do not create Control Plane audit or idempotency rows.

## Contract Tests

Covered:

- admin principal resolves through the hosted permission store fixture
- readonly principal can validate but cannot import/replace
- missing public auth and invalid public auth fail locally
- permission source unavailable fails locally
- missing membership fails locally
- suspended membership fails locally
- revoked permission removes access
- stale policy view fails closed
- forwarded headers strip caller-controlled identity and inject trusted claims
- safe policy evidence headers are injected
- all six hosted admin routes map to explicit permissions

## Dogfood Evidence

The existing live dogfood script now records:

- hosted permission source id
- policy version
- policy fingerprint
- decision ids
- required permissions
- unavailable-store, missing-membership, suspended-membership, revoked-permission, and stale-policy statuses
- unchanged Control Plane audit row counts after gateway-local denials
- Control Plane second-gate denial for insufficient trusted permissions
- secret-safe audit/idempotency evidence

Raw public tokens, gateway secrets, session tokens, and vault material remain absent from report artifacts.

Live dogfood artifact:

```text
.dogfood/go-control-plane-hosted-permission-store-contract-harness/report.json
```

Observed:

- `status=passed`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `import_status=201`
- `audit_counts.registry_revisions=3`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-store-contract-harness/report.json
```

Go test directory:

```text
services/control-plane
```

## Non-Goals Preserved

No production permission store schema, public role CRUD, user CRUD, invitation flow, OAuth/OIDC provider integration, session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic snapshot propagation, registry behavior change, or Data Plane mutable table read was added.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Store Contract Harness Closeout + Phase Review v0
```
