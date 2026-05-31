# Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0

日期：2026-05-31

状态：complete

## 决策

在实现真实 hosted public edge 之前，先定义 production trusted-gateway boundary。

Control Plane 已经支持并 dogfood 了这个 internal request shape：

```text
trusted gateway secret
  -> trusted X-API2Agent-* claims
  -> AdminPrincipal
  -> endpoint permission check
  -> audit and idempotency evidence
```

本设计定义 production gateway 在把 hosted admin requests 转发给 Control Plane 之前必须满足的 contract。

本设计经用户接受后的推荐下一项任务：

```text
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Implementation v0
```

## 为什么现在做

Control Plane 侧 hosted admin path 已实现并完成 dogfood，但 production boundary 仍然是隐含的：

- 还没有真实 gateway
- gateway header stripping 仍是 assumption
- gateway secret rotation 尚未定义
- permission claim issuance 仍在外部
- deployment 和 observability behavior 尚未指定

下一步最安全的是先做 design pass。该任务不应增加 public CRUD、OAuth/OIDC、provider onboarding、vault、billing、marketplace、workflow runtime 或 automatic propagation。

## Goals

- 定义 gateway-to-Control-Plane trust boundary
- 定义 ingress header stripping 和 trusted header rewrite rules
- 定义 gateway authentication 和 secret rotation policy
- 定义 hosted admin identity 与 permission claim issuance assumptions
- 定义 request/audit evidence contract
- 定义 gateway 和 auth-service outages 的 failure semantics
- 定义 deployment 和 observability expectations
- 命名后续 implementation slice 的 tests
- 命名后续 dogfood requirements

## Non-Goals

- 不实现 OAuth/OIDC provider
- 不实现 end-user signup、login、invitation 或 admin UI
- 不部署真实 public gateway
- 不增加 public registry CRUD APIs
- 不增加 provider self-onboarding
- 不增加 marketplace provider submission
- 不增加 credential vault writes
- 不增加 plaintext secret storage
- 不增加 billing or settlement state
- 不增加 workflow engine
- 不增加 automatic snapshot export、publish 或 Data Plane reload
- 不让 Data Plane 从 mutable Control Plane tables 读取

## Boundary Model

Production boundary 是：

```text
public admin client
  -> production trusted gateway
  -> private Control Plane admin HTTP endpoint
```

Control Plane 绝不能直接信任 public client identity headers。

Gateway 负责：

- public caller authentication
- public session/token validation
- tenant/project membership lookup
- admin permission derivation
- trusted header stripping
- trusted claim injection
- gateway-to-Control-Plane authentication
- request correlation propagation

Control Plane 负责：

- gateway authentication
- trusted claim parsing
- endpoint permission enforcement
- admin mutation semantics
- audit evidence
- idempotency scope and replay behavior
- stable error envelope

## Gateway Ingress Rules

转发到 Control Plane 之前，gateway 必须移除所有 caller-supplied internal headers：

```text
X-API2Agent-*
```

除非后续设计明确需要，gateway 也必须移除或不转发 public credentials：

```text
Authorization
Cookie
Set-Cookie
Proxy-Authorization
X-Actor-ID
X-Project-ID
X-Organization-ID
```

Control Plane 在 trusted-gateway mode 下已经会忽略 public identity headers。Gateway 仍必须 strip 它们，避免 logs、proxies 或 future middleware 混淆 public identity 与 trusted internal identity。

## Gateway-To-Control-Plane Authentication

Gateway 用以下 header 向 Control Plane 认证自身：

```text
X-API2Agent-Gateway-Authorization: Bearer <gateway-secret>
```

规则：

- hosted/trusted-gateway mode 下每个 `/v1/admin/*` request 都必须有 gateway auth
- gateway secret 至少应有 256 bits entropy
- gateway secret 只能存在 deployment secret storage 中
- gateway secret 不得进入 audit metadata、idempotency metadata、logs、metrics labels、errors、traces 或 dogfood reports
- comparison 继续用 fixed hashes 上的 constant-time compare
- `GET /healthz` 保持 public，不要求 gateway auth

## Secret Rotation Design

当前实现支持一个 gateway secret。Production boundary design 要求 rotation-compatible model。

推荐 v0 implementation shape：

```text
TrustedGatewaySecrets = active secret set
TrustedGatewayKeyID   = optional non-secret key identifier
```

Configuration 应支持：

| Purpose | Recommended Config |
| --- | --- |
| active gateway secrets | `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRETS` |
| optional primary key id | `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_KEY_ID` |
| legacy single secret | `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET` |

Rotation policy：

1. 将 new secret 加入 active set。
2. 部署同时接受 old/new secrets 的 Control Plane。
3. 部署使用 new secret 的 gateway。
4. 确认所有 gateway traffic 都使用 new key id 或 deployment version。
5. 从 active set 移除 old secret。

Hosted/trusted-gateway mode 下如果没有 active secret，Control Plane 应 fail startup 或 fail authenticator construction。

Optional key id 不是 secret。它可用于 diagnostics，但不能作为 authentication 的充分条件。

## Trusted Header Rewrite Rules

Gateway 完成 public caller authentication 和 authorization derivation 后，注入：

| Header | Required | Source |
| --- | --- | --- |
| `X-API2Agent-Gateway-Authorization` | yes | gateway deployment secret |
| `X-API2Agent-Gateway-Key-ID` | optional | active gateway key id |
| `X-API2Agent-Principal-ID` | yes | authenticated user or service principal |
| `X-API2Agent-Actor-ID` | optional | acting user, defaults to principal at Control Plane |
| `X-API2Agent-Project-ID` | yes | selected project or tenant context |
| `X-API2Agent-Organization-ID` | optional | selected organization context |
| `X-API2Agent-Token-ID` | optional | public auth token/session id, never raw token |
| `X-API2Agent-Roles` | optional | derived roles |
| `X-API2Agent-Permissions` | yes | derived endpoint permissions |

Gateway 必须从零 rewrite 这些 headers，不得保留 caller-supplied values。

## Identity Claim Contract

Required claims：

- `PrincipalID`
- `ProjectID`
- `Permissions`

推荐规则：

- `PrincipalID` 应 stable，尽量 non-human-readable。
- `ActorID` 表示 effective actor，在 Control Plane 侧默认等于 `PrincipalID`。
- `ProjectID` 是 audit 和 idempotency 的 tenant/project scope。
- project 属于 organization 时，应包含 `OrganizationID`。
- `TokenID` 标识 public session/token record，但不暴露 raw credentials。
- role strings 暂时只作为 informational。
- permission strings 对 endpoint access 具有 authoritative meaning。
- v0 不包含 wildcard permissions。

## Permission Issuance Contract

Gateway 或其 auth backend 根据 authenticated identity、project membership 和 admin policy 派生 endpoint permissions。

当前 endpoint permissions：

| Permission | Endpoint |
| --- | --- |
| `control_plane.registry.validate` | `POST /v1/admin/registry/validate` |
| `control_plane.registry.import_replace` | `POST /v1/admin/registry/import-replace` |
| `control_plane.snapshot.export_artifact` | `POST /v1/admin/snapshots/export-artifact` |
| `control_plane.distribution.publish` | `POST /v1/admin/distribution/publish` |
| `control_plane.distribution.read_current` | `GET /v1/admin/distribution/current` |

规则：

- permissions 必须按 request 做 least-privilege
- missing permission 返回 `403 AUTHZ_DENIED`
- unknown permissions 可以作为 strings 透传，但不会 grant access
- permission issuance failures 应止于 gateway，不应调用 Control Plane

## Audit And Evidence Contract

Control Plane audit record 必须保留：

- actor id
- principal subject id
- project id
- organization id when present
- auth method
- token id when present
- local/private status
- request id when supplied
- action、resource、outcome 和 error type

Control Plane idempotency scope 保持：

```text
project_id + actor_id + operation + idempotency_key_hash
```

不得存储：

- gateway secret
- raw public bearer token
- raw cookies
- raw session material
- raw authorization headers

## Failure Semantics

Gateway behavior：

- unauthenticated public caller：gateway 返回 public `401`
- authenticated caller missing admin policy：gateway 返回 public `403`
- auth backend unavailable：gateway 返回 public `503` 或等价 platform error
- gateway 无法 derive project context：根据 caller actionability 返回 public `403` 或 `400`
- gateway 无法 reach Control Plane：gateway 返回 public platform error，不得 synthesize mutation success

Control Plane behavior：

- missing/malformed/wrong gateway auth：`401 AUTH_ERROR`
- missing trusted required claim：`401 AUTH_ERROR`
- malformed trusted claim：`401 AUTH_ERROR`
- missing endpoint permission：`403 AUTHZ_DENIED`
- trusted-gateway mode without active secret：`503 AUTH_SERVICE_UNAVAILABLE`
- mutation/idempotency/persistence failures 保持现有 stable error envelope

## Deployment Expectations

Production deployment 应满足：

- Control Plane admin endpoints 不直接 public
- 只有 gateway 能访问 hosted `/v1/admin/*` endpoints
- gateway 和 Control Plane 通过 private networking 或等价 transport protection 通信
- gateway secret 由 secret manager 注入，不进入 source control
- gateway 每个 request 都 strip and rewrite trusted headers
- gateway forward 或 create request id 用于 correlation
- deployment 可以无停机 rotate gateway secrets

## Observability Expectations

Metrics/logs/traces 应暴露：

- 不含 secret values 的 gateway auth success/failure counts
- 按 endpoint 和 permission 维度的 authz denial counts
- 不含 secret values 的 trusted-gateway mode startup configuration state
- safe 时的 active key id 或 deployment version
- gateway 与 Control Plane 之间的 request id correlation
- audit write failures 和 idempotency store failures

Metrics/logs/traces 不得暴露：

- raw gateway secret
- raw public bearer token
- cookies
- raw trusted header values that contain sensitive identifiers，除非显式批准

## Implementation Test Requirements

后续 implementation slice 应添加 tests：

- multiple active gateway secrets accepted
- old secret removed after rotation is rejected
- optional gateway key id 只作为 metadata parse
- no active gateway secret fails closed
- public `X-API2Agent-*` headers 在没有 gateway auth 时被忽略
- forwarded public `Authorization` 不会成为 principal evidence
- audit/idempotency metadata 永不包含 gateway secret
- permission issuance 保持 exact-match and least-privilege
- local/private authenticator 保持兼容

## Dogfood Requirements

后续 dogfood 应：

- 用 multiple active secrets 启动 hosted/trusted-gateway service
- 验证 overlap 期间 old/new secrets 都可用
- 验证移除 old secret 后旧 secret 被拒绝
- 如果实现 `X-API2Agent-Gateway-Key-ID`，验证它只作为 non-secret evidence 出现
- 验证 public identity headers 不能覆盖 gateway claims
- 验证 audit 和 idempotency evidence 仍使用 trusted claims
- 验证 output artifacts 不包含 raw secret

## Open Questions

- gateway key id 应持久化到 audit metadata，还是只进入 logs/metrics？
- active secrets 应配置为 raw secret values、secret references，还是两者都支持？
- permission issuance 应位于 gateway process，还是单独 identity/policy service？
- gateway 之后是否应签发 structured claims，而不是转发 headers？

## Acceptance Criteria For This Design

- production gateway trust boundary 明确
- trusted header strip/rewrite rules 明确
- gateway secret rotation approach 明确
- permission issuance assumptions 明确
- audit and idempotency evidence contract 明确
- deployment and observability expectations 明确
- implementation tests and dogfood requirements 已命名
- 未引入 public CRUD、OAuth implementation、provider onboarding、vault、billing、marketplace、workflow 或 automatic propagation
