# Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Live Dogfood + Closeout v0

Date: 2026-06-01

Status: complete

## Decision

The Tenant-Partitioned Registry Mutation Private Endpoint implementation slice can close.

Live dogfood passed against a real Control Plane service process, local hosted gateway harness, and live Postgres.

## Dogfood Artifact

```text
.dogfood/go-control-plane-tenant-partition-private-endpoint/report.json
```

Observed:

- `status=passed`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `partition_violation_error_type=REGISTRY_PARTITION_VIOLATION`
- `readonly_partition_status=403`
- `readonly_partition_error_type=PUBLIC_AUTHZ_DENIED`
- `registry_revisions=3`
- `admin_audit_events=5`
- `idempotency_records=2`

## Evidence

The dogfood proved:

- the hosted gateway maps `POST /v1/admin/registry/project-partition/replace` to `control_plane.registry.project_partition_replace`
- readonly public policy is denied locally before forwarding
- trusted gateway admin policy reaches the Control Plane with project-scoped claims
- same-project partition mutation succeeds
- idempotency replay returns `200` with `replayed=true`
- cross-project/global mutation is rejected by the Control Plane as `403 REGISTRY_PARTITION_VIOLATION`
- partition success audit includes `partition_project_id`, `partition_diff_fingerprint`, and changed counts
- partition failure audit includes failure outcome and partition evidence
- idempotency rows are scoped to `registry.project_partition_replace` and `registry.import_replace`
- audit/idempotency evidence does not contain raw public tokens, gateway secrets, or spoofed trusted identity

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-tenant-partition-private-endpoint/report.json
git diff --check
```

Go test directory:

```text
services/control-plane
```

## Closeout Judgment

The endpoint satisfies the v0 design:

- method/path are implemented
- trusted-gateway-only principal requirement is enforced
- local/private principals are rejected
- broad import/replace permission is insufficient
- project scope is derived from the trusted principal
- partition validation happens in the registry-layer write transaction
- partition violations do not become public CRUD semantics
- audit and idempotency evidence are persisted
- snapshot export, publish, and Data Plane reload remain manual

## Remaining Risks

- Provider ownership is still metadata-based in v0.
- Durable hosted permission storage is still future work.
- Production gateway deployment is still future work.
- Project row mutation policy remains intentionally narrow and should be revisited before public project-management surfaces.
- Full import/replace still exists for operator administration and must stay off the hosted public mutation path.

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

## Recommended Next Task

```text
Go Control Plane Hosted Permission Store Design v0
```

Now that project-scoped mutation is constrained and dogfooded, the next hosted-readiness gap is replacing the static dogfood permission source with a durable permission store design without adding public role CRUD prematurely.
