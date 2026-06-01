# Go Control Plane Hosted Permission Decision Persistence Production Boundary Design v0

日期：2026-06-02

状态：complete

## 决策

Hosted permission decision persistence 在 production-shaped boundary 中仍应由 gateway 拥有。

Production gateway，或位于 private Control Plane 前面的 hosted admin gateway process，负责解析 public principal 和 permission decision，然后在 allowed request 转发到 private Control Plane 前，同步写入一条 non-secret append-only decision row。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Implementation v0
```

该任务应只在本地基础设施中实现 production-shaped persistence boundary。不要部署真实 public gateway，也不要加入 OAuth/OIDC、public user/project/role CRUD、invitation/session lifecycle、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic publish/reload、policy write APIs，或让 Data Plane 读取 mutable Control Plane tables。

## 为什么现在做这个设计

local hosted admin gateway 已经证明：

- hosted permission read-model resolution
- gateway-owned decision persistence
- allowed/denied/source-unavailable decision evidence
- allowed persistence failure fail-closed behavior
- duplicate-equivalent no-op behavior
- conflicting duplicate detection with `PERMISSION_DECISION_INTEGRITY_CONFLICT`
- secret-safe live Postgres dogfood artifacts

剩余风险不再是 local evidence 能否写入，而是 production ownership 放在哪里、write failure 在运营上如何表现、客户将来能看到什么，以及当前 schema 在 decision rows 成为 durable product data 前是否足够强。

## 目标

- 定义 production persistence ownership 和 process boundary
- 定义 connection lifecycle、retry/backoff、buffering posture 和 fail-closed behavior
- 定义 writes、conflicts 和 retention 的 observability expectations
- 定义 retention/privacy expectations 和 customer-visible decision history stance
- 决定 production-shaped implementation 前需要哪些 schema hardening
- 定义 implementation tests 和 local dogfood/canary evidence

## 非目标

- 不做 OAuth/OIDC provider integration
- 不做 public user/project/role/permission CRUD
- 不做 invitation、login 或 session lifecycle
- 不做 marketplace/provider onboarding
- 不写 credential vault
- 不做 billing 或 settlement state
- 不做 workflow runtime
- 不做 automatic snapshot publish 或 Data Plane reload
- 不做 policy write APIs
- 不让 Data Plane 读取 mutable Control Plane tables
- 不部署真实 production gateway

## Production Boundary Model

边界仍然是：

```text
public admin client
  -> hosted admin gateway
  -> hosted permission read model
  -> hosted permission decision persistence writer
  -> private Control Plane admin endpoint
```

gateway 拥有：

- public caller authentication result consumption
- project/tenant context selection
- endpoint permission mapping
- hosted permission read-model lookup
- decision id construction
- decision persistence
- allowed forwarding 前的 fail-closed behavior
- persistence 成功后的 trusted claim/header injection

private Control Plane 拥有：

- gateway authentication
- trusted claim parsing
- endpoint permission enforcement as the second gate
- admin mutation semantics
- forwarded requests 的 admin audit rows
- forwarded mutations 的 idempotency records

private Control Plane 不应成为 `hosted_permission_decisions` 的 writer。该表记录的是 public hosted permission lookup evidence，不是 endpoint authorization internals。

## Process And Service Ownership

v0 中，persistence writer 应与 hosted admin gateway 同进程运行。

v0 不采用：

- separate decision-audit service
- gateway 与 Postgres 之间的 async queue
- Control Plane-side decision backfill
- allowed forwarding 后的 best-effort background write

原因：

- once persistence enabled，allowed admin mutations 不应在缺少 durable permission evidence 时抵达 private Control Plane。
- in-process ownership 可以保持 request、decision、persistence 和 forwarding correlation 精确一致。
- async buffering 只有在 queue durability、replay、tenant isolation 和 loss semantics 被设计后才能加入。

## Connection Lifecycle

production-shaped writer 应使用 gateway process 拥有的专用 bounded Postgres connection pool。

必需行为：

| 区域 | 要求 |
| --- | --- |
| startup | decision persistence enabled 时校验 persistence configuration |
| health | writer 无法连接 Postgres 时暴露 readiness degraded state |
| pool | 如果本地实现支持，使用与 read-model lookup 分开的 bounded pool |
| per-write timeout | 每次 insert 使用短的 bounded timeout |
| shutdown | 进程退出前尽量 drain in-flight writes |
| credentials | DSN/credentials 从 deployment secret storage 加载，不能进 source control |
| logs | redacts DSN passwords，且不记录 raw tokens/secrets |

read-model lookup transaction 必须保持 read-only，并与 decision persistence write 分离。只有 permission decision object 存在后才开始 persistence write。

## Retry And Backoff

writer 只能做很窄的 retry：

| Failure | Retry stance |
| --- | --- |
| transient connection acquisition failure | 使用短的 bounded exponential backoff retry |
| serialization/deadlock retryable SQL state | 在 request budget 内 retry 一到两次 |
| duplicate-equivalent decision id | 视为 no-op success |
| duplicate-conflicting decision id | 不 retry；返回 `PERMISSION_DECISION_INTEGRITY_CONFLICT` |
| invalid evidence 导致 constraint violation | 不 retry；返回 platform integrity failure |
| request context canceled | 不 retry |

retry budget 必须足够小，避免 public admin caller 等到无界挂起；失败时应收到清晰的 platform failure。

## Fail-Closed And Buffering Posture

allowed decisions 必须同步持久化。

| Decision family | Persistence failure behavior |
| --- | --- |
| allowed | 返回 `503 PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE` 或 `503 PERMISSION_DECISION_INTEGRITY_CONFLICT`；不 forward |
| denied | 返回原 gateway-local denial；记录 log/metric persistence failure |
| source-unavailable | 返回原 source-unavailable failure；记录 log/metric persistence failure |
| missing/invalid public auth | v0 不持久化 |
| unknown route/method | v0 不持久化 |

production-shaped implementation 不应在 allowed forwarding 后静默 buffering decision rows。如果未来引入 queue，queue enqueue 本身必须在 allowed forwarding 前 durable complete。

## Conflict Semantics

integrity hardening 中的 conflict handling 成为 production boundary 的一部分：

- equivalent duplicate evidence 被接受为 idempotent no-op success。
- 相同 decision id 的 conflicting controlled evidence 是 platform integrity conflict。
- allowed conflicts 在 private Control Plane forwarding 前失败。
- conflict evidence 必须 secret-safe，并包含 decision id、project id、required permission、error type，以及可用时的 request correlation id。

## Observability

Metrics 应暴露：

| Metric family | Labels |
| --- | --- |
| decision persistence attempts | project、endpoint permission、allowed、result |
| persistence latency | result、allowed |
| persistence failures | error type、retryable flag |
| integrity conflicts | endpoint permission、allowed |
| duplicate-equivalent no-ops | endpoint permission |
| rows written | allowed、deny reason family |
| retention job results | status、deleted row count bucket |

Logs/traces 应包含：

- request id
- decision id
- project id
- required permission
- safe 时的 public principal id 或 hosted subject id
- policy version/fingerprint
- safe 时的 gateway key id
- persistence result 和 latency

Logs/traces 不得包含：

- raw public bearer tokens
- raw `Authorization`
- cookies
- gateway secrets
- OAuth access 或 refresh tokens
- plaintext API keys
- vault material
- raw request bodies

## Retention And Privacy

Hosted permission decision rows 是 security evidence，不是无界 analytics lake。

Production stance：

- rows 保留一个有界 operational/security window。
- 引入 customer-visible features 时，必须使用 tenant/project-scoped deletion 和 export boundaries。
- raw secrets 和 raw request bodies 不进入该表，使 retention 聚焦 authorization evidence。
- active retention window 内保持 append-only semantics。
- cleanup 必须 out of band 运行，不能嵌在 public admin request handling 中。

推荐 v0 retention policy：

| Data | Default stance |
| --- | --- |
| decision evidence rows | production-shaped environments 默认保留 90 天，除非配置覆盖 |
| local dogfood rows | 保留到 test artifact 生命周期结束 |
| aggregate metrics | 如果 tenant-safe 且 secret-free，可以长于 row retention |
| integrity conflict rows | 至少与普通 decision evidence 保留同样长 |

Deletion/export APIs 不属于本 slice。implementation 只应准备 later tenant-scoped retention 所需的 schema 和 operational boundaries。

## Customer-Visible History Stance

暂不暴露 customer-visible decision history UI/API。

未来设计时可以展示：

- timestamp
- project
- endpoint/action
- required permission
- allow/deny/source-unavailable result
- deny reason family
- 审批后的 actor/subject display reference
- policy version/fingerprint
- request id correlation

不应展示：

- 未经产品批准的 raw token ids
- raw external identity provider subject refs
- gateway/internal secret metadata
- request bodies
- private Control Plane internal error details

## Schema Hardening Decision

当前表足够支撑 local proof。production-shaped use 前，应增加一个小的 schema hardening slice，之后再把 rows 视为 durable product data。

必需 hardening：

| Need | Recommendation |
| --- | --- |
| duplicate integrity | 存储从 canonical controlled evidence 生成的 `evidence_fingerprint` |
| request correlation | 增加或标准化 safe `request_id` metadata/indexing |
| tenant history queries | 增加 `project_id, resolved_at` 和 `subject_id, resolved_at` indexes |
| retention cleanup | 为按 `created_at` 或 `resolved_at` 的 retention 增加 index support |
| conflict investigation | 让 policy version/fingerprint 可索引或可查询 |
| partial failure evidence | 保留 source-unavailable sentinel semantics，但文档化为 operational evidence，而非 customer identity |

本 slice 不加入 raw request body storage、raw token storage、OAuth token tables、public CRUD tables 或 policy write APIs。

## Implementation Requirements

下一项 implementation 应：

- 在 gateway boundary 中引入 production-shaped persistence writer interface。
- 保持 local harness path 可用。
- production-shaped mode 中，decision persistence 只有显式配置后才启用。
- 如果本地 migration tooling 已支持，则加入 schema hardening；否则记录 migration file 并用 evolved schema 跑通 tests。
- 强制 bounded write timeout 和 retry/backoff behavior。
- 保持 allowed forwarding 前的 fail-closed behavior。
- 保持 duplicate-equivalent no-op 和 duplicate-conflict failure semantics。
- 在 dogfood artifacts 中输出 secret-safe metrics/log evidence。

## Test Requirements

Implementation tests 应覆盖：

- enabled persistence 缺少 writer DSN 时的 startup/config validation
- bounded write timeout 映射为 `PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- transient retry 成功且不创建 duplicate row
- retry budget exhaustion 会在 forwarding 前阻止 allowed decisions
- duplicate-equivalent row 是 no-op success
- duplicate-conflicting row 返回 `PERMISSION_DECISION_INTEGRITY_CONFLICT`
- denied decision persistence failure 不会变成 allow
- source-unavailable persistence failure 保留原 caller failure
- public auth failures 仍不创建 decision rows
- unknown route/method 仍不创建 decision rows
- schema evidence fingerprint 匹配 canonical controlled evidence
- retention query 可以按 tenant/project 和 time 选出旧 rows
- rows、logs、metrics 和 dogfood artifacts 中没有 secret markers

## Dogfood And Canary Requirements

Local dogfood 应：

1. 启动 local Postgres。
2. 应用包含 production-boundary hardening 的 schema。
3. 以 production-shaped persistence mode 运行 gateway。
4. 覆盖 allowed、denied、source-unavailable、duplicate-equivalent 和 duplicate-conflict cases。
5. 模拟 transient write failure 并证明 retry success。
6. 模拟 exhausted persistence failure，并证明 allowed requests 没有 forwarded。
7. 断言 decision rows 包含 evidence fingerprints 和 tenant/time query fields。
8. 断言 artifact output secret-safe。

未来真实部署的 production canary requirements：

- persistence write success rate
- p95/p99 write latency
- fail-closed count by error type
- integrity conflict count
- duplicate-equivalent count
- retention cleanup success/failure
- forwarded allowed requests 从 gateway request id 到 private Control Plane audit id 的 correlation

## Acceptance Criteria

- production persistence ownership 和 process boundary 明确。
- connection lifecycle 和 bounded retry/backoff behavior 明确。
- allowed fail-closed 和 no-silent-buffering stance 明确。
- observability requirements 明确且 secret-safe。
- retention/privacy 和 customer-visible history stance 明确。
- production-shaped use 前所需 schema hardening 明确。
- implementation tests 和 dogfood/canary evidence 已定义。
- OAuth/OIDC、public CRUD、production gateway deployment、vault、billing、marketplace、workflow、provider onboarding、policy write APIs、Data Plane mutable reads 和 automatic propagation 均保持 deferred。

## 下一项推荐任务

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Implementation v0
```
