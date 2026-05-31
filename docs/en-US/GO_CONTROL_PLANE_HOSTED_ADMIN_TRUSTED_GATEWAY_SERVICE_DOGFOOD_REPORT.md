# Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Report v0

Date: 2026-05-31

Status: complete

## Summary

Hosted trusted-gateway admin dogfood passed against a real `api2agent-controlplane serve` process and live podman-backed Postgres.

The service started in hosted mode without `--admin-token`, accepted trusted gateway claims for admin requests, proved old/new gateway secret rotation overlap, rejected a removed old secret with `401 AUTH_ERROR`, rejected missing gateway auth with `401 AUTH_ERROR`, rejected missing permission with `403 AUTHZ_DENIED`, and persisted principal-derived audit/idempotency evidence.

## Script

```text
scripts/go_control_plane_hosted_admin_gateway_dogfood.py
```

Command:

```text
python scripts/go_control_plane_hosted_admin_gateway_dogfood.py --output tmp/go_control_plane_hosted_admin_gateway_dogfood.json
```

## Flow

```text
podman Postgres
  -> apply persistent registry schema
  -> seed-postgres from file registry
  -> build api2agent-controlplane
  -> serve with --admin-identity-mode hosted
  -> serve with --admin-authenticator trusted_gateway
  -> serve with --trusted-gateway-secrets old,new
  -> no --admin-token flag
  -> public GET /healthz
  -> trusted POST /v1/admin/registry/validate with old secret
  -> trusted POST /v1/admin/registry/validate
  -> missing gateway auth POST /v1/admin/registry/validate
  -> missing permission POST /v1/admin/registry/validate
  -> restart with only the new gateway secret
  -> removed old secret POST /v1/admin/registry/validate
  -> trusted POST /v1/admin/registry/import-replace
  -> query audit and idempotency evidence
```

## Results

Observed:

```json
{
  "status": "passed",
  "admin_token_flag_used": false,
  "old_secret_overlap_status": 200,
  "old_secret_removed_status": 401,
  "old_secret_removed_error_type": "AUTH_ERROR",
  "validate_status": 200,
  "missing_gateway_auth_status": 401,
  "missing_gateway_auth_error_type": "AUTH_ERROR",
  "missing_permission_status": 403,
  "missing_permission_error_type": "AUTHZ_DENIED",
  "import_status": 201,
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 3,
    "idempotency_records": 1,
    "providers": 1
  }
}
```

## Principal Evidence

The dogfood verified both `registry.validate` and `registry.import_replace` audit rows used trusted gateway identity:

```json
{
  "actor_id": "hosted-admin-actor-dogfood",
  "principal_subject_id": "hosted-admin-subject-dogfood",
  "project_id": "hosted-project-dogfood",
  "organization_id": "hosted-org-dogfood",
  "auth_method": "trusted_gateway",
  "token_id": "gateway-token-dogfood",
  "gateway_key_id": "dogfood-gateway-key-new",
  "local_private": "false",
  "metadata_contains_gateway_secret": false
}
```

The dogfood also verified the import/replace idempotency record was scoped to trusted gateway claims:

```json
{
  "project_id": "hosted-project-dogfood",
  "actor_id": "hosted-admin-actor-dogfood",
  "operation": "registry.import_replace",
  "first_request_id": "dogfood-hosted-gateway-import-1",
  "status": "succeeded",
  "response_status_code": 201,
  "has_registry_revision": true,
  "has_admin_audit_event": true,
  "noop": false
}
```

## Fix From Dogfood

The first dogfood run found that the HTTP import/replace path passed only actor/project scope into the Postgres mutation layer. The mutation audit row therefore lacked hosted principal metadata such as subject, organization, auth method, token id, and `local_private=false`.

That integration gap is fixed in this slice:

- `registry.ImportReplaceOptions` now carries admin principal evidence fields.
- `ImportReplaceRegistry` maps resolved `AdminPrincipal` evidence into those options.
- Postgres import/replace audit metadata records subject, project, organization, auth method, token id, and local/private status when present.
- Regression tests cover hosted and trusted-gateway import/replace principal evidence propagation.

## Assertions

Passed:

- service started in hosted/trusted-gateway mode without `--admin-token`
- `/healthz` remained public
- old and new active gateway secrets both worked during rotation overlap
- removed old gateway secret returned `401 AUTH_ERROR`
- trusted gateway validation returned `200`
- public `Authorization` and `X-Actor-ID` did not override trusted gateway claims
- missing gateway authorization returned `401 AUTH_ERROR`
- missing endpoint permission returned `403 AUTHZ_DENIED`
- import/replace returned `201`
- audit rows used trusted gateway actor and principal metadata
- audit metadata included non-secret `gateway_key_id`
- audit metadata did not contain old or new gateway secrets
- idempotency record used trusted gateway project and actor scope
- idempotency record linked to registry revision and admin audit event
- no public CRUD, vault, billing, marketplace, workflow, provider onboarding, or automatic propagation was added

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

## Next Recommended Task

```text
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0
```

The closeout should decide whether the implemented production-boundary support can pause before moving to the next hosted Control Plane readiness gap.
