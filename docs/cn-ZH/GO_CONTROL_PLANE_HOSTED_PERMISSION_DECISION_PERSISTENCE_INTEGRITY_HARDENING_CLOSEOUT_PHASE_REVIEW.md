# Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Closeout + Phase Review v0

日期：2026-06-02

状态：complete

## 决策

Hosted Permission Decision Persistence Integrity Hardening implementation slice 可以作为 local v0 关闭。

仓库现在已经证明：duplicate hosted permission decision IDs 不再被静默忽略。Equivalent duplicate evidence 被接受为 no-op success，conflicting controlled evidence 会抛出 `PERMISSION_DECISION_INTEGRITY_CONFLICT`，allowed conflicts 会在 forwarding 到 private Control Plane 前 fail closed。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Design v0
```

该任务应保持为 design task。它应定义 hosted decision rows 成为 durable product data 前所需的 production persistence boundary、service/process ownership、operational behavior、retention/privacy、observability 和 schema hardening。不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、policy write APIs，或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Integrity Hardening

已完成：

- duplicate decision IDs 的 canonical controlled-evidence comparison
- equivalent duplicate no-op behavior
- 通过 `PERMISSION_DECISION_INTEGRITY_CONFLICT` 检测 conflicting duplicate
- allowed conflict 在 forwarding 前 fail closed
- bounded local failure evidence，包含 decision id 和 error type
- sentinel constraints，会拒绝 allowed decisions 使用 unknown subject/actor/org/policy evidence
- duplicate-equivalent、duplicate-conflict、allowed-sentinel rejection、source-unavailable sentinel normalization 和 auth-failure skips 的 regression tests

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

已完成：

- 现有 persistence dogfood，包含 15 条 hosted decision rows
- equivalent duplicate persistence probe
- conflicting duplicate persistence probe
- allowed conflict probe，返回 `503 PERMISSION_DECISION_INTEGRITY_CONFLICT`
- row-count checks，证明 duplicates/conflicts 不创建或修改 rows
- audit-count checks，证明 allowed conflict 在 private Control Plane audit writes 前 fail
- redacted JSON artifact output

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| duplicate-equivalent decisions 被接受为 no-op success | passed |
| conflicting duplicate decisions 抛出 `PERMISSION_DECISION_INTEGRITY_CONFLICT` | passed |
| allowed integrity conflict 在 forwarding 前 fail closed | passed |
| conflicting duplicate 不修改 existing hosted decision rows | passed |
| equivalent duplicate 不创建额外 hosted decision row | passed |
| allowed decisions 不能使用 sentinel subject/actor/org/policy evidence | passed |
| source-unavailable sentinel normalization 仍可工作 | passed |
| missing/invalid public auth decisions 仍在 persistence 之外 | passed |
| canonical comparison 排除 `created_at` 和 operational write timestamps | passed |
| roles 和 permissions 以 canonical 方式比较 | passed |
| metadata 保持 bounded 且 secret-safe | passed |
| public CRUD、OAuth/OIDC、production gateway、marketplace、vault、billing、workflow、automatic propagation、policy write APIs、schema migration 和 Data Plane mutable reads 保持 out of scope | passed |

## Dogfood Evidence

观察结果：

- `status=passed`
- `audit_counts.hosted_permission_decisions=15`
- `hosted_permission_decision_rows_after_duplicate_equivalent=15`
- `hosted_permission_decision_rows_after_integrity_conflict=15`
- `integrity_conflict_status=503`
- `integrity_conflict_error_type=PERMISSION_DECISION_INTEGRITY_CONFLICT`
- `audit_rows_after_integrity_conflict=5`
- `permission_decision_duplicate_equivalent_count=1`
- `permission_decision_integrity_conflict_count=1`

dogfood artifact 还证明：

- equivalent duplicates 不新增 rows。
- conflicting duplicates 不修改 rows。
- allowed integrity conflicts 不触达 private Control Plane audit/idempotency writes。
- persisted rows 和 local failure evidence 保持 secret-safe。

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
git diff --check
git diff --cached --check
```

Go test 工作目录：

```text
services/control-plane
```

Python test 和 dogfood 工作目录：

```text
repository root
```

## Closeout Judgment

这个 integrity hardening slice 已完成 local v0。

上一 slice 最大 correctness gap 是 silent duplicate handling。该 gap 已在本地关闭：duplicates 会与 canonical controlled evidence 比较，equivalent duplicates no-op，conflicting duplicates 成为 explicit platform integrity failures。当 durable evidence 含混时，gateway 仍拒绝 forwarding allowed requests。

这仍是 local harness proof。它不定义 production connection management、deployment topology、retention policy、tenant privacy controls 或 customer-visible decision history。

## Remaining Risks

### Production Persistence Boundary Is Undefined

harness 仍通过 local SQL execution 写入。Production 需要明确 service/process boundary、connection lifecycle、retry/backoff behavior、observability、rollout plan 和 operational ownership model。

### Schema Hardening Is Deferred

本次没有新增 schema migration。Production 可能仍需要 stored evidence fingerprint、retention indexes、explicit partial-failure shape、nullable fields 或 stronger constraints。

### Retention And Tenant Privacy Are Still Deferred

Append-only decision rows 现在更可信，但 production retention、export、deletion、privacy controls、legal discovery 和 customer-visible history 仍未定义。

### Public Identity And Policy Lifecycle Remain Local

Public principal mapping 和 hosted policy data 仍是 local/dogfood seeded。OAuth/OIDC、login/session/invitation lifecycle 和 hosted policy mutation APIs 仍是未来工作。

### Production Gateway Deployment Is Still Out Of Scope

TLS、private networking、rate limits、rollout、production observability、health checks 和 gateway SLOs 仍是未来工作。

## Still Not Allowed

不要开始：

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

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Design v0
```

原因：

- local persistence 和 integrity semantics 现在已经证明。
- 下一项风险不是再做 local evidence tweak，而是决定该 persistence boundary 在 production-shaped infrastructure 中如何运行。
- decision rows 成为 durable customer/product data 前，必须设计 retention/privacy。
- production boundary design 可以保持 narrow，不启动 public CRUD、OAuth/OIDC、billing、marketplace、workflow、policy write APIs 或 automatic propagation。

预期范围：

- 定义 production persistence ownership 和 process/service boundary。
- 定义 connection lifecycle、retry/backoff、fail-closed/buffering posture 和 observability。
- 定义 retention/privacy expectations 和 customer-visible history stance。
- 定义 production use 前是否需要 schema hardening。
- 定义下一项 implementation slice 的 tests 与 dogfood/canary evidence。

Out of scope：

- public CRUD
- OAuth/OIDC
- invitation/session lifecycle
- marketplace/provider onboarding
- vault writes
- billing
- workflow runtime
- automatic publish/reload
- policy write APIs
- Data Plane mutable Control Plane table reads
