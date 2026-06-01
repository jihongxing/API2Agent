# Go Control Plane Hosted Permission Decision Persistence Production Boundary Implementation Report v0

Date: 2026-06-02

Status: complete

## Summary

The local hosted admin gateway harness now implements the production-shaped hosted permission decision persistence boundary.

The gateway-owned writer remains in-process, writes canonical `evidence_fingerprint` values, records bounded timeout/retry configuration in non-secret metadata, retries transient write failures within a tiny budget, and fails allowed decisions closed before private Control Plane forwarding when persistence is unavailable or times out.

No real production gateway deployment, OAuth/OIDC, public CRUD, invitation/session lifecycle, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, policy write APIs, or Data Plane reads from mutable Control Plane tables were added.

## Implemented

Updated:

```text
services/control-plane/schema/postgres/001_persistent_registry_store.sql
services/control-plane/internal/registry/persistent_schema_test.go
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
tests/test_go_control_plane_hosted_admin_gateway_contract.py
```

Added production-boundary schema hardening:

- `hosted_permission_decisions.evidence_fingerprint`
- `CHECK (evidence_fingerprint LIKE 'sha256:%')`
- project/time query index for tenant history
- subject/time query index
- `created_at` index for retention scans
- policy fingerprint index for conflict investigation

Added gateway writer behavior:

- canonical controlled-evidence fingerprinting
- evidence fingerprint persistence for each decision row
- production boundary metadata version
- bounded write timeout evidence
- transient write retry budget evidence
- transient retry success path
- timeout fail-closed path for allowed decisions

Preserved:

- duplicate-equivalent no-op behavior
- conflicting duplicate `PERMISSION_DECISION_INTEGRITY_CONFLICT`
- allowed conflict fail-closed behavior before forwarding
- denied/source-unavailable caller semantics
- auth-failure persistence skips
- secret-safe metadata and artifacts

## Dogfood Artifact

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
```

Observed:

- `status=passed`
- `audit_counts.hosted_permission_decisions=16`
- `permission_decision_rows_written_count=16`
- `permission_decision_retry_count=1`
- `permission_decision_timeout_count=1`
- `transient_retry_status=200`
- `persistence_timeout_status=503`
- `persistence_timeout_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- `audit_rows_after_persistence_timeout=0`
- `hosted_permission_decision_rows_after_duplicate_equivalent=16`
- `integrity_conflict_status=503`
- `integrity_conflict_error_type=PERMISSION_DECISION_INTEGRITY_CONFLICT`
- `hosted_permission_decision_rows_after_integrity_conflict=16`
- every persisted decision row has `evidence_fingerprint`
- every persisted decision row has production boundary metadata
- secret markers remain absent from rows and report artifact

## Validation

Passed locally before live dogfood:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./internal/registry
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
```

## Next Recommended Task

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Live Dogfood + Closeout v0
```
