# Go Control Plane Hosted Admin Gateway Contract Harness Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

The hosted admin gateway contract harness is implemented as dogfood-only local tooling.

The dogfood now proves the full request boundary:

```text
public dogfood request
  -> local gateway harness
  -> strip caller-supplied trusted headers
  -> inject static trusted claims
  -> authenticate to Control Plane with a gateway secret
  -> private Control Plane admin endpoint
```

No OAuth/OIDC, public registry CRUD, provider onboarding, marketplace, vault, billing, workflow runtime, automatic snapshot propagation, or Data Plane reads from mutable Control Plane tables were added.

## Script

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
```

Command:

```text
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output tmp/go_control_plane_hosted_admin_gateway_contract_dogfood.json
```

## Implementation

The script starts:

```text
podman Postgres
  -> apply persistent registry schema
  -> seed-postgres from file registry
  -> build api2agent-controlplane
  -> serve with hosted/trusted_gateway admin mode
  -> local ThreadingHTTPServer gateway harness
  -> public dogfood HTTP requests to the harness
  -> query Postgres evidence
```

The harness:

- forwards `GET /healthz`
- forwards `POST /v1/admin/registry/validate`
- forwards `POST /v1/admin/registry/import-replace`
- rejects unsupported paths locally with `404`
- rejects unsupported methods locally with `405`
- consumes public bearer auth locally
- preserves only `Content-Type`, `X-Request-ID`, and `Idempotency-Key`
- strips caller-supplied `X-API2Agent-*`, public `Authorization`, public identity headers, `Cookie`, and `Proxy-Authorization`
- injects trusted gateway authorization, gateway key id, principal, actor, project, organization, token, roles, and permissions

## Results

Observed:

```json
{
  "status": "passed",
  "admin_token_flag_used": false,
  "unsupported_path_status": 404,
  "unsupported_method_status": 405,
  "missing_public_auth_status": 401,
  "audit_rows_before_missing_public_auth": 0,
  "audit_rows_after_missing_public_auth": 0,
  "validate_status": 200,
  "readonly_validate_status": 403,
  "readonly_import_status": 403,
  "import_status": 201,
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 2,
    "idempotency_records": 1,
    "providers": 1
  }
}
```

## Evidence

Audit rows use the harness-injected identity:

```json
{
  "actor_id": "gateway-harness-actor",
  "principal_subject_id": "gateway-harness-principal",
  "project_id": "gateway-harness-project",
  "organization_id": "gateway-harness-org",
  "auth_method": "trusted_gateway",
  "token_id": "gateway-harness-token-admin",
  "gateway_key_id": "dogfood-gateway-key-contract",
  "local_private": "false",
  "metadata_contains_spoofed_identity": false,
  "metadata_contains_gateway_secret": false,
  "metadata_contains_public_token": false
}
```

The import/replace idempotency record is scoped to the harness-injected project and actor:

```json
{
  "project_id": "gateway-harness-project",
  "actor_id": "gateway-harness-actor",
  "operation": "registry.import_replace",
  "first_request_id": "dogfood-gateway-contract-import-1",
  "status": "succeeded",
  "response_status_code": 201,
  "has_registry_revision": true,
  "has_admin_audit_event": true,
  "noop": false,
  "row_contains_gateway_secret": false,
  "row_contains_public_token": false
}
```

## Assertions

Passed:

- `/healthz` through the harness returned `200`
- valid public admin auth plus spoofed trusted headers returned `200` for registry validation
- audit metadata used harness-injected identity instead of spoofed caller headers
- caller-supplied gateway authorization was stripped and replaced
- missing public auth returned gateway-local `401` and did not create Control Plane audit rows
- readonly public auth returned `403 AUTHZ_DENIED` for validate and import/replace
- full admin public auth import/replace returned `201`
- import/replace idempotency evidence used harness-injected project and actor
- audit metadata included harness gateway key id
- raw public bearer tokens and the raw gateway secret were absent from audit/idempotency evidence and the dogfood report artifact

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

## Next Recommended Task

```text
Go Control Plane Hosted Admin Gateway Contract Harness Closeout + Phase Review v0
```

The closeout should decide whether the local gateway contract proof is sufficient to pause before designing a real hosted public gateway or permission-source integration.
