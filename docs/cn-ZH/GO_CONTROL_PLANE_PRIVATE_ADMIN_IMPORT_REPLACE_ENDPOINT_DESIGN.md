# Go Control Plane Private Admin Import/Replace Endpoint Design v0

日期：2026-05-31

状态：complete

## 决策

为已经实现的 persistent registry import/replace primitive 增加一份 private admin HTTP contract。

推荐下一项实现任务：

```text
Go Control Plane Private Admin Import/Replace Endpoint Implementation v0
```

这个 endpoint 只是下面这个 registry 层能力的薄 HTTP 包装：

```go
registry.ReplacePersistentRegistry(ctx, db, reg, opts)
```

它不能变成 public registry CRUD surface。

## Endpoint Contract

```text
POST /v1/admin/registry/import-replace
```

这个 endpoint 只面向 private admin。

它从一个完整、已验证的 registry document 替换 Postgres-backed active registry graph，然后返回 registry 层产生的 mutation result。

它不负责 export、publish 或 reload snapshots。

后续流程仍然是：

```text
POST /v1/admin/registry/import-replace
  -> POST /v1/admin/snapshots/export-artifact
  -> POST /v1/admin/distribution/publish
  -> Data Plane reload
```

## Store Boundary

该 endpoint 只在显式 Postgres persistent registry store 下启用。

规则：

- `FileStore` 继续是默认 store。
- file-backed service mode 不能通过这个 endpoint 修改 registry 文件。
- 如果 service 没有配置 Postgres mutation dependency，返回 `409 REGISTRY_MUTATION_UNAVAILABLE`。
- Data Plane 继续消费 snapshots，而不是读取 Control Plane mutable tables。

## Required Headers

| Header | Required | Purpose |
| --- | --- | --- |
| `Authorization: Bearer <admin-token>` | yes | 复用现有 private admin auth boundary。 |
| `X-Request-ID` | yes | 关联 admin request、mutation audit 和 registry revision source。 |
| `Idempotency-Key` | yes | HTTP mutation safety 和 audit traceability 必需。 |
| `X-Actor-ID` | no | local/private actor override。缺省时使用 `admin`。 |

Header 校验：

- `Authorization` 沿用现有 admin-token 行为。
- 缺失或空白 `X-Request-ID` 返回 `400 INVALID_REQUEST`。
- 缺失或空白 `Idempotency-Key` 返回 `400 INVALID_REQUEST`。
- 空白 `X-Actor-ID` 视为未提供。
- implementation 应该 trim surrounding whitespace。

## Request Body

使用 wrapper object，而不是 raw registry JSON。这样 endpoint 以后可以增加 flags，而不改变 top-level contract。

```json
{
  "registry": {
    "projects": [],
    "api_keys": [],
    "capabilities": [],
    "providers": [],
    "credential_metadata": [],
    "routing_policy": {},
    "snapshot": {}
  },
  "source": "admin_http_import",
  "dry_run": false
}
```

字段：

| Field | Required | v0 behavior |
| --- | --- | --- |
| `registry` | yes | 完整 registry document，用于 canonicalize、validate、fingerprint 和 replace。 |
| `source` | no | Audit metadata hint。缺省时使用 `admin_http_import`。 |
| `dry_run` | no | Reserved。省略或 `false` 允许；v0 中 `true` 返回 `400 INVALID_REQUEST`。 |

Credential 规则：

- registry credential rows 仍然只存 metadata。
- 这个 endpoint 不能接收 plaintext API key、OAuth token 或 provider secret。
- 如果未来 registry shape 增加 secret-bearing fields，该 endpoint 必须在 mutation 前拒绝。

## Request Size Limit

v0 应该在 JSON decoding 前限制 HTTP request body。

默认限制：

```text
2 MiB
```

实现提示：

- 使用 `http.MaxBytesReader` 或等价机制。
- body-size failures 返回 `413 REQUEST_BODY_TOO_LARGE`。
- 这个限制以后可以配置化，但 v0 contract 必须有 bounded default。

## Response Shape

当 registry 发生替换：

```http
201 Created
```

```json
{
  "registry_store": "postgres",
  "registry_fingerprint": "sha256:...",
  "previous_registry_fingerprint": "sha256:...",
  "snapshot_version": "snapshot_v1",
  "noop": false,
  "counts": {
    "projects": 1,
    "api_keys": 1,
    "capabilities": 1,
    "providers": 1,
    "credential_metadata": 1,
    "routing_policies": 1,
    "snapshot_configs": 1
  }
}
```

当 fingerprint 相同、无需替换：

```http
200 OK
```

```json
{
  "registry_store": "postgres",
  "registry_fingerprint": "sha256:...",
  "previous_registry_fingerprint": "sha256:...",
  "snapshot_version": "snapshot_v1",
  "noop": true,
  "counts": {
    "projects": 1,
    "api_keys": 1,
    "capabilities": 1,
    "providers": 1,
    "credential_metadata": 1,
    "routing_policies": 1,
    "snapshot_configs": 1
  }
}
```

## Registry Mutation Options Mapping

将 HTTP request identity 映射到 registry-layer options：

```go
registry.ImportReplaceOptions{
    ActorID:        actorIDFromHeaderOrAdmin,
    RequestID:      requestIDHeader,
    IdempotencyKey: idempotencyKeyHeader,
    Source:         request.SourceOrDefault,
}
```

规则：

- `RequestID` 必须来自 `X-Request-ID`。
- `IdempotencyKey` 必须来自 `Idempotency-Key`。
- `ActorID` 在 local/private 场景下来自 `X-Actor-ID`，否则为 `admin`。
- 未来 hosted auth 可以用 authenticated principal 替代 `X-Actor-ID`，但必须保留 audit field。

## Status Codes And Error Mapping

endpoint 必须复用当前 service error envelope：

```json
{
  "error": {
    "error_type": "REGISTRY_MUTATION_INVALID",
    "error_scope": "caller",
    "message": "...",
    "retryable": false
  }
}
```

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| Missing or invalid admin token | 401 | `AUTH_ERROR` | caller | false |
| Wrong method | 405 | `INVALID_REQUEST` | caller | false |
| Missing `X-Request-ID` | 400 | `INVALID_REQUEST` | caller | false |
| Missing `Idempotency-Key` | 400 | `INVALID_REQUEST` | caller | false |
| Invalid JSON body | 400 | `INVALID_REQUEST` | caller | false |
| Missing `registry` wrapper field | 400 | `INVALID_REQUEST` | caller | false |
| `dry_run=true` in v0 | 400 | `INVALID_REQUEST` | caller | false |
| Request body over limit | 413 | `REQUEST_BODY_TOO_LARGE` | caller | false |
| Service not configured for Postgres mutation | 409 | `REGISTRY_MUTATION_UNAVAILABLE` | platform | false |
| Invalid registry payload or graph | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| Concurrent registry mutation | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Serializable transaction conflict | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| Persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| Required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

`registry.RegistryMutationError` 应该作为 registry-layer failures 的 source of truth：

- `REGISTRY_MUTATION_INVALID` -> `400`
- `REGISTRY_MUTATION_CONFLICT` -> `409`
- `PERSISTENT_STORE_READ_FAILED` -> `503`
- `PERSISTENT_STORE_WRITE_FAILED` -> `503`
- `AUDIT_WRITE_FAILED` -> `500`

未知 registry-layer errors 应该 fail closed：

```text
500 REGISTRY_MUTATION_FAILED platform retryable=true
```

## Audit Mapping

registry 层已经写入 required success/failure audit evidence。endpoint 必须把 request identity 传下去；不能为同一次 mutation 再写第二条 success audit。

必需 audit action：

```text
registry.import_replace
```

必需 audit metadata：

- `registry_store=postgres`
- `mutation_mode=import_replace`、`import_replace_noop` 或 `import_replace_failure`
- `registry_fingerprint`
- `previous_registry_fingerprint` when available
- `snapshot_version` when available
- `idempotency_key`
- `source`
- object counts：
  - `projects`
  - `api_keys`
  - `capabilities`
  - `providers`
  - `credential_metadata`
  - `routing_policies`
  - `snapshot_configs`

Failure audit 仍然是 best effort，且不能遮蔽原始 HTTP error。

## Idempotency Semantics

HTTP endpoint 要求 `Idempotency-Key`，但 v0 idempotency 仍然基于 registry fingerprint。

含义：

- 如果 incoming fingerprint 等于 current persistent registry fingerprint，返回 `200 OK` 和 `noop=true`。
- 如果 incoming fingerprint 不同，执行 full replace，返回 `201 Created` 和 `noop=false`。
- v0 不引入 idempotency-key result cache。
- 使用相同 key 但不同 registry document 的重复请求，不会被视为等价；它们仍然走正常 fingerprint 和 transaction semantics。

未来增强：

- 未来可以增加 request-id/idempotency-key table，用于发现 idempotency key 的冲突复用。
- 这不是 v0 implementation 必需项。

## Implementation Seam

推荐 service seam：

```go
type RegistryImportReplacer interface {
    ReplacePersistentRegistry(ctx context.Context, reg registry.Registry, opts registry.ImportReplaceOptions) (registry.ImportReplaceResult, error)
}
```

也可以使用围绕现有 Postgres DB handle 的更窄 handler dependency。

endpoint 不能绕过 registry 层手写 table mutations。

## Tests Required For Implementation

最低测试：

- endpoint 注册在 `POST /v1/admin/registry/import-replace`
- admin token 必需
- `X-Request-ID` 必需
- `Idempotency-Key` 必需
- invalid JSON 返回 `400 INVALID_REQUEST`
- 缺失 `registry` 返回 `400 INVALID_REQUEST`
- `dry_run=true` 返回 `400 INVALID_REQUEST`
- over-limit body 返回 `413 REQUEST_BODY_TOO_LARGE`
- file-store/unconfigured mutation 返回 `409 REGISTRY_MUTATION_UNAVAILABLE`
- changed registry 返回 `201` 和 registry-layer result
- no-op registry 返回 `200` 和 `noop=true`
- `RegistryMutationError` values 映射到稳定 HTTP status 和 error response fields
- actor/request/idempotency/source 会传入 `ImportReplaceOptions`
- import/replace 不触发 snapshot export/publish/reload

## Non-Goals

- no public CRUD registry APIs
- no provider self-onboarding
- no marketplace provider submission
- no credential vault writes
- no plaintext API key storage
- no billing, settlement, or revenue-share state
- no workflow engine
- no automatic snapshot export, publish, or Data Plane reload
- no direct Data Plane reads from Control Plane mutable tables

## Acceptance Criteria

这个 design 被接受的条件：

- endpoint method/path 已文档化
- request/response schema 已文档化
- required headers 和 identity mapping 已文档化
- idempotency behavior 已文档化
- error mapping 已文档化
- audit mapping 已文档化
- request size limit 已文档化
- snapshot boundary 保持明确
- implementation 继续推迟到下一项任务

