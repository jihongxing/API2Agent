# Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Design v0

日期：2026-06-02

状态：complete

## 决策

下一项 hosted-readiness implementation slice 应 harden hosted permission decision persistence integrity，但不扩大 hosted product surface。

推荐下一项 implementation task：

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Implementation v0
```

实现应保持 local/dogfood-scoped。它应让 duplicate decision handling 显式化，证明 conflicting evidence 会作为 platform integrity error 被拒绝，收紧 partial-failure/sentinel evidence semantics，并记录 metadata retention/privacy expectations。不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、policy write APIs，或 Data Plane 从 mutable Control Plane tables 读取。

## 为什么现在做这一项

hosted admin gateway 现在已经：

- 通过 hosted permission read model 解析 public admin permission decisions。
- 持久化 authenticated allowed、denied 和 source-unavailable decision rows。
- 跳过 missing/invalid public auth 以及 unknown route/method failures。
- 在 allowed-decision persistence unavailable 时 forwarding 前 fail closed。
- 通过 live Postgres dogfood 证明 15 条 secret-safe decision rows。

剩余 correctness gap 不是能否写入 rows，而是当 decision IDs 碰撞或 evidence 变化时，persistence boundary 能否证明 row integrity。

当前 local implementation 使用：

```text
ON CONFLICT (id) DO NOTHING
```

这具备 deterministic behavior，但会静默忽略 conflicting duplicate。hardening slice 应让可接受的 duplicate case 必须 byte-equivalent，并让 conflicting duplicate case 显式化。

## 目标

- 保留 append-only decision persistence。
- 让 duplicate decision handling observable 且 deterministic。
- 只有 controlled evidence 等价时才接受 duplicate inserts。
- duplicate decision IDs 携带 conflicting evidence 时拒绝，并返回 `PERMISSION_DECISION_INTEGRITY_CONFLICT`。
- allowed-decision integrity conflicts 在 forwarding 前 fail closed。
- denied/source-unavailable 仍保留原始 fail-closed responses，同时记录 local conflict evidence。
- 澄清 sentinel 和 partial-failure row semantics。
- 保持 persisted metadata secret-safe 且 bounded。
- 在 decision rows 成为 production product data 前定义 retention/privacy expectations。
- 用 focused tests 和 live dogfood evidence 证明 hardening。

## 非目标

不要实现或设计：

- public user/project/role/permission CRUD
- OAuth/OIDC provider integration
- login/session/invitation lifecycle
- production gateway deployment
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- workflow runtime
- automatic snapshot publish/reload
- policy write APIs
- Data Plane reads from mutable Control Plane tables
- policy cache invalidation or propagation

## Integrity Boundary

gateway 仍然拥有 permission lookup 和 decision recording：

```text
GatewayPermissionDecision
  -> normalize persistence evidence
  -> compute controlled evidence fingerprint
  -> insert hosted_permission_decisions
  -> if id exists, compare controlled evidence fingerprint
  -> accept exact/equivalent duplicate or raise integrity conflict
```

private Control Plane 仍不得在 endpoint authorization 中写入 hosted permission decisions。

## Controlled Evidence

hardening implementation 应定义 canonical controlled-evidence object 用于 duplicate comparison。

推荐字段：

| Field | Include |
| --- | --- |
| `subject_id` | yes |
| `actor_id` | yes |
| `project_id` | yes |
| `organization_id` | yes |
| `token_id` | yes |
| `required_permission` | yes |
| `allowed` | yes |
| `deny_reason` | yes |
| `roles` | yes，排序或以 canonical 方式保留 |
| `permissions` | yes，排序或以 canonical 方式保留 |
| `policy_source` | yes |
| `policy_version` | yes |
| `policy_fingerprint` | yes |
| `resolved_at` | yes，归一化到 storage 使用的 timestamptz precision |
| metadata allowlist | yes |
| `created_at` | no |

`created_at` 不应参与比较，因为它是 write timestamp。database-generated 或 operational-only fields 不应导致 duplicate conflict。

canonical form 应使用 stable key ordering，且不得包含 secrets。未来 production schema 可以存储显式 `decision_evidence_fingerprint`；v0 local implementation 可以直接比较查询出的 row values，或在 harness 中计算 fingerprint 后判断 duplicate 是否等价。

## Duplicate Handling

推荐行为：

| Case | Behavior |
| --- | --- |
| new `id` | insert row |
| duplicate `id` with equivalent controlled evidence | no-op success；如有价值可在 dogfood/report 中记录 duplicate-equivalent evidence |
| duplicate `id` with conflicting controlled evidence | raise `PERMISSION_DECISION_INTEGRITY_CONFLICT` |

implementation 不应继续只依赖 unconditional silent `ON CONFLICT (id) DO NOTHING` 来证明 correctness。

允许的实现策略：

1. 先 insert with `ON CONFLICT DO NOTHING`，如果没有插入行，则查询 existing row 并比较 controlled evidence。
2. 先查询 existing row，存在则比较，否则 insert。
3. 增加 local-only canonical evidence fingerprint，并在 SQL conflict handling 中使用。

v0 应优先选择最小 local harness change，只要能在 tests 中清楚证明行为即可。

## Failure Semantics

Integrity conflict 是 platform failure。

推荐 caller behavior：

| Decision being persisted | Integrity conflict behavior |
| --- | --- |
| allowed decision | forwarding 前返回 `503 PERMISSION_DECISION_INTEGRITY_CONFLICT` |
| denied `403` decision | 保留原始 `403`；记录 local integrity-conflict evidence |
| source-unavailable `503` decision | 保留原始 `503 PERMISSION_SOURCE_UNAVAILABLE`；记录 local integrity-conflict evidence |

这与 persistence-unavailable behavior 对齐：当 durable evidence 被污染或含混时，不转发 allowed request；但也不把已经 fail-closed 的 denial 改成不同的 caller-visible authorization result。

## Sentinel And Partial-Failure Semantics

当前 v0 sentinel values：

| Missing evidence | Sentinel |
| --- | --- |
| unknown subject | `unknown-subject` |
| unknown actor | `unknown-actor` |
| unknown organization | `unknown-organization` |
| unknown policy source | `hosted-permission-source-unavailable` |
| unknown policy version | `unavailable` |
| unknown policy fingerprint | `sha256:unavailable` |

hardening 应为 local compatibility 保留这些 sentinel，但约束其使用：

- 只有 authenticated source-unavailable decisions 可以使用 unknown subject/actor/org sentinels。
- allowed decisions 绝不能使用 unknown subject、actor、organization、policy source、policy version 或 policy fingerprint。
- denied `403` decisions 只有在 read model 合理无法导出 membership evidence 时，才可使用 unknown actor/org。
- sentinel policy source/version rows 必须显式 seed，且标记为 non-active。
- dogfood 应统计 sentinel rows，并证明它们只对应 source-unavailable 或 partial-denial cases。

未来 production schema work 可以重新评估 nullability 或 dedicated partial-failure evidence table。本设计不要求现在做 schema migration。

## Metadata Allowlist

v0 hardening 允许的 metadata keys：

| Key | Status |
| --- | --- |
| `decision_status` | keep |
| `error_type` | keep |
| `permission_source` | keep |
| `request_id` | keep |
| `method` | keep |
| `path` | keep |
| `gateway_key_id` | keep |
| `persistence_version` | keep |
| `duplicate_resolution` | optional local evidence |
| `integrity_error_type` | optional local evidence |

不要把 raw request body、raw public bearer token、raw `Authorization`、cookies、gateway secret、OAuth access/refresh tokens、plaintext credentials、vault material 或 unbounded exception strings 放入 persisted metadata。

Local in-memory/report failure evidence 可以包含 bounded error type 和 decision id，但不得包含 raw SQL、DSN passwords、tokens 或 headers。

## Retention And Privacy

v0 hardening 应记录并保持以下立场：

- local dogfood rows 只在 temporary Postgres container 生命周期内保留。
- production retention、export、deletion、tenant privacy controls 和 legal discovery workflows 延后。
- cleanup automation 不应在 request handling 中运行。
- 未来 production design 应按 tenant/project 定义 retention，并澄清哪些 decision fields 对 customer-visible。

本 slice 不应新增 cleanup job。

## Schema Guidance

local hardening proof 不需要 schema migration。

允许的 optional local changes：

- 增加 local-only helper 计算 canonical evidence fingerprint。
- 增加 tests 查询 existing rows 并比较 controlled evidence。
- 增加 dogfood report fields 记录 duplicate-equivalent 和 duplicate-conflict probes。

延后的 production/schema options：

- 显式 `decision_evidence_fingerprint` column。
- `(id, decision_evidence_fingerprint)` uniqueness。
- partial-failure nullable fields 或 dedicated sentinel entities。
- 基于 `organization_id`、`project_id` 和 `created_at` 的 retention indexes。

## Test Requirements

implementation tests 应证明：

- duplicate insert with equivalent controlled evidence 成功，且不创建第二行。
- duplicate insert with conflicting allowed evidence 抛出 `PERMISSION_DECISION_INTEGRITY_CONFLICT`。
- allowed conflict 在 forwarding 前 fail closed。
- denied/source-unavailable 的 duplicate conflict 保留原始 fail-closed response，并记录 local evidence。
- allowed decisions 不能被 normalize 成 sentinel subject/actor/org/policy values。
- source-unavailable sentinel rows 只接受 authenticated decisions。
- metadata allowlist 会拒绝 secret-like material 和 unbounded raw headers/bodies。
- canonical evidence comparison 忽略 `created_at`。
- role/permission ordering 被 canonicalized 或一致比较。

## Dogfood Requirements

Live dogfood 应扩展现有 persistence artifact，加入：

1. equivalent duplicate persistence probe。
2. conflicting duplicate persistence probe。
3. allowed conflict probe，forwarding 前返回 `503 PERMISSION_DECISION_INTEGRITY_CONFLICT`。
4. 证明 equivalent duplicates 不增加 hosted decision row count。
5. 证明 conflicting duplicates 不修改 existing rows。
6. 证明 sentinel rows 限定在 expected decision families。
7. persisted rows 和 local failure evidence 的 secret-safety checks。

可以复用现有 artifact path，也可以创建 hardening-specific artifact path。如果复用，report 应包含显式 hardening fields，方便 closeout 区分 base persistence 和 integrity probes。

## Non-Goals Preserved

本设计不新增 public CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic snapshot publish/reload、policy write APIs，或 Data Plane mutable table reads。

## 下一项建议任务

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Implementation v0
```
