# Go Control Plane Hosted Permission Decision Retention Boundary Live Dogfood + Closeout v0

Date: 2026-06-02

Status: complete

## Decision

The Hosted Permission Decision Retention Boundary implementation slice can close for local v0.

The repository now proves that persisted hosted permission decisions can carry retention/history metadata, support tenant/project scoped redacted history queries, emit audited support/operator history access evidence, and select cleanup candidates while respecting legal-hold metadata. This is still a local/private boundary proof, not a customer-facing decision history product.

Recommended next task:

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Design v0
```

That task should design the hosted policy mutation boundary for roles, grants, memberships, policy versions, review/promotion, rollback, and audit. It must not add public CRUD, OAuth/OIDC, invitation/session lifecycle, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, Data Plane reads from mutable Control Plane tables, real production gateway deployment, or a customer-facing decision history endpoint.

## What Is Now Complete

### Retention Metadata

Completed:

- `retention_policy_version=hosted-permission-decision-retention-v0`
- `retention_class=security`
- deterministic 90-day `retain_until`
- `history_visibility=tenant_visible_candidate`
- `redaction_policy_version=hosted-permission-decision-history-redaction-v0`
- `legal_hold=false` default
- metadata-backed project/retain-until index
- metadata-backed project/visibility/time index

### Redacted History Query

Completed:

- local/private tenant/project scoped history query helper
- required project scope
- bounded page size
- result-family and required-permission filters
- hashed subject refs
- hashed actor refs
- no token id exposure in redacted history rows
- cross-project query isolation proof

### Operator Audit And Cleanup Candidate Selection

Completed:

- support/operator history query writes `admin_audit_events`
- audit metadata includes project, organization, access reason, ticket id, result count bucket, and redaction policy version
- audit metadata remains secret-safe
- cleanup candidate selector uses `retain_until`
- legal-hold rows are excluded from cleanup candidates
- expired rows without legal hold are selected

Reference:

- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_RETENTION_BOUNDARY_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| retention/history metadata is present on persisted decision rows | passed |
| v0 retention policy version is recorded | passed |
| redaction policy version is recorded | passed |
| tenant/project scoped history query is implemented locally | passed |
| cross-project history query returns no rows | passed |
| redacted history rows hash subject and actor refs | passed |
| redacted history rows do not expose token ids | passed |
| support/operator history query emits audit evidence | passed |
| support/operator audit metadata is secret-safe | passed |
| cleanup candidate selector excludes legal-hold rows | passed |
| cleanup candidate selector includes expired rows without legal hold | passed |
| customer-facing decision history endpoint remains deferred | passed |
| public CRUD, OAuth/OIDC, production deployment, marketplace, vault, billing, workflow, policy write APIs, Data Plane mutable reads, and automatic propagation remain deferred | passed |

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
- `cleanup_candidates_without_legal_hold=["decision-503589fc1a0e1bc2"]`
- `hosted_permission_decision_rows_after_integrity_conflict=16`
- `permission_decision_retry_count=1`
- `permission_decision_timeout_count=1`

The artifact also proves:

- history rows are tenant/project scoped.
- redacted history output uses hashed subject and actor references.
- the support/operator audit event is separate from the six private Control Plane forwarded-request audit events.
- legal hold is treated as mutable operational metadata and does not rewrite decision evidence.
- customer-facing history endpoints remain absent from the proof.

## Validation

Passed:

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py -q
go test ./internal/registry -run "TestPersistentSchema|TestHostedPermission"
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-retention-boundary/report.json
git diff --check
```

Go test directory:

```text
services/control-plane
```

Python test and dogfood directory:

```text
repository root
```

## Closeout Judgment

This retention boundary slice is complete for local v0.

The implementation proves the local mechanics needed before customer-visible decision history can be designed: rows carry retention metadata, history queries are scoped and redacted, operator access is audited, and cleanup candidate selection respects legal hold. This is the correct stopping point before opening policy mutation work.

## Remaining Risks

### Customer-Facing Decision History Is Still Deferred

There is no public or customer-facing decision history endpoint, UI, export API, or deletion API. The current proof is local/private only.

### Legal Hold Is Metadata Proof Only

Legal hold can protect cleanup candidate selection in the local proof, but there is no operator API, workflow, approval model, or release path.

### Retention Cleanup Does Not Delete Rows Yet

Cleanup candidate selection is proven. Actual deletion, batching, metrics, audit summary rows, and rollback/restore behavior remain future work.

### Hosted Policy Mutation Is Still Seeded

Roles, grants, memberships, and policy versions are still seeded for local proof. The next hosted-readiness gap is designing how those policies mutate safely.

### Public Identity Lifecycle Remains Future Work

OAuth/OIDC, invitations, sessions, and external subject lifecycle remain deferred.

### Production Gateway Deployment Remains Future Work

TLS, private networking, rate limits, production rollout, health/readiness, SLOs, and production observability are still outside this slice.

## Still Not Allowed

Do not start:

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation/login/session lifecycle
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- policy write APIs
- Data Plane reads from mutable Control Plane tables
- real production gateway deployment
- customer-facing decision history endpoint

## Completion Estimate

Hosted permission decision retention boundary lane:

```text
100%
```

Hosted Control Plane phase:

```text
72%
```

This is an estimate. The completed retention boundary reduces the risk around durable decision evidence, but the broader Hosted Control Plane still lacks hosted policy mutation, public identity lifecycle, customer-facing history/export/delete, production gateway deployment, production operations, vault/billing/marketplace/workflow surfaces, and Data Plane mutable-read decisions.

## Next Task Rationale

The next highest-signal task is:

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Design v0
```

Why:

- permission read, decision persistence, production-shaped persistence, and retention/history boundary proof are now complete for local v0.
- hosted policy rows are still seeded rather than safely mutated.
- before adding customer-visible history or public identity lifecycle, the project needs a deliberate policy mutation boundary for roles, grants, memberships, policy versions, promotion, rollback, and audit.
- this can stay a design task without starting public CRUD, OAuth/OIDC, production deployment, billing, marketplace, vault, workflow, automatic propagation, or Data Plane mutable reads.
