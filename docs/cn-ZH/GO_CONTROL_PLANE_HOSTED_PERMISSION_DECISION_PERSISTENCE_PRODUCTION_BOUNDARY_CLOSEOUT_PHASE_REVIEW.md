# Go Control Plane Hosted Permission Decision Persistence Production Boundary Closeout + Phase Review v0

日期：2026-06-02

状态：complete

## 决策

Hosted Permission Decision Persistence Production Boundary implementation slice 可以关闭为 local v0。

仓库现在证明了 hosted permission decision persistence 已具备 production-shaped local boundary：gateway 拥有 in-process writer，allowed decisions 在 persistence unavailable 或 timeout 时会在 forwarding 前 fail closed，persisted rows 携带 canonical `evidence_fingerprint`，bounded retry/timeout settings 会进入 secret-safe metadata，duplicate/conflict integrity 仍保持稳定。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Decision Persistence Stage Closeout + Readiness Review v0
```

该任务应汇总从 design 到 production-boundary proof 的完整 hosted permission decision persistence lane，判断这一 lane 是否可作为 local v0 完成，并排序下一项 hosted-readiness gap。不要新增 public CRUD、OAuth/OIDC、invitation/session lifecycle、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、policy write APIs、Data Plane 从 mutable Control Plane tables 读取，或真实 production gateway deployment。

## 现在已完成

### Production Boundary Implementation

已完成：

- `hosted_permission_decisions.evidence_fingerprint`
- `CHECK (evidence_fingerprint LIKE 'sha256:%')`
- 用于 tenant history 的 project/time query index
- subject/time query index
- 用于 retention scans 的 `created_at` index
- 用于 conflict investigation 的 policy fingerprint index
- canonical controlled-evidence fingerprinting
- gateway-owned bounded write timeout 和 transient retry behavior
- persisted rows 上的 production-boundary metadata
- allowed decisions 的 timeout fail-closed behavior
- transient retry success proof
- duplicate-equivalent no-op preservation
- conflicting duplicate `PERMISSION_DECISION_INTEGRITY_CONFLICT` preservation

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

已完成：

- 真实 local Postgres schema application
- hosted permission store seeding
- private Control Plane service 以 trusted-gateway mode 启动
- local hosted admin gateway harness 启动
- production-boundary persistence writer exercise
- transient write failure retry success
- forced persistence unavailable 和 timeout fail-closed probes
- duplicate-equivalent 和 duplicate-conflict probes
- secret-safe persisted rows 和 artifact checks

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| gateway-owned production-shaped persistence writer 已在本地实现 | passed |
| allowed persistence unavailable 在 forwarding 前 fail closed | passed |
| allowed persistence timeout 在 forwarding 前 fail closed | passed |
| transient write failure 在预算内 retry 并成功 | passed |
| persisted rows 包含 canonical `evidence_fingerprint` | passed |
| persisted rows 包含 production boundary metadata | passed |
| tenant/time 和 retention query indexes 存在 | passed |
| duplicate-equivalent decision 仍是 no-op success | passed |
| conflicting duplicate decision 仍是 `PERMISSION_DECISION_INTEGRITY_CONFLICT` | passed |
| integrity conflict 不会 mutate decision rows | passed |
| allowed integrity conflict 在 private Control Plane audit 前失败 | passed |
| missing/invalid public auth decisions 仍不进入 persistence | passed |
| rows、audit、idempotency 和 artifact evidence 中没有 secret markers | passed |
| public CRUD、OAuth/OIDC、production gateway deployment、marketplace、vault、billing、workflow、automatic propagation、policy write APIs 和 Data Plane mutable reads 仍然 out of scope | passed |

## Dogfood Evidence

Observed：

- `status=passed`
- `audit_counts.hosted_permission_decisions=16`
- `audit_counts.admin_audit_events=6`
- `permission_decision_rows_written_count=16`
- `permission_decision_retry_count=1`
- `permission_decision_timeout_count=1`
- `permission_decision_write_attempt_count=18`
- `transient_retry_status=200`
- `transient_retry_valid=true`
- `persistence_unavailable_status=503`
- `persistence_unavailable_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- `persistence_timeout_status=503`
- `persistence_timeout_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- `audit_rows_after_persistence_unavailable=0`
- `audit_rows_after_persistence_timeout=0`
- `hosted_permission_decision_rows_after_duplicate_equivalent=16`
- `integrity_conflict_status=503`
- `integrity_conflict_error_type=PERMISSION_DECISION_INTEGRITY_CONFLICT`
- `audit_rows_after_integrity_conflict=6`
- `hosted_permission_decision_rows_after_integrity_conflict=16`
- `permission_decision_duplicate_equivalent_count=1`
- `permission_decision_integrity_conflict_count=1`
- 16/16 decision rows 有 `evidence_fingerprint`
- 16/16 decision rows 有 `production_boundary_version=hosted-permission-decision-production-boundary-v0`

Dogfood artifact 还证明：

- persisted row evidence 是 secret-safe。
- private Control Plane audit rows 与 forwarded allowed requests 可以关联。
- gateway-local denials 和 source-unavailable decisions 不创建 private Control Plane audit rows。
- allowed persistence failures 和 integrity conflicts 不触达 private Control Plane mutation/audit paths。

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
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

该 slice 已完成 local v0。

production-boundary design 要求 gateway-owned persistence、synchronous allowed-decision evidence、bounded failure behavior、observability-ready metadata、retention/query schema hardening 和 secret-safe live proof。implementation 和 dogfood 已在本地满足这些要求。

这不表示 API2Agent 已有真实 production hosted gateway。它表示 local Control Plane hosted admin gateway harness 已经证明了 production gateway 必须保持的 decision persistence contract。

## Remaining Risks

### Real Production Gateway Deployment 仍是未来工作

TLS、private networking、deployment topology、gateway health/readiness endpoints、rate limiting、rollout 和 production SLOs 都不属于本 slice。

### Public Identity Lifecycle 仍是本地证明

Public principal mapping、token/session lifecycle、invitations、OAuth/OIDC 和 public role/policy mutation APIs 仍是未来工作。

### Retention Execution 尚未实现

schema 现在支持 retention scans，但还没有 cleanup job、export path、deletion API 或 customer-visible decision history。

### Observability 仍是 local evidence

artifact 已证明本地 metadata 和 counters。production metrics/logs/traces 仍需要未来 gateway process 中的真实 instrumentation。

### Schema Migration Strategy 仍是本地

schema file 已 harden，但对已部署数据库仍没有 production migration/versioning rollout plan。

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

## 阶段完成度估计

Hosted permission decision persistence production-boundary lane：

```text
100%
```

local production-boundary proof 已完成并接受为 v0。更大的 Hosted Control Plane phase 还没有完成，因为 public identity lifecycle、production deployment、policy mutation、retention execution 和 customer-visible history 仍是未来工作。

## 下一项任务理由

下一项最高信号任务是：

```text
Go Control Plane Hosted Permission Decision Persistence Stage Closeout + Readiness Review v0
```

原因：

- decision persistence 已完成 design、implementation、integrity hardening、production-boundary design、production-boundary implementation 和 live dogfood closeout。
- 在开启新 hosted-readiness lane 前，仓库应记录完整 decision-persistence lane 是否已作为 local v0 完成。
- 下一项 gap 应从 remaining hosted risks 中选择，而不是自动扩展产品面。

Expected scope：

- 汇总完整 hosted permission decision persistence lane。
- 判断该 lane 是否完成 local v0。
- 排序 remaining hosted-readiness risks。
- 选择下一项窄任务，不启动 public CRUD、OAuth/OIDC、production deployment、billing、marketplace、vault、workflow、policy write APIs、automatic propagation 或 Data Plane mutable reads。
