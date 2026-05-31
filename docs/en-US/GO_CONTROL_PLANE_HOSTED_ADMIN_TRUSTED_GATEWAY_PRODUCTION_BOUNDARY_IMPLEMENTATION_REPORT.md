# Go Control Plane Hosted Admin Trusted Gateway Production Boundary Implementation Report v0

Date: 2026-05-31

Status: complete

## Summary

Production boundary support for the hosted trusted-gateway admin path is implemented in the Go Control Plane.

The implementation keeps legacy single-secret configuration compatible while adding a rotation-compatible active secret set and optional non-secret gateway key-id evidence.

## Implemented

### Rotation-Compatible Gateway Secrets

Added:

- `--trusted-gateway-secrets`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRETS`
- `Handler.TrustedGatewaySecrets`
- `TrustedGatewayAuthenticator.GatewaySecrets`

Behavior:

- comma-separated active secrets are trimmed and de-duplicated
- legacy `--trusted-gateway-secret` / `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET` remains supported
- hosted/trusted-gateway mode fails closed when no active secret exists
- any active secret can authenticate during a rotation overlap
- a removed secret is rejected with `401 AUTH_ERROR`

### Gateway Key-ID Evidence

Added:

- `--trusted-gateway-key-id`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_KEY_ID`
- `X-API2Agent-Gateway-Key-ID`
- `registry.AdminPrincipal.GatewayKeyID`
- `registry.ImportReplaceOptions.GatewayKeyID`

Behavior:

- request header key id is parsed as an optional trusted claim after gateway auth
- configured key id is used when the request header is absent
- key id is non-secret evidence only
- audit metadata includes `gateway_key_id` when present
- import/replace Postgres audit metadata includes `gateway_key_id` when present
- gateway secrets are not written to audit/idempotency metadata

### Secret-Safe Matching

The authenticator compares the presented gateway bearer token against all active secrets using fixed hashes and constant-time comparison over each candidate.

## Dogfood

Updated:

```text
scripts/go_control_plane_hosted_admin_gateway_dogfood.py
```

The live dogfood now verifies:

- hosted/trusted-gateway service starts without `--admin-token`
- old and new active secrets both work during overlap
- the service restarts with only the new secret
- the old removed secret returns `401 AUTH_ERROR`
- the new secret can still run import/replace
- audit metadata includes `gateway_key_id`
- audit metadata does not contain old or new raw gateway secrets
- idempotency scope remains trusted project plus trusted actor

Observed:

```json
{
  "status": "passed",
  "old_secret_overlap_status": 200,
  "old_secret_removed_status": 401,
  "old_secret_removed_error_type": "AUTH_ERROR",
  "validate_status": 200,
  "missing_gateway_auth_status": 401,
  "missing_permission_status": 403,
  "import_status": 201,
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 3,
    "idempotency_records": 1,
    "providers": 1
  }
}
```

## Tests

Added or updated tests for:

- comma-separated gateway secret parsing
- multiple active gateway secrets accepted
- removed old gateway secret rejected
- configured key id used when request key id is absent
- request key id appears in audit metadata
- import/replace carries gateway key id into Postgres audit metadata
- no active gateway secret fails closed
- local/private behavior remains compatible

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

## Not Implemented

This slice intentionally does not add:

- real public gateway deployment
- OAuth/OIDC provider implementation
- public registry CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime

## Next Recommended Task

```text
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0
```

The closeout should decide whether this production-boundary support is sufficient before moving to the next hosted Control Plane readiness gap.
