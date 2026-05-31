# Go Control Plane Hosted Admin Identity Boundary Design v0

日期：2026-05-31

状态：complete

## 决策

在增加更多 write surfaces 之前，为 private Control Plane mutation endpoints 定义 hosted admin identity boundary。

这个 boundary 引入 resolved admin principal shape，HTTP 层可以把它传给 registry mutations、audit writes 和 idempotency scope derivation。

这是 design task。它不实现 hosted identity provider、user database、organization model、public CRUD API 或新的 mutation endpoint。

设计被接受后的推荐下一项任务：

```text
Go Control Plane Hosted Admin Identity Boundary Implementation v0
```

## 为什么下一项是它

当前 private admin API 对 local dogfood 足够安全，但它不是 hosted identity model：

- `Authorization: Bearer <admin-token>` 只能证明持有 shared local token。
- `X-Actor-ID` 由 caller 提供，在 hosted mode 下不能信任。
- idempotency records 当前默认把 `project_id` 填成 `control_plane`。
- 增加更多 mutation endpoints 前，admin audit rows 需要稳定 principal attribution。
- 扩展 public 或 hosted write surfaces 前，必须先有 permission checks。

## 目标

- 定义 Control Plane 使用的 admin principal fields
- 定义 local/private compatibility behavior
- 定义 hosted-mode actor 和 project derivation
- 定义 endpoint permission names
- 定义 audit identity mapping
- 定义 idempotency `project_id` 和 `actor_id` derivation
- 定义稳定 auth/authz error mapping
- 为后续 implementation slice 命名 tests

## Non-Goals

- no public registry CRUD APIs
- no hosted user signup、login、invitation 或 UI
- no OAuth/OIDC integration implementation
- no provider self-onboarding
- no marketplace provider submission
- no credential vault writes
- no plaintext secret storage
- no billing or settlement state
- no workflow engine
- no automatic snapshot export、publish 或 Data Plane reload
- no Data Plane reads from mutable Control Plane tables

## Modes

Control Plane 应支持两个显式 admin identity modes。

| Mode | Purpose | Actor source | Project source |
| --- | --- | --- | --- |
| `local_private` | 当前 local dogfood 和 private service use | bearer token auth 后的 `X-Actor-ID` 或 `admin` | `control_plane` |
| `hosted` | 未来 hosted Control Plane | authenticated principal | authenticated principal 或 trusted gateway claims |

mode 必须来自明确 service configuration。不能通过任意 headers 的存在来推断 hosted behavior。

## Admin Principal Shape

HTTP 层应把 requests 解析成：

```go
type AdminPrincipal struct {
    SubjectID    string
    ActorID      string
    ProjectID    string
    OrganizationID string
    AuthMethod   string
    TokenID      string
    Roles        []string
    Permissions  []string
    LocalPrivate bool
}
```

字段含义：

| Field | Required | Meaning |
| --- | --- | --- |
| `SubjectID` | hosted yes, local optional | 稳定 authenticated subject，例如 user/service-account id。 |
| `ActorID` | yes | Audit actor 和 idempotency actor scope。 |
| `ProjectID` | yes | Mutation 和 idempotency project scope。 |
| `OrganizationID` | hosted optional | Project 上层 tenant grouping。 |
| `AuthMethod` | yes | `local_admin_token`、`hosted_admin_token`、`trusted_gateway` 或之后 provider-specific method。 |
| `TokenID` | optional | 用于 audit correlation 的 non-secret token/session identifier。 |
| `Roles` | optional | 粗粒度 labels，例如 `control_plane_admin`。 |
| `Permissions` | yes | endpoint 检查的 fine-grained permission names。 |
| `LocalPrivate` | yes | 只在 local/private compatibility mode 中为 true。 |

`ActorID` 必须稳定，且不能包含 raw bearer tokens、raw API keys、未规范化 email 或 provider secrets。

## Local Private Compatibility

当前 local behavior 在 `local_private` mode 下继续有效：

- `Authorization: Bearer <admin-token>` 必需。
- missing or invalid bearer token 返回 `401 AUTH_ERROR`。
- `X-Actor-ID` 可以覆盖 local actor id。
- blank `X-Actor-ID` 默认是 `admin`。
- `ProjectID` 默认是 `control_plane`。
- `AuthMethod` 是 `local_admin_token`。
- `Permissions` 包含所有当前 private admin endpoint permissions。

这会保持现有 dogfood scripts 和 local service use 可用。

Local compatibility 必须显式启用。Hosted deployment 不能意外信任 `X-Actor-ID`。

## Hosted Mode Rules

在 `hosted` mode 中：

- `X-Actor-ID` 不能被信任为 identity。
- public clients 不能通过任意 headers 设置 `ProjectID`、`ActorID`、roles 或 permissions。
- Control Plane identity 来源只能是：
  - in-process hosted admin token verifier，或
  - trusted gateway，它会剥离 public identity headers 并注入 verified internal claims
- resolved principal 必须在 mutation handler 执行前包含 `ActorID`、`ProjectID` 和 endpoint permissions。

如果 hosted request 带 `X-Actor-ID`，service 可以忽略它，或把它记录为 untrusted request metadata。它不能变成 `ActorID`。

如果之后使用 trusted gateway headers，必须使用 internal namespace，例如：

```text
X-API2Agent-Principal-ID
X-API2Agent-Project-ID
X-API2Agent-Organization-ID
X-API2Agent-Permissions
```

这些 headers 只有在 gateway verification 和 public-header stripping 之后才有效。不能从 public edge 直接接受。

## Permission Names

使用 fine-grained permission strings。

| Endpoint | Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |

v0 中，local private admin token 授予这些全部 permissions。

Hosted mode 应尽可能在解析或执行 mutation body 前检查 required permission。

## HTTP Error Mapping

继续使用现有 error envelope。

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| Missing/invalid credentials | 401 | `AUTH_ERROR` | caller | false |
| Valid principal lacks permission | 403 | `AUTHZ_DENIED` | caller | false |
| Principal has no project scope | 403 | `AUTHZ_DENIED` | caller | false |
| Trusted gateway identity header is malformed | 401 | `AUTH_ERROR` | caller | false |
| Identity verifier unavailable | 503 | `AUTH_SERVICE_UNAVAILABLE` | platform | true |

Local/private mode 下不要用 `404` 隐藏 private admin endpoints。当前这些 endpoints 已经在 admin auth 后面，并使用显式 auth errors。

## Audit Mapping

Admin audit events 应使用：

```text
actor_id = principal.ActorID
```

必需 audit metadata additions：

- `principal_subject_id`
- `project_id`
- `organization_id` when available
- `auth_method`
- `token_id` when available
- `local_private=true|false`

现有 action/resource/outcome/error fields 保持不变。

Hosted mode 不能把 caller-supplied `X-Actor-ID` 写成 audit actor。

## Idempotency Mapping

`registry.ImportReplaceOptions` 已有：

```go
ProjectID string
ActorID   string
```

Identity resolution 必须填充：

```text
ProjectID = principal.ProjectID
ActorID   = principal.ActorID
```

Local/private compatibility：

```text
ProjectID = control_plane
ActorID   = X-Actor-ID or admin
```

Hosted mode：

```text
ProjectID = authenticated project scope
ActorID   = authenticated principal actor id
```

这样 idempotency records 会按 tenant/project 和 authenticated actor 分 scope，而不是按 caller-supplied actor header。

## Handler Shape

推荐 HTTP seam：

```go
type AdminAuthenticator interface {
    ResolveAdminPrincipal(r *http.Request, requiredPermission string) (registry.AdminPrincipal, error)
}
```

handler 应该：

1. Check method。
2. Resolve principal and permission。
3. Validate request identity headers，例如 `X-Request-ID` 和 `Idempotency-Key`。
4. Parse and validate body。
5. 将 principal-derived `ProjectID` 和 `ActorID` 传入 registry-layer options。

只写 service-level audit evidence 的 endpoints 也应该使用同一个 principal 写 audit rows。

## Registry Package Shape

registry package 可以拥有 shared struct，避免 HTTP-only identity types 不一致地泄漏：

```go
type AdminPrincipal struct {
    SubjectID      string
    ActorID        string
    ProjectID      string
    OrganizationID string
    AuthMethod     string
    TokenID        string
    Roles          []string
    Permissions    []string
    LocalPrivate   bool
}
```

`ImportReplaceOptions` 继续只携带 mutation primitive 需要的字段：

- `ProjectID`
- `ActorID`
- `RequestID`
- `IdempotencyKey`
- `Source`

不要把 raw auth tokens 传入 registry-layer mutation options。

## Security Rules

- Hosted mode 无法 resolve identity 时必须 fail closed。
- Hosted mode 不能信任 `X-Actor-ID`。
- Hosted mode 不能信任 public `X-Project-ID` 或 `X-Organization-ID`。
- Trusted gateway headers 必须在 edge stripping 后再注入。
- Raw bearer tokens 不能写入 audit、idempotency records 或 error messages。
- Permission denial 必须发生在 mutation side effects 前。
- Request replay 必须使用 resolved principal 派生的 idempotency scope。

## Tests Required For Implementation

HTTP/auth tests：

- local mode 继续接受 bearer admin token
- local mode 将 blank `X-Actor-ID` 映射为 `admin`
- local mode 将 nonblank `X-Actor-ID` 映射为 actor id
- hosted mode 忽略或拒绝 caller-supplied `X-Actor-ID`
- hosted mode 要求 resolved principal
- hosted mode 在缺少 permission 时返回 `403 AUTHZ_DENIED`
- hosted mode 把 principal `ProjectID` 和 `ActorID` 传入 `ImportReplaceOptions`
- malformed trusted gateway identity 返回 `401 AUTH_ERROR`

Audit/idempotency tests：

- admin audit actor 来自 resolved principal
- audit metadata 包含 project 和 auth method
- idempotency scope 使用 principal project 和 actor
- same idempotency key 可以被不同 project scopes 独立复用
- raw auth tokens 不出现在 audit 和 idempotency metadata

Regression tests：

- local dogfood behavior 保持兼容
- private admin import/replace 仍要求 `X-Request-ID`
- private admin import/replace 仍要求 `Idempotency-Key`
- file-store mutation 仍不可用
- 不增加 snapshot export、publish 或 Data Plane reload

## Acceptance Criteria

这个 design 被接受的条件：

- admin principal shape 已文档化
- local/private compatibility behavior 已文档化
- hosted-mode identity trust rules 已文档化
- endpoint permission names 已文档化
- audit identity mapping 已文档化
- idempotency identity mapping 已文档化
- error mapping 已文档化
- implementation tests 已命名
- public CRUD、vault、billing、marketplace、workflow、provider onboarding 和 automatic propagation 继续 out of scope
