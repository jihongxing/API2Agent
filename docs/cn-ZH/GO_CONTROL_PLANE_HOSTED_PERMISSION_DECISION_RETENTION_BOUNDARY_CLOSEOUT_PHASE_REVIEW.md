# Go Control Plane Hosted Permission Decision Retention Boundary Live Dogfood + Closeout v0

日期：2026-06-02

状态：complete

## 决策

Hosted Permission Decision Retention Boundary implementation slice 可以关闭为 local v0。

仓库现在证明了 persisted hosted permission decisions 可以携带 retention/history metadata，支持 tenant/project scoped redacted history queries，产生 audited support/operator history access evidence，并在 cleanup candidate selection 中遵守 legal-hold metadata。这仍是 local/private boundary proof，不是 customer-facing decision history product。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Design v0
```

该任务应设计 hosted policy mutation boundary，包括 roles、grants、memberships、policy versions、review/promotion、rollback 和 audit。不要新增 public CRUD、OAuth/OIDC、invitation/session lifecycle、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、Data Plane 从 mutable Control Plane tables 读取、真实 production gateway deployment，或 customer-facing decision history endpoint。

## 现在已完成

### Retention Metadata

已完成：

- `retention_policy_version=hosted-permission-decision-retention-v0`
- `retention_class=security`
- deterministic 90-day `retain_until`
- `history_visibility=tenant_visible_candidate`
- `redaction_policy_version=hosted-permission-decision-history-redaction-v0`
- `legal_hold=false` default
- metadata-backed project/retain-until index
- metadata-backed project/visibility/time index

### Redacted History Query

已完成：

- local/private tenant/project scoped history query helper
- required project scope
- bounded page size
- result-family 和 required-permission filters
- hashed subject refs
- hashed actor refs
- redacted history rows 不暴露 token ids
- cross-project query isolation proof

### Operator Audit And Cleanup Candidate Selection

已完成：

- support/operator history query 会写 `admin_audit_events`
- audit metadata 包含 project、organization、access reason、ticket id、result count bucket 和 redaction policy version
- audit metadata 保持 secret-safe
- cleanup candidate selector 使用 `retain_until`
- legal-hold rows 会被排除出 cleanup candidates
- 无 legal hold 的 expired rows 会被选中

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_RETENTION_BOUNDARY_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| persisted decision rows 带 retention/history metadata | passed |
| v0 retention policy version 已记录 | passed |
| redaction policy version 已记录 | passed |
| tenant/project scoped history query 已本地实现 | passed |
| cross-project history query 返回 0 rows | passed |
| redacted history rows hash subject 和 actor refs | passed |
| redacted history rows 不暴露 token ids | passed |
| support/operator history query 产生 audit evidence | passed |
| support/operator audit metadata 是 secret-safe | passed |
| cleanup candidate selector 排除 legal-hold rows | passed |
| cleanup candidate selector 包含无 legal hold 的 expired rows | passed |
| customer-facing decision history endpoint 仍然 deferred | passed |
| public CRUD、OAuth/OIDC、production deployment、marketplace、vault、billing、workflow、policy write APIs、Data Plane mutable reads 和 automatic propagation 仍然 deferred | passed |

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
- `cleanup_candidates_without_legal_hold=["decision-503589fc1a0e1bc2"]`
- `hosted_permission_decision_rows_after_integrity_conflict=16`
- `permission_decision_retry_count=1`
- `permission_decision_timeout_count=1`

Artifact 还证明：

- history rows 按 tenant/project scoped。
- redacted history output 使用 hashed subject 和 actor references。
- support/operator audit event 与 6 条 private Control Plane forwarded-request audit events 分离。
- legal hold 被视为 mutable operational metadata，不重写 decision evidence。
- customer-facing history endpoints 未进入 proof。

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py -q
go test ./internal/registry -run "TestPersistentSchema|TestHostedPermission"
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-retention-boundary/report.json
git diff --check
```

Go test 目录：

```text
services/control-plane
```

Python test 和 dogfood 目录：

```text
repository root
```

## Closeout Judgment

该 retention boundary slice 已完成 local v0。

implementation 证明了 customer-visible decision history 设计之前所需的 local mechanics：rows 携带 retention metadata，history queries scoped 且 redacted，operator access 被审计，cleanup candidate selection 遵守 legal hold。这是打开 policy mutation 工作前正确的停止点。

## Remaining Risks

### Customer-Facing Decision History 仍然 Deferred

还没有 public 或 customer-facing decision history endpoint、UI、export API 或 deletion API。当前 proof 仅为 local/private。

### Legal Hold 只是 Metadata Proof

Legal hold 可以在 local proof 中保护 cleanup candidate selection，但还没有 operator API、workflow、approval model 或 release path。

### Retention Cleanup 尚不删除 Rows

cleanup candidate selection 已证明。实际 deletion、batching、metrics、audit summary rows 和 rollback/restore behavior 仍是未来工作。

### Hosted Policy Mutation 仍是 Seeded

Roles、grants、memberships 和 policy versions 仍为 local proof seed。下一项 hosted-readiness gap 是设计这些 policies 如何安全 mutate。

### Public Identity Lifecycle 仍是未来工作

OAuth/OIDC、invitations、sessions 和 external subject lifecycle 仍然 deferred。

### Production Gateway Deployment 仍是未来工作

TLS、private networking、rate limits、production rollout、health/readiness、SLOs 和 production observability 仍不属于本 slice。

## 仍然不要启动

不要启动：

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation/login/session lifecycle
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish 或 reload
- policy write APIs
- Data Plane 从 mutable Control Plane tables 读取
- real production gateway deployment
- customer-facing decision history endpoint

## 完成度估计

Hosted permission decision retention boundary lane：

```text
100%
```

Hosted Control Plane phase：

```text
72%
```

这是估算。retention boundary 的完成降低了 durable decision evidence 相关风险，但更大的 Hosted Control Plane 仍缺 hosted policy mutation、public identity lifecycle、customer-facing history/export/delete、production gateway deployment、production operations、vault/billing/marketplace/workflow surfaces，以及 Data Plane mutable-read decisions。

## 下一项任务理由

下一项最高信号任务是：

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Design v0
```

原因：

- permission read、decision persistence、production-shaped persistence 和 retention/history boundary proof 已完成 local v0。
- hosted policy rows 仍是 seed 的，而不是安全 mutation 的。
- 在添加 customer-visible history 或 public identity lifecycle 之前，项目需要明确 roles、grants、memberships、policy versions、promotion、rollback 和 audit 的 policy mutation boundary。
- 这可以保持为 design task，不启动 public CRUD、OAuth/OIDC、production deployment、billing、marketplace、vault、workflow、automatic propagation 或 Data Plane mutable reads。
