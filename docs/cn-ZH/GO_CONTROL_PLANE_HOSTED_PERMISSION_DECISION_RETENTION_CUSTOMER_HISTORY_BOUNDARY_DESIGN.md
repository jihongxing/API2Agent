# Go Control Plane Hosted Permission Decision Retention + Customer History Boundary Design v0

日期：2026-06-02

状态：complete

## 决策

在暴露 decision history 或把 persisted decision rows 视为长期 product data 前，先设计 hosted permission decision evidence 的 retention 和 customer-history boundary。

对于 v0，hosted permission decision rows 仍是 security and operations evidence。下一项 implementation 应添加 local boundary pieces，让后续 retention 和 tenant-scoped history 可以安全构建：显式 retention policy metadata、tenant/project scoped query semantics、redaction rules、access-control checks、operator audit evidence 和 dogfood proof。暂不暴露 public customer history API。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Decision Retention Boundary Implementation v0
```

该 implementation 应保持 local/private，证明 retention/history boundary mechanics，不新增 public CRUD、OAuth/OIDC、invitation/session lifecycle、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、policy write APIs、Data Plane 从 mutable Control Plane tables 读取，或真实 production gateway deployment。

## 为什么现在设计

完整 hosted permission decision persistence lane 已接受为 local v0：

- request-time decision evidence 已持久化。
- allowed decisions 在 required evidence 无法写入时 fail closed。
- duplicate-equivalent evidence 稳定。
- duplicate-conflicting evidence 显式失败。
- production-shaped timeout/retry behavior 已证明。
- persisted rows 携带 `evidence_fingerprint` 和 production-boundary metadata。
- live Postgres dogfood 证明 16 条 secret-safe decision rows。

剩余风险不再是 decision evidence 能不能写入，而是 evidence 应保留多久、谁可以查看、什么可以 export 或 delete、support operators 如何审计，以及 decision history 成为 customer-visible 前有哪些 privacy guarantees。

## 目标

- 定义 hosted permission decision rows 的 default retention stance
- 定义 tenant/project scoped decision-history query semantics
- 定义 safe customer-visible fields 和 redaction rules
- 定义 tenant admins、project admins、support operators 和 internal systems 的 access-control expectations
- 定义 export、deletion、legal hold 和 cleanup boundaries
- 定义查看 decision evidence 的 operator audit requirements
- 定义下一项 slice 的 local implementation 和 dogfood evidence

## 非目标

- 本 design slice 不提供 public customer-facing history endpoint
- 不做 OAuth/OIDC provider integration
- 不做 public user/project/role CRUD
- 不做 invitation、login 或 session lifecycle
- 不做 marketplace/provider onboarding
- 不做 credential vault writes
- 不做 billing 或 settlement state
- 不做 workflow runtime
- 不做 automatic snapshot publish 或 Data Plane reload
- 不做 hosted policy write APIs
- 不做 Data Plane 从 mutable Control Plane tables 读取
- 不做 real production gateway deployment

## Data Classification

Hosted permission decision rows 是 security evidence。

它们不是：

- raw request logs
- raw identity-provider records
- billing metering records
- provider marketplace analytics
- workflow execution logs
- credential vault records

它们可能包含 tenant-sensitive identifiers，例如 project id、subject id、actor id、token id、required permission、policy fingerprint、deny reason family、gateway key id 和 request id。这些字段对 accountability、support 和 incident response 有用，但必须保持 bounded 且 secret-free。

## Retention Policy

默认 v0 stance：

```text
90 days
```

规则：

- append-only rows 在 active retention window 内保持 immutable。
- cleanup 是 out of band，绝不 inline 到 public admin request handling。
- expired rows 只有在没有 legal hold 时才 eligible for deletion。
- aggregate、tenant-safe metrics 可以比 raw row retention 保留更久。
- integrity conflict evidence 应至少与普通 decision evidence 保留同样长。
- local dogfood rows 只按 test artifact lifetime 保留。

推荐下一项 implementation 的 local metadata：

| Field | Purpose |
| --- | --- |
| `retention_policy_version` | 记录写入该 row 时使用的 policy |
| `retention_class` | 区分 normal、security、integrity-conflict 或 legal-hold candidate evidence |
| `retain_until` | 显式 cleanup eligibility timestamp |
| `history_visibility` | 记录 hidden、tenant_visible_candidate 或 support_only |
| `legal_hold` | 为 true 时阻止 cleanup |

如果下一项 slice 直接加列过大，implementation 可以先用 bounded JSON metadata shape 加 query/index proof。之后的 schema-hardening slice 再把字段提升为 first-class columns。

## History Visibility Model

Decision history 应构建为 tenant/project scoped view，而不是 global table dump。

初始 visibility classes：

| Class | Meaning |
| --- | --- |
| `hidden` | internal-only evidence；不 eligible for customer history |
| `tenant_visible_candidate` | 通过 access checks/redaction 后可进入未来 customer history |
| `support_only` | 只对 audited support/operator workflows 可见 |

默认：

```text
tenant_visible_candidate
```

例外候选：

- platform integrity conflicts 可以是 `support_only`，直到设计出 customer-safe explanation。
- source-unavailable rows 可以作为 availability events 可见，但不能暴露 internal database failure details。
- unknown route/method 和 missing/invalid public auth 在 v0 仍保持在 decision persistence 之外。

## Customer-Visible Field Boundary

未来 customer history 可以展示：

| Field | Stance |
| --- | --- |
| decision timestamp | visible |
| project id/name | 在 tenant/project scope 内 visible |
| action or endpoint permission | visible |
| allow/deny/source-unavailable result | visible |
| deny reason family | visible |
| request id correlation | 如果是 tenant supplied 或 safe，则 visible |
| policy version/fingerprint | visible |
| actor/subject display reference | 仅在 identity lifecycle 获批后 visible |
| decision id | 作为 support/debug reference visible |
| evidence fingerprint | 作为 integrity/audit reference visible |

未来 customer history 不能展示：

- raw bearer tokens
- raw `Authorization` headers
- cookies
- gateway secrets
- OAuth access 或 refresh tokens
- plaintext API keys
- vault material
- raw request bodies
- raw provider credentials
- private Control Plane internal stack/error details
- 未获批准的 external identity-provider subject references

## Access Control

Decision history access 必须按 tenant 和 project scope。

Expected principals：

| Principal | Access stance |
| --- | --- |
| tenant owner/admin | 未来 public identity lifecycle 存在后，可查询 tenant/project-scoped history |
| project admin | 未来 public identity lifecycle 存在后，可查询 project-scoped history |
| readonly project member | v0 默认无 history access |
| support operator | support-only access，必须带 reason、ticket id 和 audit row |
| internal system | 只允许 retention cleanup、export generation、metrics 和 incident workflows 读取 |
| Data Plane | 不直接读取 mutable Control Plane tables |

在 public identity lifecycle 存在前，local implementation 应只通过 trusted gateway/test principals 证明 access checks。

## Operator Audit

任何 support/operator 查看 decision evidence 都必须创建 audit record。

Audit evidence 应包含：

- actor/operator id
- organization id 和 project id scope
- access reason
- optional ticket/case reference
- query time range
- result count bucket
- redaction policy version
- request id
- outcome

Audit evidence 不能包含 raw decision row contents、raw tokens、gateway secrets 或 request bodies。

## Export Boundary

Export 在本 slice 中只设计，不作为 public API 实现。

未来 export requirements：

- 必须有 tenant/project scope。
- 必须有显式 time range。
- export 必须使用 customer-visible field boundary。
- export creation 必须写 audit event。
- export artifact 必须包含 manifest，记录 schema version、redaction policy version、row count、time range 和 fingerprint。
- export artifacts 除非 legal hold 要求更长 retention，否则应短期存在。
- export 不应包含 hidden/support-only fields，除非走单独 audited support workflow。

## Deletion Boundary

Deletion 分为 cleanup 和 customer-requested deletion。

Cleanup：

- 删除 `retain_until < now()` 且 `legal_hold=false` 的 rows。
- out of band 运行。
- 产生 cleanup metrics 和 summary audit/operation event。
- 不删除 admin audit rows、registry revisions 或 aggregate metrics。

Customer-requested deletion：

- defer 到 public identity lifecycle 和 policy/tenant admin authority 存在后。
- 必须 tenant/project scoped。
- 在允许时保留 aggregate security metrics。
- 必须产生 deletion audit evidence。

## Legal Hold Boundary

Legal hold 会阻止匹配 rows 的 cleanup 和 customer-requested deletion。

V0 design stance：

- support/operator-only function，不 customer-facing。
- 按 tenant/project/time range scope。
- 需要 reason 和 operator audit evidence。
- 除 hold metadata 外，不 mutate decision evidence。

Implementation 可以 defer legal hold mechanics，但 retention schema/metadata 不应让 legal hold 变得不可能。

## Query Semantics

初始 local query helper 应支持：

- project id scope
- optional subject id scope
- start/end time range
- result family filter：allowed、denied、source-unavailable、persistence-failure、integrity-conflict
- endpoint/required permission filter
- limit 加 stable descending time order

规则：

- 不提供 unscoped cross-tenant query helper。
- default time range 应 bounded。
- 必须有 hard maximum page size。
- 即使只在本地使用，query output 也必须通过 customer-visible field boundary redaction。
- support/operator query paths 必须产生 audit evidence。

## Schema And Index Guidance

现有 production-boundary schema 已有 tenant/time、subject/time、retention 和 policy-fingerprint indexes。下一项 implementation 应添加显式 retention/history metadata，或证明等价的 bounded metadata shape。

如果提升为 columns，推荐 indexes：

```sql
CREATE INDEX hosted_permission_decisions_project_retain_until
  ON hosted_permission_decisions (project_id, retain_until);

CREATE INDEX hosted_permission_decisions_project_visibility_time
  ON hosted_permission_decisions (project_id, history_visibility, resolved_at DESC);
```

Implementation 不得添加 raw request body storage、raw token storage、OAuth token tables、public CRUD tables、policy write APIs 或 Data Plane mutable-read paths。

## Implementation Requirements

下一项 implementation 应：

- 为 hosted permission decision rows 添加或标准化 retention metadata。
- 添加 local/private decision-history query helper，并强制 tenant/project scoping。
- 对 query output 应用 redaction。
- 为 support/operator query 增加 audit evidence。
- 添加 cleanup candidate selection logic；除非能在 isolated local helper 中安全证明 deletion，否则暂不删除 rows。
- 保持 customer-facing history endpoints disabled/deferred。
- 在 tests 和 dogfood 中证明 query、redaction、retention metadata 和 audit behavior。

## Test Requirements

Tests 应覆盖：

- 新 decision rows 会获得 retention policy metadata。
- `retain_until` 或等价 metadata 可从 `resolved_at` 和 policy deterministic 地计算。
- tenant/project scoped query 只返回匹配 rows。
- cross-project query attempts 被拒绝或通过 helper 变得不可能。
- subject-scoped query 保持在 project scope 内。
- time range 和 page size limits 被 enforce。
- redacted output 不包含 tokens、authorization headers、cookies、gateway secrets、OAuth tokens、plaintext credentials、vault material 和 raw request bodies。
- support/operator query 写 audit evidence。
- cleanup candidate selector 忽略 legal-hold rows。
- customer-facing history endpoint 仍 absent/disabled。
- Data Plane 仍不读取 mutable Control Plane tables。

## Dogfood Requirements

Local dogfood 应：

1. 运行已有 hosted admin gateway contract harness，并启用 decision persistence。
2. 写入带 retention/history metadata 的 production-boundary decision rows。
3. 查询一个 project 的 decision history，证明 row count 和 filters。
4. 查询另一个 project 或 scope，证明 isolation。
5. 运行 support/operator query，证明 audit evidence 被写入。
6. 运行 cleanup-candidate selection，证明 retained/legal-hold rows 被正确处理。
7. 输出只包含 redacted history rows 和 summary counts 的 secret-safe artifact。

## Acceptance Criteria

该 design 在以下条件满足时接受：

- default retention stance 明确。
- history visibility classes 明确。
- customer-visible fields 和 redaction rules 明确。
- access control expectations 明确。
- operator audit expectations 明确。
- export、deletion、cleanup 和 legal hold boundaries 明确。
- local implementation requirements 已定义。
- test 和 dogfood evidence requirements 已定义。
- public CRUD、OAuth/OIDC、production gateway deployment、vault、billing、marketplace、workflow、provider onboarding、policy write APIs、Data Plane mutable reads 和 automatic propagation 保持 deferred。

## Next Recommended Task

```text
Go Control Plane Hosted Permission Decision Retention Boundary Implementation v0
```
