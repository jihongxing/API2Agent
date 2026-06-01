# Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Implementation Report v0

Date: 2026-06-02

Status: complete

## Summary

The local hosted admin gateway harness can now use the internal hosted permission read model as its permission source.

This slice keeps public auth local/dogfood-scoped, maps public principals to non-secret hosted subject references, calls `HostedPermissionReadModel.Resolve` through a small local Go lookup helper, and converts the read-model decision into the same gateway-issued trusted headers used by the private Control Plane. Static fixture mode remains the focused unit-test fallback.

No public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, decision persistence, or Data Plane mutable Control Plane table reads were added.

## Implemented

Added a local lookup helper:

```text
services/control-plane/cmd/api2agent-hosted-permission-gateway-lookup/main.go
```

The helper:

- opens a Postgres DSN with pgx.
- accepts public-principal evidence, external subject ref, project context, token id, required permission, and resolved-at.
- calls `registry.NewHostedPermissionReadModel(db).Resolve`.
- prints a gateway-compatible JSON decision.
- does not receive raw public bearer tokens.

Updated the hosted admin gateway dogfood harness:

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
```

The harness now has:

- `GatewayPermissionSource` protocol.
- `StaticFixturePermissionSource` for existing tests.
- `HostedReadModelPermissionSource` for live Postgres dogfood.
- hosted permission seed rows in the live gateway dogfood database.
- read-model-backed gateway decisions before trusted header injection.
- live checks for missing membership, suspended membership, revoked grant, no active policy, ambiguous active policy, readonly denial, Control Plane second gate, audit/idempotency safety, and zero decision persistence.

Updated the Postgres schema so hosted permission project references are deferrable. This lets same-transaction registry import/replace delete and reinsert the same project while preserving hosted permission rows as an independent read-side boundary.

## Dogfood Artifact

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-read-model-gateway-runtime-wiring/report.json
```

Observed:

- `status=passed`
- `missing_public_auth_status=401`
- `invalid_public_auth_status=401`
- `permission_source_unavailable_status=503`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `ambiguous_policy_status=503`
- `readonly_validate_status=200`
- `readonly_import_status=403`
- `readonly_partition_status=403`
- `insufficient_forward_status=403`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `import_status=201`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`
- `audit_counts.hosted_permission_decisions=0`

Gateway-local failures did not create Control Plane audit or idempotency rows. Trusted-header spoofing, public bearer tokens, and gateway secrets did not leak into audit/idempotency/report evidence.

## Validation

Passed:

```text
gofmt -w services/control-plane/cmd/api2agent-hosted-permission-gateway-lookup/main.go
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./cmd/api2agent-hosted-permission-gateway-lookup ./internal/registry -run HostedPermission
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-read-model-gateway-runtime-wiring/report.json
```

## Next Recommended Task

```text
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Closeout + Phase Review v0
```
