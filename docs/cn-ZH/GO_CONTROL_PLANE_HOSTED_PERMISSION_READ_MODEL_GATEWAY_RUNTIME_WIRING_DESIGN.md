# Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Design v0

日期：2026-06-02

状态：complete

## 决策

下一项 hosted-readiness implementation slice 应把 local hosted admin gateway permission source 接到 internal hosted permission read model。

推荐下一项 implementation task：

```text
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Implementation v0
```

实现应保持 local/dogfood-scoped。它应在配置 Postgres DSN 时，用 read-model-backed permission source 替换 gateway harness 的 static hosted permission fixture，同时保留现有 static fixture 作为 test fallback。不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、decision persistence，或 Data Plane 从 mutable Control Plane tables 读取。

## 为什么现在做

hosted admin path 现在已经具备：

- trusted gateway authentication 和 header rewriting
- hosted admin routes 的 endpoint permission mapping
- gateway-local fail-closed permission decisions
- Control Plane endpoint checks 作为第二道 authorization gate
- tenant-partitioned project mutation
- durable hosted permission schema
- hosted permission tables 上的 internal Go read model
- live Postgres dogfood 已证明 read model 可以在真实 schema 和 seeded rows 上工作

剩余 gap 是 runtime wiring：gateway 仍使用 local/static permission fixture。下一项 implementation 应把已证明的 read model 接到 gateway permission-source boundary，同时不改变 public identity、policy management、production deployment 或 Control Plane authorization semantics。

## 当前 Baseline

local gateway harness 当前会：

1. 消费 public `Authorization`。
2. 把 dogfood public bearer tokens 映射为 `PublicPrincipal`。
3. 从 local hosted-permission-shaped fixture 解析 permissions。
4. forwarding 前检查 endpoint required permission。
5. strip caller-supplied public/trusted identity headers。
6. 注入 gateway-issued trusted `X-API2Agent-*` headers。
7. 用 trusted gateway authorization 转发到 private Control Plane。

internal read model 当前会：

1. 打开 Postgres-backed `HostedPermissionReadModel`。
2. 解析 subject、membership、roles、grants、active policy 和 decision evidence。
3. 对 missing membership、suspended membership、revoked/missing permission、no active policy 和 ambiguous active policy fail closed。
4. 返回 gateway-compatible decision shape。
5. v0 不持久化 `hosted_permission_decisions`。

## Goals

- 定义 gateway runtime permission source 如何调用 hosted permission read model
- 保留 gateway-local public auth 和 route permission mapping
- 保留 trusted header stripping 和 gateway-issued trusted header injection
- 保留 Control Plane endpoint permission checks 作为 second gate
- read model 或 backing store unavailable 时 fail closed
- 保持 policy/source/fingerprint/decision evidence secret-safe
- decision persistence 继续 deferred
- public auth provider implementation 和 public role CRUD 保持 out of scope
- 定义下一 slice 的 implementation tests 和 dogfood

## Non-Goals

不要实现或设计：

- OAuth/OIDC provider integration
- login/session/user lifecycle
- invitation management
- public project/user/role/permission CRUD
- hosted policy write APIs
- decision persistence
- provider onboarding
- marketplace/provider submission
- credential vault writes
- billing or settlement
- workflow runtime
- production gateway deployment
- automatic snapshot publish/reload
- Data Plane reads from mutable Control Plane tables

## Runtime Boundary

read-model call 由 gateway 持有：

```text
public request
  -> gateway public auth
  -> endpoint permission mapping
  -> hosted permission source
  -> HostedPermissionReadModel.Resolve
  -> gateway-local allow/deny decision
  -> trusted header injection
  -> private Control Plane request
  -> Control Plane trusted-gateway auth
  -> Control Plane endpoint permission check
```

private Control Plane 在 endpoint authorization 时不得读取 hosted permission tables。它只接收 gateway-issued trusted claims 和可选的 non-secret decision evidence headers。

## Proposed Gateway Interface

概念 Go interface：

```go
type GatewayPermissionSource interface {
    Resolve(ctx context.Context, req GatewayPermissionLookupRequest) (GatewayPermissionDecision, error)
}
```

Request：

```go
type GatewayPermissionLookupRequest struct {
    PublicPrincipalID  string
    ExternalSubjectRef string
    ProjectID          string
    TokenID            string
    Method             string
    Path               string
    RequiredPermission string
    RequestID          string
    ResolvedAt         time.Time
}
```

Decision：

```go
type GatewayPermissionDecision struct {
    Allowed            bool
    Status             int
    ErrorType          string
    DenyReason         string
    SubjectID          string
    ActorID            string
    ProjectID          string
    OrganizationID     string
    TokenID            string
    Roles              []string
    Permissions        []string
    RequiredPermission string
    PolicySource       string
    PolicyVersion      string
    PolicyFingerprint  string
    DecisionID         string
    ResolvedAt         time.Time
}
```

read-model-backed implementation 应把该 request 适配为：

```go
registry.HostedPermissionLookupRequest
```

并把：

```go
registry.HostedPermissionDecision
```

转换为 gateway decision shape。

## Public Principal Input

v0 runtime wiring 中，public auth 仍保持 dogfood/local：

- public bearer token parsing 仍在 gateway。
- token-to-principal mapping 仍是 local dogfood map 或 fixture。
- mapping 产生 `public_principal_id`、`external_subject_ref` 和 non-secret `token_id`。
- raw public bearer tokens 永远不传给 read model。
- raw public bearer tokens 永远不转发给 Control Plane。
- raw public bearer tokens 永远不写入 dogfood artifacts 或 audit/idempotency evidence。

实现应使用 `external_subject_ref` 作为主要 read-model lookup key。`public_principal_id` 可以作为 evidence/context，并且只有在代码明确需要时才作为 fallback；hosted schema 锚定在 `hosted_subjects.external_subject_ref`。

## Project Context

当前 hosted admin endpoints 的 project context 应从 trusted gateway routing/config 派生，而不是 caller-controlled headers。

当前 dogfood scope：

```text
gateway-harness-project
```

未来 project routing 可以从以下来源派生 project context：

- authenticated hosted project context
- path/routing metadata
- gateway tenancy middleware

Caller-supplied `X-Project-ID`、`X-Actor-ID`、`X-API2Agent-*`、cookies 或任意 query parameters 不得选择 project authorization scope。

## Endpoint Permission Mapping

gateway runtime wiring 必须保留显式 route map：

| Method / Path | Required Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/registry/project-partition/replace` | `control_plane.registry.project_partition_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |

Unknown admin routes 本地 fail，不得触达 Control Plane。

## Configuration

建议 local/dogfood config：

| Config | Purpose |
| --- | --- |
| `permission_source_mode=static` | 现有 fixture behavior，用于 tests。 |
| `permission_source_mode=hosted_read_model` | 对 Postgres 使用 `HostedPermissionReadModel`。 |
| `postgres_dsn` | read-model mode 的 backing store DSN。 |
| `permission_lookup_timeout` | read-model lookup 的短 timeout。 |
| `gateway_project_id` | 在真实 hosted tenancy 出现前使用的 dogfood project context。 |

如果选择 `hosted_read_model` 但没有 DSN，startup 应失败，或 gateway 应在 forwarding 前返回 `503 PERMISSION_SOURCE_UNAVAILABLE`。绝不能 fallback 到 broad static allow。

## Failure Semantics

Gateway-local failures：

| Condition | HTTP | Error Type | Forward? |
| --- | --- | --- |
| missing public auth | `401` | `PUBLIC_AUTH_REQUIRED` | no |
| invalid public token/principal | `401` | `PUBLIC_AUTH_INVALID` | no |
| read model unavailable or DB error | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| lookup timeout | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| no active policy | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| ambiguous active policy | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| missing hosted subject | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| missing project membership | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| suspended membership | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| revoked/missing required permission | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| unknown admin route | `404` | `PUBLIC_ROUTE_NOT_FOUND` | no |
| unsupported method | `405` | `PUBLIC_METHOD_NOT_ALLOWED` | no |

Control Plane failures 仍保持独立：

- invalid trusted gateway auth -> `401 AUTH_ERROR`
- missing trusted permissions -> `403 AUTHZ_DENIED`
- Control Plane auth configuration failure -> `503 AUTH_SERVICE_UNAVAILABLE`

## Trusted Header Mapping

allow 时 gateway 注入：

```text
X-API2Agent-Gateway-Authorization
X-API2Agent-Gateway-Key-ID
X-API2Agent-Principal-ID
X-API2Agent-Actor-ID
X-API2Agent-Project-ID
X-API2Agent-Organization-ID
X-API2Agent-Token-ID
X-API2Agent-Roles
X-API2Agent-Permissions
X-API2Agent-Permission-Source
X-API2Agent-Policy-Version
X-API2Agent-Policy-Fingerprint
X-API2Agent-Permission-Decision-ID
```

Mapping：

| Header | Source |
| --- | --- |
| `X-API2Agent-Principal-ID` | `decision.SubjectID` |
| `X-API2Agent-Actor-ID` | `decision.ActorID` |
| `X-API2Agent-Project-ID` | `decision.ProjectID` |
| `X-API2Agent-Organization-ID` | `decision.OrganizationID` |
| `X-API2Agent-Token-ID` | `decision.TokenID` |
| `X-API2Agent-Roles` | comma-joined `decision.Roles` |
| `X-API2Agent-Permissions` | comma-joined `decision.Permissions` |
| `X-API2Agent-Permission-Source` | `decision.PolicySource` |
| `X-API2Agent-Policy-Version` | `decision.PolicyVersion` |
| `X-API2Agent-Policy-Fingerprint` | `decision.PolicyFingerprint` |
| `X-API2Agent-Permission-Decision-ID` | `decision.DecisionID` |

gateway 必须先 strip caller-supplied versions of all `X-API2Agent-*` headers，再注入自己的 headers。

Control Plane 可以把 policy evidence headers 记录为 metadata，但本 slice 不得用这些 header 做 authorization。Authorization 仍基于 trusted permissions 和 endpoint required-permission checks。

## Request Forwarding Rules

只转发：

- gateway-issued trusted headers
- `X-Request-ID`
- `Idempotency-Key`
- private endpoint 需要的 safe content headers
- request body

不要转发：

- public `Authorization`
- cookies
- caller-supplied identity headers
- raw public tokens
- artifact/audit metadata 中的 raw gateway secrets

## Timeout And Availability

gateway 应用短 timeout 包裹 read-model lookup。

建议 v0 behavior：

- default timeout：小的 dogfood 值，例如 1-2 seconds
- timeout 映射为 `503 PERMISSION_SOURCE_UNAVAILABLE`
- DB open/ping failure 映射为 `503 PERMISSION_SOURCE_UNAVAILABLE`
- query error 映射为 `503 PERMISSION_SOURCE_UNAVAILABLE`
- v0 runtime wiring 不加 cache

如果未来引入 cache，必须单独设计，并受 policy version/fingerprint 约束。本 slice 不应增加 cache behavior。

## Decision Persistence

Decision persistence 保持 out of scope。

read model 应继续返回 decision evidence，而不插入 `hosted_permission_decisions`。Runtime wiring tests 应断言 zero decision rows，除非后续 persistence slice 明确改变该 contract。

## Implementation Test Requirements

新增或更新 tests 以证明：

- hosted read-model permission source 允许 admin validate/import paths。
- readonly principal 可以 validate/read current，但不能 import/replace。
- no membership 本地 fail，且不 forward。
- suspended membership 本地 fail，且不 forward。
- revoked/missing grant 本地 fail，且不 forward。
- no active policy 本地 `503`。
- ambiguous active policy 本地 `503`。
- missing/invalid public auth 仍为 `401`。
- unknown route/method 仍本地 fail。
- caller-supplied trusted headers 被 strip。
- forwarded trusted headers 匹配 read-model decision evidence。
- Control Plane second gate 仍拒绝 forced insufficient trusted permissions。
- dogfood artifacts、audit rows、idempotency rows 不出现 raw public token 或 gateway secret。
- `hosted_permission_decisions` 保持为空。

## Dogfood Requirements

implementation dogfood 应：

1. 启动真实 local Postgres。
2. apply schema。
3. seed registry 和 hosted permission rows。
4. 以 trusted-gateway mode 启动 private Control Plane。
5. 以 `hosted_read_model` permission-source mode 启动 local gateway harness。
6. 通过 gateway HTTP boundary 跑 success 和 denial cases。
7. 检查 Postgres audit/idempotency rows，证明 gateway-local denied requests 没有触达 Control Plane。
8. 断言 artifacts secret-safe。

最小 observed cases：

- admin validate succeeds。
- admin project partition replace 在有 permission 时 succeeds。
- readonly validate succeeds。
- readonly import/replace 本地 fails。
- missing membership 本地 fails。
- suspended membership 本地 fails。
- revoked grant 本地 fails。
- no active policy 本地 `503`。
- ambiguous policy 本地 `503`。
- forced insufficient forwarded permissions 仍在 Control Plane second gate fail。

## Acceptance Criteria

Implementation 可关闭条件：

- gateway runtime 有 hosted read-model permission-source mode。
- static fixture mode 仍可用于 focused local tests。
- real Postgres dogfood 证明 read-model-backed gateway decisions。
- 所有 deny cases 在 forwarding 前 fail。
- trusted header injection 使用 read-model evidence。
- Control Plane second gate 仍权威。
- raw tokens/secrets 不泄漏到 evidence。
- 未新增 decision persistence、public CRUD、OAuth/OIDC、production gateway deployment、marketplace、vault、billing、workflow、automatic propagation 或 Data Plane mutable reads。

## 下一项建议任务

```text
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Implementation v0
```
