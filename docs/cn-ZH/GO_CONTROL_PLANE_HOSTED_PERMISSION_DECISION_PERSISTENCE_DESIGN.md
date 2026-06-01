# Go Control Plane Hosted Permission Decision Persistence Design v0

日期：2026-06-02

状态：complete

## 决策

下一项 hosted-readiness implementation slice 应为 local hosted admin gateway permission source 产生的 hosted permission decisions 增加 append-only persistence。

推荐下一项实现任务：

```text
Go Control Plane Hosted Permission Decision Persistence Implementation v0
```

实现应保持 local/dogfood-scoped。它应在 gateway 解析 public admin permission decision 后，把非 secret hosted permission decision evidence 写入已有 `hosted_permission_decisions` 表。不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation，或 Data Plane 从 mutable Control Plane tables 读取。

## 为什么现在做这个 slice

hosted admin path 现在已有：

- gateway 本地消费 public auth。
- 显式 endpoint permission mapping。
- trusted header stripping 和 gateway-issued trusted header injection。
- Control Plane endpoint permission checks 作为 second gate。
- durable hosted permission schema。
- internal Postgres read model。
- live Postgres read-model dogfood。
- gateway runtime wiring 到 read-model-backed permission source。
- live gateway dogfood 证明 allow/deny/source-unavailable paths。

剩余 evidence gap 是 persistence。系统已经能产生 stable decision IDs 和 non-secret evidence，但 `hosted_permission_decisions` 仍刻意保持为空。下一项 implementation 应通过 append-only decision records 明确改变这个 contract。

## Goals

- 将 hosted permission decisions 持久化为 append-only evidence。
- 保持 gateway 作为 permission lookup 和 decision recording 的 owner。
- 在有足够 safe evidence 时记录 allowed、denied 和 source-unavailable decisions。
- 不把 raw public tokens、gateway secrets、OAuth tokens、refresh tokens、cookies 或 vault material 写入表。
- 保持 gateway fail-closed authorization semantics。
- 定义 persistence failure behavior，避免产生不安全的 broad allows。
- 让 decision persistence 与 Control Plane endpoint authorization 保持分离。
- 用 local/live Postgres dogfood 证明 persistence。

## Non-Goals

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
- Data Plane reads from mutable Control Plane tables
- policy write APIs
- cache invalidation or policy propagation

## Ownership Boundary

gateway permission source 拥有 decision persistence：

```text
public request
  -> gateway public auth
  -> endpoint permission mapping
  -> hosted permission source
  -> HostedPermissionReadModel.Resolve
  -> GatewayPermissionDecision
  -> persist hosted_permission_decisions
  -> gateway-local allow/deny response or trusted forwarding
```

private Control Plane 不应在 endpoint authorization 中写 hosted permission decisions。它接收 trusted claims，并可为 forwarded requests 记录 admin audit events，但不应成为 public hosted permission lookup evidence 的 source of truth。

## Existing Table

当前 schema 已定义：

```text
hosted_permission_decisions
```

当前字段：

| Field | Design use |
| --- | --- |
| `id` | `decision.DecisionID` |
| `subject_id` | 已知 hosted subject id |
| `actor_id` | 已知 hosted actor id |
| `project_id` | gateway-derived project context |
| `organization_id` | 已知 organization id |
| `token_id` | 非 secret token/session id |
| `required_permission` | endpoint permission |
| `allowed` | decision allow/deny |
| `deny_reason` | stable deny reason 或 source-unavailable reason |
| `roles` | 非 secret role ids/names |
| `permissions` | 非 secret permission constants |
| `policy_source` | source identifier |
| `policy_version` | decision 使用的 policy version |
| `policy_fingerprint` | 非 secret policy fingerprint |
| `resolved_at` | gateway decision time |
| `metadata` | bounded non-secret diagnostics |
| `created_at` | write time |

如果 implementation 把缺失的 subject/actor/org evidence 映射为 sentinel non-secret values，则可以直接使用现有表而不做 schema migration。后续 schema hardening slice 可在 production requirements 需要更丰富 partial-failure records 时再讨论 nullability。

## Record Shape

每个 gateway permission decision 持久化一行：

| Field | Source |
| --- | --- |
| `id` | decision id |
| `subject_id` | `decision.SubjectID` 或 sentinel |
| `actor_id` | `decision.ActorID` 或 sentinel |
| `project_id` | gateway-derived project context |
| `organization_id` | `decision.OrganizationID` 或 sentinel |
| `token_id` | public principal mapping 中的非 secret token id |
| `required_permission` | endpoint permission |
| `allowed` | decision allowed flag |
| `deny_reason` | decision deny reason，allowed 时为空 |
| `roles` | decision roles |
| `permissions` | decision permissions |
| `policy_source` | decision policy source 或 fallback source |
| `policy_version` | decision policy version 或 sentinel |
| `policy_fingerprint` | decision policy fingerprint 或 sentinel `sha256:unavailable` |
| `resolved_at` | decision resolved time |
| `metadata` | bounded non-secret JSON |

推荐 sentinel values：

| Missing evidence | Sentinel |
| --- | --- |
| unknown subject | `unknown-subject` |
| unknown actor | `unknown-actor` |
| unknown organization | `unknown-organization` |
| unknown policy source | `hosted-permission-source-unavailable` |
| unknown policy version | `unavailable` |
| unknown policy fingerprint | `sha256:unavailable` |

Sentinels 让 v0 与当前 `NOT NULL` 表兼容，同时让 partial source-unavailable decisions 可 inspect。

## Metadata

允许的 metadata keys：

| Key | Purpose |
| --- | --- |
| `decision_status` | numeric decision status，例如 `200`、`403`、`503` |
| `error_type` | gateway-local error type |
| `permission_source` | source identifier |
| `public_principal_id` | 非 secret public principal id，不是 raw token |
| `external_subject_ref_hash` | 如果需要包含 external subject ref，只存 hash |
| `request_id` | safe request correlation id |
| `method` | normalized method |
| `path` | normalized public admin path |
| `gateway_key_id` | 非 secret gateway key id |
| `persistence_version` | `hosted-permission-decision-persistence-v0` |

不要存储：

- raw public bearer token
- raw `Authorization`
- cookies
- gateway secret
- OAuth access token
- OAuth refresh token
- plaintext API key
- vault material
- raw request body

## Decision ID And Deduplication

当前 decision id 基于以下字段确定性生成：

```text
subject_id | project_id | required_permission | policy_version | resolved_at
```

v0 implementation 保持该 decision id，并仅在 incoming row 与 implementation 控制的字段 byte-equivalent 时使用 `ON CONFLICT (id) DO NOTHING`。如果 duplicate decision id 的 evidence 不同，tests 中应将其视为 platform integrity error。

gateway dogfood 目前 live request decisions 使用秒级 timestamps。implementation 应确保创建 decisions 时 `resolved_at` 有足够精度，从而保持或提高唯一性。如果现有 helper 输出更高精度，则持久化该值。

未来 production work 可以把 request-id 或 nonce 加入 decision id generation，但这应显式设计，因为它会改变 correlation semantics。

## Write Timing

推荐 v0 timing：

1. Resolve public principal and endpoint permission。
2. 调用 hosted permission read model。
3. 构造 `GatewayPermissionDecision`。
4. 持久化 decision row。
5. 如果 allowed，注入 trusted headers 并 forward。
6. 如果 denied，返回 local error response。

在 forwarding 前持久化，这样 allowed decision 即使后续 downstream Control Plane request 失败，也已有 evidence。

missing 或 invalid public auth 在 v0 不写入 `hosted_permission_decisions`。此时还没有 hosted subject/policy decision；这些 failures 仍是 gateway auth failures。

unknown route 或 unsupported method 在 v0 不写入 `hosted_permission_decisions`。此时还没有 endpoint permission decision。

## Persistence Failure Semantics

Decision persistence 是 evidence，不是 authorization。

推荐 v0 behavior：

| Case | Persistence failure behavior |
| --- | --- |
| allowed decision | forwarding 前 fail closed，返回 `503 PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE` |
| denied `403` decision | 返回原始 `403`，在 local artifact/logs 中包含/report persistence failure evidence |
| source-unavailable `503` decision | 返回原始 `503 PERMISSION_SOURCE_UNAVAILABLE`，包含/report persistence failure evidence |

原因：

- 一旦启用 persistence，allowed decisions 不应在没有 durable evidence 的情况下被 forwarded。
- denied/source-unavailable decisions 对 caller 已经 fail closed；persistence failure 不应把它们变成不同的 authorization result。
- dogfood 应证明 persistence failures 永远不会创建 broad allows。

implementation 应保持该行为为 local/dogfood-scoped。Production operational policy 可在后续结合明确 SLOs 和 buffering design 再讨论。

## Transaction Semantics

不要把 decision persistence 混入 read-model repeatable-read transaction。

推荐 implementation：

- read-model lookup 保持 read-only。
- decision persistence 在 read transaction commit 后使用独立短 write operation。
- persistence insert 是 append-only。
- persistence insert 不修改 policy、membership、role、grant、registry、admin audit 或 idempotency rows。

这会把 authorization lookup consistency 与 evidence recording 分开，避免把 read model 变成 mutable read/write boundary。

## Source-Unavailable Decisions

当已有 `GatewayPermissionDecision` 时，应持久化 source-unavailable decisions。

示例：

- no active policy
- ambiguous active policy
- public auth 已产生 known public principal 后，read-model helper/database unavailable

当 source 无法返回完整 evidence 时，使用 sentinel policy/subject fields。Metadata 应包含：

```json
{
  "decision_status": 503,
  "error_type": "PERMISSION_SOURCE_UNAVAILABLE",
  "persistence_version": "hosted-permission-decision-persistence-v0"
}
```

## Secret Safety

implementation 和 dogfood 必须拒绝包含以下 markers 的 evidence：

- public bearer token values
- gateway secret values
- `access_token`
- `refresh_token`
- `plaintext`
- `authorization`
- raw cookies
- vault material markers

dogfood report 应保持 DSN password redacted，且不包含 raw public tokens。

## Retention

V0 design 不增加 cleanup automation。

推荐 retention stance：

- append-only records 保留于 local dogfood artifacts。
- production retention、export、deletion 和 tenant privacy controls 延后。
- 任何未来 cleanup job 都必须显式设计，且不得在 request handling 中隐式执行。

## Test Requirements

Implementation tests 应证明：

- allowed admin decision inserts one row。
- readonly denied mutation inserts one denied row。
- missing membership inserts one denied row with safe evidence。
- suspended membership inserts one denied row。
- revoked grant inserts one denied row。
- no active policy inserts one source-unavailable row with sentinel policy evidence。
- ambiguous policy inserts one source-unavailable row。
- missing/invalid public auth 不插入 hosted permission decision rows。
- unknown route/method 不插入 hosted permission decision rows。
- forced Control Plane second-gate denial 在 forwarding 前已有 allowed gateway decision row。
- raw public token 和 gateway secret 不出现在 persisted rows 中。
- duplicate decision id handling 是 deterministic。
- allowed decision persistence failure 在 forwarding 前 fail closed。

## Dogfood Requirements

Live dogfood 应：

1. start local Postgres。
2. apply schema。
3. seed registry and hosted permission rows。
4. start private Control Plane in trusted-gateway mode。
5. start gateway in hosted read-model permission-source mode with decision persistence enabled。
6. exercise allowed、denied、source-unavailable 和 second-gate cases。
7. query `hosted_permission_decisions`。
8. assert expected row count and row evidence。
9. assert gateway-local denied requests still do not create Control Plane admin audit/idempotency rows。
10. assert secret-safe persisted evidence。

Expected persisted row families：

- allowed validate
- readonly allowed validate
- readonly denied import/replace
- missing membership
- suspended membership
- revoked grant
- no active policy
- ambiguous active policy
- allowed gateway decision followed by Control Plane `AUTHZ_DENIED`
- partition/import allowed decisions

exact row count 应由 implementation tests 在 live dogfood case order 最终确定后指定。

## Non-Goals Preserved

本设计不新增 public CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic snapshot publish/reload、policy write APIs，或 Data Plane mutable table reads。

## 下一项建议任务

```text
Go Control Plane Hosted Permission Decision Persistence Implementation v0
```
