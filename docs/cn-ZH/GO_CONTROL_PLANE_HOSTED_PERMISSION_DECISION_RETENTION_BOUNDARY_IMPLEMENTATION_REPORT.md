# Go Control Plane Hosted Permission Decision Retention Boundary Implementation v0

日期：2026-06-02

状态：complete

## 摘要

已实现 local hosted permission decision retention boundary proof。

Hosted permission decision rows 现在会在 bounded secret-safe metadata shape 中携带 retention/history metadata；local harness 可以查询 tenant/project scoped redacted decision history；support/operator history queries 会写 audit evidence；cleanup candidate selection 会遵守 retention 和 legal-hold metadata。

## 已实现

- `retention_policy_version=hosted-permission-decision-retention-v0`
- `retention_class=security`
- 基于 v0 90-day policy 的 deterministic `retain_until`
- `history_visibility=tenant_visible_candidate`
- `redaction_policy_version=hosted-permission-decision-history-redaction-v0`
- `legal_hold=false` 默认 metadata
- metadata-backed project/retain-until 和 project/visibility/time indexes
- local/private tenant/project scoped history query helper
- redacted history rows，subject/actor refs 被 hash，且不包含 token ids
- support/operator history query audit event
- cleanup candidate selector 会排除 legal-hold rows
- dogfood artifact 证明 query isolation、redaction、audit 和 cleanup selection

## Dogfood Evidence

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-decision-retention-boundary/report.json
```

Observed：

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
- `cleanup_candidates_without_legal_hold` 包含 expired probe decision id

该 artifact 也保留上一条 production-boundary lane 的证据：16 条 persisted decision rows、evidence fingerprints、production-boundary metadata、transient retry proof、timeout fail-closed proof、duplicate-equivalent no-op behavior 和 duplicate-conflict fail-closed behavior。

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py -q
go test ./internal/registry -run "TestPersistentSchema|TestHostedPermission"
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-retention-boundary/report.json
```

Go test 目录：

```text
services/control-plane
```

## 仍然 deferred

- customer-facing decision history endpoint
- public user/project/role CRUD
- OAuth/OIDC 和 invitation/session lifecycle
- hosted policy write APIs
- real production gateway deployment
- vault、billing、marketplace、workflow runtime
- automatic propagation
- Data Plane 从 mutable Control Plane tables 读取

## 下一项推荐任务

```text
Go Control Plane Hosted Permission Decision Retention Boundary Live Dogfood + Closeout v0
```
