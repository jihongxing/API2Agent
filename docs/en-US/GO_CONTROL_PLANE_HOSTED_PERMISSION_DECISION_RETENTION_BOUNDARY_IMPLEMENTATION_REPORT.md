# Go Control Plane Hosted Permission Decision Retention Boundary Implementation v0

Date: 2026-06-02

Status: complete

## Summary

Implemented the local hosted permission decision retention boundary proof.

Hosted permission decision rows now carry retention/history metadata in their bounded secret-safe metadata shape, the local harness can query tenant/project scoped redacted decision history, support/operator history queries emit audit evidence, and cleanup candidate selection respects retention plus legal-hold metadata.

## Implemented

- `retention_policy_version=hosted-permission-decision-retention-v0`
- `retention_class=security`
- deterministic `retain_until` using the v0 90-day policy
- `history_visibility=tenant_visible_candidate`
- `redaction_policy_version=hosted-permission-decision-history-redaction-v0`
- `legal_hold=false` default metadata
- metadata-backed project/retain-until and project/visibility/time indexes
- local/private tenant/project scoped history query helper
- redacted history rows with hashed subject/actor refs and no token ids
- support/operator history query audit event
- cleanup candidate selector that excludes legal-hold rows
- dogfood artifact evidence for query isolation, redaction, audit, and cleanup selection

## Dogfood Evidence

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-decision-retention-boundary/report.json
```

Observed:

- `status=passed`
- `permission_decision_rows_written_count=16`
- `decision_history_rows_count=16`
- `decision_history_denied_import_rows_count=1`
- `decision_history_cross_project_rows_count=0`
- `decision_history_redaction_policy_version=hosted-permission-decision-history-redaction-v0`
- `decision_history_retention_policy_version=hosted-permission-decision-retention-v0`
- `decision_history_support_audit_rows_before=6`
- `decision_history_support_audit_rows_after=7`
- `cleanup_candidates_with_legal_hold=[]`
- `cleanup_candidates_without_legal_hold` contains the expired probe decision id

The artifact also preserves the production-boundary evidence from the previous lane: 16 persisted decision rows, evidence fingerprints, production-boundary metadata, transient retry proof, timeout fail-closed proof, duplicate-equivalent no-op behavior, and duplicate-conflict fail-closed behavior.

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py -q
go test ./internal/registry -run "TestPersistentSchema|TestHostedPermission"
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-retention-boundary/report.json
```

Go test directory:

```text
services/control-plane
```

## Still Deferred

- customer-facing decision history endpoint
- public user/project/role CRUD
- OAuth/OIDC and invitation/session lifecycle
- hosted policy write APIs
- real production gateway deployment
- vault, billing, marketplace, workflow runtime
- automatic propagation
- Data Plane reads from mutable Control Plane tables

## Next Recommended Task

```text
Go Control Plane Hosted Permission Decision Retention Boundary Live Dogfood + Closeout v0
```
