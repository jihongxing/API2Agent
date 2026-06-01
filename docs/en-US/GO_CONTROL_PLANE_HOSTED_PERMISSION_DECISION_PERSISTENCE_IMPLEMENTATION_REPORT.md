# Go Control Plane Hosted Permission Decision Persistence Implementation Report v0

Date: 2026-06-02

Status: complete

## Summary

The local hosted admin gateway harness now persists non-secret hosted permission decision evidence into `hosted_permission_decisions`.

The write happens after the gateway resolves a hosted permission decision and before allowed requests are forwarded to the private Control Plane. Missing or invalid public auth, unknown routes, and unsupported methods remain gateway-local failures and do not create hosted decision rows.

No public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, policy write APIs, or Data Plane reads from mutable Control Plane tables were added.

## Implemented

Updated:

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
tests/test_go_control_plane_hosted_admin_gateway_contract.py
```

The gateway dogfood harness now has:

- `HostedPermissionDecisionPersistence`, a local persistence helper for append-only `hosted_permission_decisions` inserts.
- secret-safe metadata for decision status, error type, permission source, request id, method, path, gateway key id, and persistence version.
- sentinel subject and policy-version seed data for source-unavailable decisions that cannot return complete read-model evidence.
- a persistence skip guard for `PUBLIC_AUTH_REQUIRED` and `PUBLIC_AUTH_INVALID`.
- allowed-decision persistence failure handling that returns `503 PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE` before forwarding.
- denied/source-unavailable persistence failure evidence that preserves the original fail-closed caller response.
- live dogfood assertions for row counts, status counts, required-permission counts, sentinel evidence, readonly mutation denials, and secret leakage.

Regression coverage now checks:

- persistence SQL is secret-safe and includes expected metadata.
- source-unavailable decisions normalize missing row fields to sentinel values.
- missing/invalid public auth decisions are skipped while authenticated source-unavailable decisions are persisted.

## Dogfood Artifact

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
```

Observed:

- `status=passed`
- `audit_counts.hosted_permission_decisions=15`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`
- `permission_decision_rows_after_invalid_public_auth=0`
- `persistence_unavailable_status=503`
- `persistence_unavailable_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- decision status counts: `200=7`, `403=5`, `503=3`
- required permission counts: `validate=9`, `import_replace=2`, `project_partition_replace=4`

Gateway-local auth failures did not create Control Plane audit rows or hosted decision rows. Allowed decision persistence failure failed closed before forwarding. Persisted decision rows did not contain public bearer tokens, caller `Authorization`/`Cookie` material, or the trusted gateway secret.

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
```

`go test ./...` was run from:

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0
```
