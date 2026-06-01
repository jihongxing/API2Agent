# Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Implementation Report v0

Date: 2026-06-02

Status: complete

## Summary

The local hosted admin gateway harness now makes hosted permission decision duplicate handling explicit.

Equivalent duplicate decision evidence is accepted as a no-op, conflicting duplicate evidence raises `PERMISSION_DECISION_INTEGRITY_CONFLICT`, and allowed conflicts fail closed before forwarding. Denied/source-unavailable failures still preserve their original fail-closed caller response while recording local evidence.

No public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, policy write APIs, schema migration, or Data Plane reads from mutable Control Plane tables were added.

## Implemented

Updated:

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
tests/test_go_control_plane_hosted_admin_gateway_contract.py
```

The gateway dogfood harness now has:

- canonical controlled-evidence comparison for persisted decision rows.
- duplicate-equivalent no-op behavior.
- explicit `PERMISSION_DECISION_INTEGRITY_CONFLICT` for conflicting duplicates.
- allowed-conflict fail-closed handling before forwarding.
- bounded local failure evidence with error type and decision id.
- sentinel constraints that reject allowed decisions with unknown subject/actor/org/policy evidence.
- live dogfood probes for equivalent duplicate and conflicting duplicate decisions.

Regression coverage now checks:

- equivalent duplicate persistence performs one insert and one no-op.
- conflicting duplicate evidence raises `PERMISSION_DECISION_INTEGRITY_CONFLICT`.
- allowed sentinel evidence is rejected.
- source-unavailable sentinel normalization still works.
- missing/invalid public auth decisions remain outside persistence.

## Dogfood Artifact

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
```

Observed:

- `status=passed`
- `audit_counts.hosted_permission_decisions=15`
- `hosted_permission_decision_rows_after_duplicate_equivalent=15`
- `hosted_permission_decision_rows_after_integrity_conflict=15`
- `integrity_conflict_status=503`
- `integrity_conflict_error_type=PERMISSION_DECISION_INTEGRITY_CONFLICT`
- `audit_rows_after_integrity_conflict=5`
- `permission_decision_duplicate_equivalent_count=1`
- `permission_decision_integrity_conflict_count=1`

The live dogfood proves equivalent duplicates do not create new rows, conflicting duplicates do not mutate existing rows, and allowed integrity conflicts fail closed before Control Plane audit/idempotency writes.

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
```

`go test ./...` was run from:

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Closeout + Phase Review v0
```
