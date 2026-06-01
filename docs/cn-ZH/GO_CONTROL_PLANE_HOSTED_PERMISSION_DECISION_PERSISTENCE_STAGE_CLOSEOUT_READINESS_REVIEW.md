# Go Control Plane Hosted Permission Decision Persistence Stage Closeout + Readiness Review v0

日期：2026-06-02

状态：complete

## 决策

完整 Hosted Permission Decision Persistence lane 可以关闭为 local v0。

API2Agent 现在已经有 local、production-shaped proof：hosted admin gateway 可以解析 hosted permission decisions，持久化 secret-safe evidence，在 required evidence 无法写入时于 forwarding 前 fail closed，保持 duplicate/conflict integrity，并暴露足够 metadata 支撑后续 retention、history 和 operations 工作。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Decision Retention + Customer History Boundary Design v0
```

该任务应设计 persisted hosted permission decisions 的 retention、customer-visible history、export/delete 边界、access control、auditability 和 operator evidence。不要新增 public CRUD、OAuth/OIDC、invitation/session lifecycle、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、policy write APIs、Data Plane 从 mutable Control Plane tables 读取，或真实 production gateway deployment。

## Lane Summary

decision-persistence lane 已完成这些 slice：

```text
Go Control Plane Hosted Permission Decision Persistence Design v0
Go Control Plane Hosted Permission Decision Persistence Implementation v0
Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Design v0
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Implementation v0
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Closeout + Phase Review v0
Go Control Plane Hosted Permission Decision Persistence Production Boundary Design v0
Go Control Plane Hosted Permission Decision Persistence Production Boundary Implementation v0
Go Control Plane Hosted Permission Decision Persistence Production Boundary Live Dogfood + Closeout v0
```

## 现在已完成

### Request-Time Decision Evidence

已完成：

- hosted admin gateway 通过 hosted permission read model 解析 permission decisions。
- authenticated allowed、denied 和 source-unavailable decisions 可以被持久化。
- missing/invalid public auth 和 unknown routes 保持在 decision persistence 之外。
- allowed write failure 在 private Control Plane forwarding 前 fail closed。
- local denials 和 source-unavailable responses 保持 gateway-local failure semantics。
- private Control Plane 仍是 forwarded requests 的第二道 authorization gate。

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_CLOSEOUT_PHASE_REVIEW.md`

### Integrity Hardening

已完成：

- duplicate decision ids 使用 canonical controlled-evidence comparison。
- equivalent duplicates 被接受为 no-op success。
- conflicting duplicates 返回 `PERMISSION_DECISION_INTEGRITY_CONFLICT`。
- allowed integrity conflicts 在 private Control Plane audit/idempotency writes 前 fail closed。
- sentinel constraints 会拒绝 invalid allowed evidence，同时保留 source-unavailable sentinel evidence。
- persisted metadata 保持 bounded 且 secret-safe。

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_CLOSEOUT_PHASE_REVIEW.md`

### Production-Shaped Boundary

已完成：

- gateway-owned in-process persistence writer。
- bounded write timeout 和 transient retry budget。
- persistence unavailable 和 timeout cases 的 fail-closed behavior。
- persisted rows 上的 canonical `evidence_fingerprint`。
- `production_boundary_version=hosted-permission-decision-production-boundary-v0` metadata。
- tenant/time、subject/time、retention 和 policy-fingerprint indexes。
- secret-safe live Postgres dogfood artifact 证明 16 条 persisted decision rows。

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`

## Evidence Review

已接受 evidence：

- base persistence dogfood：`15` 条 hosted permission decision rows。
- integrity hardening dogfood：duplicate-equivalent 和 duplicate-conflict probes 将 row count 稳定保持在 `15`。
- production-boundary dogfood：`16` 条 hosted permission decision rows。
- production-boundary dogfood：`16/16` rows 包含 `evidence_fingerprint`。
- production-boundary dogfood：`16/16` rows 包含 `production_boundary_version=hosted-permission-decision-production-boundary-v0`。
- production-boundary dogfood：`permission_decision_retry_count=1`。
- production-boundary dogfood：`permission_decision_timeout_count=1`。
- production-boundary dogfood：unavailable 和 timeout persistence failures 返回 `PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`。
- production-boundary dogfood：allowed persistence unavailable 和 timeout probes 创建 `0` 条 private Control Plane audit rows。
- production-boundary dogfood：integrity conflict 返回 `PERMISSION_DECISION_INTEGRITY_CONFLICT`。
- production-boundary dogfood：integrity conflict 后 hosted decision row count 稳定为 `16`。

Artifacts：

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
.dogfood/go-control-plane-hosted-permission-decision-persistence-integrity-hardening/report.json
.dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| decision persistence design 已完成 | passed |
| gateway-owned request-time persistence 已实现 | passed |
| allowed decisions 在 persistence 无法写入 required evidence 时 fail closed | passed |
| denied/source-unavailable decisions 持久化 secret-safe evidence | passed |
| missing/invalid public auth 保持在 persistence 之外 | passed |
| duplicate-equivalent evidence 稳定 | passed |
| duplicate-conflicting evidence 显式失败 | passed |
| allowed integrity conflict 在 Control Plane forwarding/audit 前失败 | passed |
| production-shaped retry/timeout behavior 已本地实现 | passed |
| persisted rows 携带 canonical evidence fingerprints | passed |
| persisted rows 携带 production-boundary metadata | passed |
| tenant/time、subject/time、retention 和 conflict-investigation indexes 存在 | passed |
| live dogfood 证明 secret-safe artifacts | passed |
| retention/customer-history design 已完成 | next task |
| real production gateway deployment 已完成 | deferred |
| public identity lifecycle 和 policy mutation APIs 已完成 | deferred |

## 完成度估计

Hosted permission decision persistence lane：

```text
100%
```

该 lane 已接受为 local v0 complete。

Hosted Control Plane phase：

```text
70%
```

这是估算，不是正式 product-completion claim。local hosted-readiness foundation 已经很强，但更大的 Hosted Control Plane 仍缺 retention execution、customer-visible decision history、real public identity lifecycle、hosted policy mutation APIs、production gateway deployment、production migration rollout、vault/billing/marketplace/workflow surfaces，以及 Data Plane mutable-read decisions。

## Remaining Hosted-Readiness Risks

### Decision Retention And Customer History

schema 已有 retention-friendly indexes，但还没有 retention policy execution、customer-visible decision history、export path、delete path、access-control model，或查看 decision evidence 的 audit trail。这是现在最高信号的下一项 design boundary。

### Real Public Identity Lifecycle

Public principal mapping 仍是 dogfood/local。OAuth/OIDC、invitations、sessions、organization/project membership lifecycle 和 external subject lifecycle 仍是未来工作。

### Hosted Policy Mutation Lifecycle

Hosted roles、grants、memberships 和 policy versions 仍是为 local proof seed 的。还没有 policy write API、review flow、promotion flow、rollback story 或 tenant admin UX/API。

### Production Gateway Deployment

local harness 证明了 production gateway 必须保持的 contract。它还没有部署 TLS、private networking、rate limits、rollout controls、production health/readiness、SLOs 或 production observability。

### Production Migration And Operations

schema hardening 存在于 local schema file，但 production migration ordering、backfills、compatibility windows、rollback、cleanup jobs、metrics、traces 和 alerting 仍是未来工作。

### Product Surface Boundaries

Vault writes、billing、marketplace/provider onboarding、workflow runtime、automatic propagation 和 Data Plane 从 mutable Control Plane tables 读取仍然刻意 deferred。

## Ranked Next Work

1. `Go Control Plane Hosted Permission Decision Retention + Customer History Boundary Design v0`
2. `Go Control Plane Hosted Permission Policy Mutation Boundary Design v0`
3. `Go Control Plane Hosted Public Identity Lifecycle Boundary Design v0`
4. `Go Control Plane Hosted Gateway Production Deployment Boundary Design v0`

第一项应先做，因为 decision rows 现在已经是 durable local product evidence。在暴露或长期保留它们之前，项目需要明确 customer history、privacy、export、deletion、access 和 operator audit 的边界。

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

## 下一项任务理由

下一项最高信号任务是：

```text
Go Control Plane Hosted Permission Decision Retention + Customer History Boundary Design v0
```

Expected scope：

- 定义 hosted permission decisions 的 retention classes 和 default retention stance。
- 定义 customers 是否以及如何查询 decision history。
- 定义 export、deletion、legal hold 和 audit boundaries。
- 定义 tenant admins、project admins、support operators 和 internal systems 的 access control。
- 定义 decision evidence 的 privacy redaction requirements。
- 定义 customer-visible history endpoint 之前需要的 implementation/dogfood evidence。

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
- real production gateway deployment
