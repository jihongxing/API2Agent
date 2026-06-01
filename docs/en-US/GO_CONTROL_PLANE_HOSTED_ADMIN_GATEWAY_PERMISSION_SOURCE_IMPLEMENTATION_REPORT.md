# Go Control Plane Hosted Admin Gateway Permission Source Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

The hosted admin gateway contract harness now implements a local permission source boundary. Public dogfood bearer tokens are resolved into project-scoped trusted admin claims before any private Control Plane forwarding occurs.

This keeps the Control Plane trusted-gateway authenticator as the second authorization gate while proving gateway-side permission issuance, denial, route mapping, trusted header stripping, and secret-safe evidence.

## Implemented

- Added an explicit `GatewayPermissionDecision` contract to the local hosted admin gateway harness.
- Added a static dogfood permission source with `policy_source`, `policy_version`, roles, project scope, and permission claims.
- Mapped hosted admin methods and paths to the existing Control Plane permission constants:
  - `POST /v1/admin/registry/validate`
  - `POST /v1/admin/registry/import-replace`
  - `POST /v1/admin/snapshots/export-artifact`
  - `GET /v1/admin/distribution/current`
  - `POST /v1/admin/distribution/publish`
- Kept public `Authorization` local to the gateway and injected only gateway-issued trusted headers.
- Preserved `X-Request-ID` and `Idempotency-Key` forwarding.
- Added fail-closed gateway-local errors:
  - `PUBLIC_AUTH_REQUIRED`
  - `PUBLIC_AUTH_INVALID`
  - `PERMISSION_SOURCE_UNAVAILABLE`
  - `PUBLIC_AUTHZ_DENIED`
  - `PUBLIC_ROUTE_NOT_FOUND`
  - `PUBLIC_METHOD_NOT_ALLOWED`
- Added a forced insufficient trusted-permission path to prove the Control Plane still returns `403 AUTHZ_DENIED` as the second gate.
- Added regression tests for permission decisions, failure typing, trusted header injection, public header stripping, and endpoint permission mapping.

## Dogfood Evidence

Live dogfood passed:

```text
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-admin-gateway-permission-source/report.json
```

The report recorded:

- `status=passed`
- `admin_audit_events=3`
- `idempotency_records=1`
- missing public auth returned `401 PUBLIC_AUTH_REQUIRED`
- invalid public auth returned `401 PUBLIC_AUTH_INVALID`
- permission source unavailable returned `503 PERMISSION_SOURCE_UNAVAILABLE`
- readonly validate succeeded
- readonly import/replace failed locally with `403 PUBLIC_AUTHZ_DENIED`
- forced insufficient trusted permissions reached the Control Plane and returned `403 AUTHZ_DENIED`
- raw public tokens and gateway secret were absent from audit/idempotency/report evidence

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -c "import importlib.util, sys; p='scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py'; s=importlib.util.spec_from_file_location('harness', p); m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m); m.assert_contract_helpers(); print('contract helpers passed')"
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-admin-gateway-permission-source/report.json
```

## Non-Goals Preserved

No OAuth/OIDC, login/session lifecycle, public CRUD, invitation management, marketplace/provider onboarding, credential vault, billing, workflow runtime, production gateway deployment, automatic propagation, or Data Plane mutable table reads were added.

## Next Recommended Task

```text
Go Control Plane Hosted Admin Gateway Permission Source Closeout + Phase Review v0
```
