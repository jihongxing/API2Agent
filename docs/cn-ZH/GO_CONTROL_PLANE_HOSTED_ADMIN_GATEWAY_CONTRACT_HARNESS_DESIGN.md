# Go Control Plane Hosted Admin Gateway Contract Harness Design v0

日期：2026-05-31

状态：complete

## 决策

在构建任何真实 public gateway 之前，先增加 local hosted admin gateway contract harness。

Harness 是 dogfood-only gateway process，用来证明这条边界：

```text
public dogfood request
  -> local gateway harness
  -> strip caller-supplied trusted headers
  -> inject static trusted claims
  -> authenticate to Control Plane with gateway secret
  -> private Control Plane admin endpoint
```

本设计经用户接受后的推荐下一项任务：

```text
Go Control Plane Hosted Admin Gateway Contract Harness Implementation v0
```

## 为什么现在做

Control Plane 侧 trusted-gateway mechanics 已完成：

- hosted/trusted-gateway authenticator
- active gateway secret set
- gateway key-id evidence
- audit/idempotency identity propagation
- live direct-to-Control-Plane dogfood

剩余未证明的边界是 gateway behavior 本身。当前 dogfood 直接把 trusted headers 发到 Control Plane。下一项证明应运行 local gateway process，由它接收 public requests、strip spoofed headers、inject trusted claims，并转发到 Control Plane。

## Goals

- 定义 local gateway harness responsibilities
- 定义 public auth stubs，但不实现 OAuth/OIDC
- 定义 static identity and permission policy
- 定义 public header stripping matrix
- 定义 trusted claim injection rules
- 定义 gateway secret and key-id forwarding rules
- 定义 request id and idempotency header propagation
- 定义 negative spoofing cases
- 定义 dogfood evidence and acceptance criteria

## Non-Goals

- 不部署真实 public gateway
- 不实现 OAuth/OIDC provider
- 不实现 signup、login、invitation 或 user lifecycle
- 不增加 public registry CRUD APIs
- 不增加 provider onboarding
- 不增加 marketplace provider submission
- 不增加 credential vault writes
- 不增加 plaintext secret storage
- 不增加 billing or settlement state
- 不增加 workflow engine
- 不增加 automatic snapshot export、publish 或 Data Plane reload
- 不让 Data Plane 从 mutable Control Plane tables 读取

## Harness Shape

推荐实现：

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
```

脚本应启动：

```text
podman Postgres
  -> api2agent-controlplane serve
  -> local gateway harness HTTP server
  -> public dogfood HTTP requests to gateway
```

Harness 可以用 Python standard library HTTP server 和 forwarding 实现。它不是 production code，而是一个 contract harness，用真实 HTTP hops 练习 production boundary rules。

## Public Gateway Endpoints

Harness 只应 forward dogfood 需要的当前 admin endpoints：

| Public Harness Endpoint | Forwarded Control Plane Endpoint |
| --- | --- |
| `GET /healthz` | `GET /healthz` |
| `POST /v1/admin/registry/validate` | `POST /v1/admin/registry/validate` |
| `POST /v1/admin/registry/import-replace` | `POST /v1/admin/registry/import-replace` |

其他 paths 应由 harness 本地返回 `404` 或 `405`。

## Static Public Auth

Harness 只使用 static dogfood bearer tokens：

| Public Token | Meaning |
| --- | --- |
| `dogfood-public-admin-token` | full hosted admin test identity |
| `dogfood-public-readonly-token` | authenticated identity without registry mutation permission |

规则：

- missing public `Authorization` 返回 gateway-local `401`
- wrong public token 返回 gateway-local `401`
- valid token 映射到 static identity and permissions
- 不增加 OAuth/OIDC、cookies、sessions、database 或 user lifecycle

## Static Identity Policy

Full admin token 映射为：

```text
principal_id = gateway-harness-principal
actor_id = gateway-harness-actor
project_id = gateway-harness-project
organization_id = gateway-harness-org
token_id = gateway-harness-token-admin
roles = control-plane-admin,dogfood
permissions =
  control_plane.registry.validate
  control_plane.registry.import_replace
```

Readonly token 映射为：

```text
principal_id = gateway-harness-readonly-principal
actor_id = gateway-harness-readonly-actor
project_id = gateway-harness-project
organization_id = gateway-harness-org
token_id = gateway-harness-token-readonly
roles = control-plane-readonly,dogfood
permissions =
  control_plane.distribution.read_current
```

Readonly token 可用于证明 gateway 转发 insufficient endpoint permission 时，Control Plane 仍返回 `403 AUTHZ_DENIED`。

## Header Stripping Matrix

Harness 转发前必须移除 caller-supplied versions of these headers：

| Header Pattern | Action |
| --- | --- |
| `X-API2Agent-*` | strip all caller values |
| `X-API2Agent-Gateway-Authorization` | strip caller value and inject harness secret |
| `X-API2Agent-Gateway-Key-ID` | strip caller value and inject harness key id |
| `X-API2Agent-Principal-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Actor-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Project-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Organization-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Token-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Roles` | strip caller value and inject static policy value |
| `X-API2Agent-Permissions` | strip caller value and inject static policy value |
| `X-Actor-ID` | strip |
| `X-Project-ID` | strip |
| `X-Organization-ID` | strip |
| `Cookie` | strip |
| `Proxy-Authorization` | strip |
| public `Authorization` | consume locally, do not forward |

Harness 应在 normalization 后 forward body handling 需要的 safe request headers，例如 `Content-Type`。

## Trusted Header Injection

Public auth 成功后，harness 注入：

```text
X-API2Agent-Gateway-Authorization: Bearer <gateway-secret>
X-API2Agent-Gateway-Key-ID: <gateway-key-id>
X-API2Agent-Principal-ID: <principal-id>
X-API2Agent-Actor-ID: <actor-id>
X-API2Agent-Project-ID: <project-id>
X-API2Agent-Organization-ID: <organization-id>
X-API2Agent-Token-ID: <token-id>
X-API2Agent-Roles: <comma-separated roles>
X-API2Agent-Permissions: <comma-separated permissions>
```

Harness 应使用 Control Plane service 配置接受的同一个 gateway secret 和 key id。

## Propagated Request Headers

Harness 应保留：

| Header | Reason |
| --- | --- |
| `X-Request-ID` | audit/request correlation |
| `Idempotency-Key` | import/replace idempotency |
| `Content-Type` | request body parsing |

Harness 不应 synthesize mutation success。Control Plane responses 应原样 proxy 回 public dogfood caller。

## Dogfood Scenarios

后续 implementation dogfood 应验证：

1. 通过 harness 调用 `GET /healthz` 返回 `200`。
2. valid public admin token 加 spoofed trusted headers 调用 registry validate 返回 `200`。
3. Audit metadata 使用 harness-injected identity，而不是 spoofed caller headers。
4. Caller-supplied `X-API2Agent-Gateway-Authorization` 被 strip 并 replace。
5. Missing public token 返回 gateway-local `401`，且不创建 Control Plane audit rows。
6. Readonly public token 调用 registry validate 或 import/replace 返回 Control Plane 的 `403 AUTHZ_DENIED`。
7. Full admin token 通过 harness import/replace 返回 `201`。
8. Import/replace idempotency row 使用 harness-injected project 和 actor。
9. Audit metadata 包含 harness gateway key id。
10. Raw public bearer token 和 raw gateway secret 不出现在 audit/idempotency evidence 或 report artifacts。

## Evidence Queries

如果 Postgres 可用，dogfood 应 query：

- `admin_audit_events`
- `admin_mutation_idempotency_records`
- `registry_revisions`

Expected evidence：

- audit actor 等于 harness-injected actor
- audit metadata principal/project/org/token/key id 等于 harness policy
- spoofed public actor/project/principal values 不存在
- idempotency project/actor 等于 harness policy
- raw gateway secret 不存在
- raw public token 不存在

## Failure Semantics

Gateway-local failures：

- missing public auth：`401`
- wrong public auth：`401`
- unsupported path：`404`
- unsupported method：`405`
- invalid request body forwarding failure：dogfood harness 返回 `502` 或 `500`

Control Plane propagated failures：

- insufficient trusted permissions：`403 AUTHZ_DENIED`
- gateway forwarding 后缺失 idempotency headers：现有 Control Plane `400 INVALID_REQUEST`
- mutation/persistence failures：现有 Control Plane stable error envelope

## Implementation Test Requirements

后续 implementation 应包含 tests：

- header stripping function removes all `X-API2Agent-*` caller headers
- public `Authorization` 被 consume 且不会 forward
- static full-admin policy injects expected claims
- static readonly policy injects limited permissions
- `X-Request-ID` 和 `Idempotency-Key` 被 preserve
- unsupported paths/methods 本地 fail

## Acceptance Criteria For This Design

- local gateway harness responsibilities 明确
- static public auth and identity policy 明确
- public header stripping matrix 明确
- trusted claim injection rules 明确
- request id and idempotency propagation 明确
- negative spoofing cases 已命名
- dogfood evidence requirements 明确
- 未引入 OAuth/OIDC、public CRUD、provider onboarding、vault、billing、marketplace、workflow 或 automatic propagation
