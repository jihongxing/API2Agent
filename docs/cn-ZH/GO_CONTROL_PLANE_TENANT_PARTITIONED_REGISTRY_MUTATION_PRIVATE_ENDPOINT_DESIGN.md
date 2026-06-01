# Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Design v0

日期：2026-06-01

状态：complete

## 决策

新增一个 private hosted admin endpoint contract，用于 project-scoped registry replacement：

```text
POST /v1/admin/registry/project-partition/replace
```

这份设计不实现 endpoint。它定义下一步 implementation boundary：把已有 hosted trusted-gateway principal、permission-source proof、admin idempotency store、persistent registry replacement transaction 和 tenant-partition validation helper 组合起来。

建议下一项实现任务：

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Implementation v0
```

这个 endpoint 不能变成 public CRUD。它是 private Control Plane admin surface，只能在 hosted gateway 已完成 public caller 认证、strip caller-supplied trusted headers、注入 trusted project-scoped claims，并经 trusted gateway boundary 转发之后访问。

## 为什么现在做这片

之前几片已经证明：

- hosted admin identity shape 和 trusted-gateway principal resolution
- gateway-side trusted header stripping 与 injection
- gateway-local permission-source decisions
- Control Plane endpoint permission checks 作为第二道 gate
- project-scoped audit 与 idempotency evidence
- local partition validation 可以拒绝 cross-project 和 global registry edits

剩余风险是 endpoint composition：

```text
hosted project principal
  -> project partition endpoint
  -> persistent registry transaction
  -> partition validator
  -> revision + audit + idempotency evidence
```

implementation 必须让 partition validator 成为同一个 write transaction 的一部分。HTTP handler 如果先在 transaction 外读取 current registry，再调用 validator，之后再调用 replacement，会留下 stale-check gap。因此这份设计要求新增 registry-layer project partition replacement seam，而不是让 HTTP handler 手工拼写整条写路径。

## Endpoint Contract

```text
POST /v1/admin/registry/project-partition/replace
```

endpoint 接受完整 registry document 作为 proposed target view，但只允许变更 authenticated principal 的 project partition 内对象。

partition project 永远来自：

```text
partition_project_id = resolved AdminPrincipal.ProjectID
```

不得来自：

- request body
- query string
- URL path
- public caller headers
- `X-Actor-ID`
- 任何未来 public project selector

现有 full import/replace endpoint 保持独立：

```text
POST /v1/admin/registry/import-replace
```

该 endpoint 继续是 operator/full-registry oriented，不暴露为 hosted project mutation surface。

## Required Principal

Control Plane handler 必须解析出带有下列 permission 的 admin principal：

```text
control_plane.registry.project_partition_replace
```

principal 必须满足：

- `AuthMethod == trusted_gateway`
- `LocalPrivate == false`
- non-empty `SubjectID`
- non-empty `ActorID`
- non-empty `ProjectID`
- permissions 包含 `control_plane.registry.project_partition_replace`

拒绝：

- local/private admin-token principals
- 没有 project scope 的 hosted principals
- 只有 `control_plane.registry.import_replace` 的 hosted principals
- 未通过 trusted gateway authenticator 的 caller-supplied trusted headers

Local/private full import/replace 继续留在现有 operator endpoint 上，不扩展到这个 hosted partition endpoint。

## Required Headers

| Header | Required | Source |
| --- | --- | --- |
| `Authorization: Bearer <gateway-secret>` | yes | trusted gateway to Control Plane |
| `X-API2Agent-Subject-ID` | yes | gateway-issued trusted identity claim |
| `X-API2Agent-Actor-ID` | yes | gateway-issued trusted actor claim |
| `X-API2Agent-Project-ID` | yes | gateway-issued trusted project claim |
| `X-API2Agent-Permissions` | yes | gateway-issued trusted permission claim |
| `X-Request-ID` | yes | gateway-forwarded request correlation |
| `Idempotency-Key` | yes | gateway-forwarded mutation safety key |

Header validation：

- missing or blank `X-Request-ID` 返回 `400 INVALID_REQUEST`
- missing or blank `Idempotency-Key` 返回 `400 INVALID_REQUEST`
- trusted identity failures 返回 `401 AUTH_ERROR`
- missing permission 或 project scope 返回 `403 AUTHZ_DENIED`
- handler 绝不能直接信任 public identity 或 permission headers

## Request Body

沿用 import/replace 的 wrapper pattern，但 mutation mode 更窄：

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
  "source": "hosted_project_partition_replace",
  "dry_run": false
}
```

字段：

| Field | Required | v0 behavior |
| --- | --- | --- |
| `registry` | yes | 完整 proposed registry graph，用于 canonicalize、validate 和 partition-check。 |
| `source` | no | Audit hint。缺省为 `hosted_project_partition_replace`。 |
| `dry_run` | no | Reserved。省略或 `false` 允许；v0 中 `true` 返回 `400 INVALID_REQUEST`。 |

v0 拒绝这些 body fields：

- `project_id`
- `partition_project_id`
- `actor_id`
- `organization_id`
- `permissions`
- 任何 project override 或 identity override field

registry 仍然只能包含 metadata。Plaintext API keys、OAuth tokens、provider secrets、vault material 或 gateway secrets 不得被该 endpoint 接收或持久化。

## Request Size Limit

沿用 private import/replace 的 bounded default：

```text
2 MiB
```

body-size failures 返回：

```text
413 REQUEST_BODY_TOO_LARGE
```

## Registry-Layer Seam

不要让 HTTP handler 分别执行 load current registry、call validator、再 call `ReplacePersistentRegistry`。

下一步实现应新增一个拥有 transaction 的 registry-layer seam：

```go
type ProjectPartitionReplaceOptions struct {
    Principal      registry.AdminPrincipal
    RequestID      string
    IdempotencyKey string
    Source         string
}

type ProjectPartitionReplaceResult struct {
    RegistryStore               string
    RegistryFingerprint          string
    PreviousRegistryFingerprint  string
    SnapshotVersion              string
    Noop                         bool
    Replayed                     bool
    Counts                       registry.RegistryCounts
    PartitionDecision            registry.ProjectPartitionMutationDecision
}

type RegistryProjectPartitionReplacer interface {
    ReplaceProjectPartitionRegistry(
        ctx context.Context,
        proposed registry.Registry,
        opts ProjectPartitionReplaceOptions,
    ) (ProjectPartitionReplaceResult, error)
}
```

registry-layer implementation 应该：

1. 开启 persistent registry replacement 使用的同一个 serializable write transaction
2. 获取现有 registry mutation lock
3. 在该 transaction 内加载 current persistent registry
4. canonicalize 并 validate proposed full registry graph
5. 调用 `ValidateProjectPartitionMutation(current, proposed, principal.ProjectID)`
6. 如果 decision 不允许，在任何写入前拒绝
7. 从 registry 和 partition evidence 计算 idempotency request fingerprint
8. partition decision 通过后才执行 replacement
9. 在同一 transaction 内写 registry revision、admin audit 和 idempotency completion

这样 stale-read 和 time-of-check/time-of-use 边界才是闭合的。

## Idempotency

Operation：

```text
registry.project_partition_replace
```

Scope：

```text
project_id = principal.ProjectID
actor_id = principal.ActorID
operation = registry.project_partition_replace
idempotency_key_hash = hash(Idempotency-Key)
```

request fingerprint 应包含：

- HTTP method and path
- operation
- principal project id
- principal actor id
- proposed registry fingerprint
- previous registry fingerprint when known
- partition diff fingerprint
- source

预期行为：

- same scope、same key、same request 返回 stored committed response，`replayed=true`
- same scope、same key、different request 返回 `409 IDEMPOTENCY_KEY_CONFLICT`
- 不同 projects 可以复用同一个 raw idempotency key，因为 project scope 是 idempotency key 的一部分
- raw idempotency key 不得写入 audit metadata 或 dogfood artifacts

## Response Shape

Changed registry：

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
  "replayed": false,
  "partition_project_id": "project_alpha",
  "partition_diff_fingerprint": "sha256:...",
  "partition_counts": {
    "projects_changed": 0,
    "api_keys_changed": 1,
    "credential_metadata_changed": 1,
    "providers_changed": 0
  },
  "counts": {
    "projects": 2,
    "api_keys": 3,
    "capabilities": 1,
    "providers": 1,
    "credential_metadata": 2,
    "routing_policies": 1,
    "snapshot_configs": 1
  }
}
```

No-op：

```http
200 OK
```

response shape 相同，但 `noop=true`。

Idempotency replay：

```http
200 OK
```

response shape 是 committed result，且 `replayed=true`。

## Error Mapping

使用现有 service error envelope：

```json
{
  "error": {
    "error_type": "REGISTRY_PARTITION_VIOLATION",
    "error_scope": "caller",
    "message": "...",
    "retryable": false
  }
}
```

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| missing/invalid trusted gateway auth | 401 | `AUTH_ERROR` | caller | false |
| missing required permission | 403 | `AUTHZ_DENIED` | caller | false |
| principal missing project scope | 403 | `AUTHZ_DENIED` | caller | false |
| local/private principal used on this endpoint | 403 | `AUTHZ_DENIED` | caller | false |
| wrong method | 405 | `INVALID_REQUEST` | caller | false |
| missing `X-Request-ID` | 400 | `INVALID_REQUEST` | caller | false |
| missing `Idempotency-Key` | 400 | `INVALID_REQUEST` | caller | false |
| invalid JSON body | 400 | `INVALID_REQUEST` | caller | false |
| missing `registry` wrapper field | 400 | `INVALID_REQUEST` | caller | false |
| body contains project or identity override | 400 | `INVALID_REQUEST` | caller | false |
| `dry_run=true` in v0 | 400 | `INVALID_REQUEST` | caller | false |
| request body over limit | 413 | `REQUEST_BODY_TOO_LARGE` | caller | false |
| service not configured for Postgres mutation | 409 | `REGISTRY_MUTATION_UNAVAILABLE` | platform | false |
| invalid registry graph | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| proposed change outside project partition | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| ownership transfer attempted | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| global object changed | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| idempotency key conflict | 409 | `IDEMPOTENCY_KEY_CONFLICT` | caller | false |
| concurrent registry mutation | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

service-level registry mutation error mapper 应显式增加：

```text
REGISTRY_PARTITION_VIOLATION -> 403
```

未知 registry-layer errors 应 fail closed 为 `500 REGISTRY_MUTATION_FAILED`。

## Audit Evidence

Required action：

```text
registry.project_partition_replace
```

Required metadata：

- `registry_store=postgres`
- `mutation_mode=project_partition_replace`
- `project_id`
- `organization_id` when available
- `principal_subject_id`
- `principal_actor_id`
- `auth_method=trusted_gateway`
- `token_id` when available
- `gateway_key_id` when available
- `partition_project_id`
- `registry_fingerprint`
- `previous_registry_fingerprint`
- `partition_diff_fingerprint`
- `projects_changed`
- `api_keys_changed`
- `credential_metadata_changed`
- `providers_changed`
- rejected object counts on failure when safe
- idempotency key hash or prefix only
- `source`

不得包含：

- raw public bearer token
- gateway shared secret
- raw idempotency key
- provider credential secret
- plaintext API key material

Gateway-local auth/authz failures 仍然是 gateway-local，不得创建 Control Plane audit 或 idempotency rows。Partition violations 发生在 trusted forwarding 之后，因此 Control Plane 应在 audit sink 可用时写 failure audit。

## Permission Source Mapping

未来 gateway permission-source implementation 应把可变更自身 project partition 的 hosted principal 映射到：

```text
control_plane.registry.project_partition_replace
```

不能为 hosted project mutation 授予 `control_plane.registry.import_replace`。

implementation slice 中，local dogfood permission source 可以给 project-scoped test principal 增加该 permission，但这份设计不新增 OAuth/OIDC、public role CRUD 或 durable permission store。

## Snapshot Boundary

该 endpoint 只改变 mutable Control Plane registry state。

它不得自动：

- export snapshot artifact
- publish distribution `current.json`
- reload Data Plane instances
- 让 Data Plane 读取 mutable Control Plane tables

propagation sequence 仍然必须显式执行：

```text
project partition replace
  -> snapshot export
  -> distribution publish
  -> Data Plane reload
```

## Tests Required For Implementation

最低 HTTP 和 registry-layer tests：

1. route 注册在 `POST /v1/admin/registry/project-partition/replace`
2. trusted-gateway auth is required
3. local/private principal is rejected
4. `control_plane.registry.project_partition_replace` is required
5. 只有 `control_plane.registry.import_replace` 不足以通过
6. missing project scope 返回 `403 AUTHZ_DENIED`
7. `X-Request-ID` is required
8. `Idempotency-Key` is required
9. invalid JSON 返回 `400 INVALID_REQUEST`
10. missing `registry` 返回 `400 INVALID_REQUEST`
11. project 或 identity override fields 返回 `400 INVALID_REQUEST`
12. `dry_run=true` 返回 `400 INVALID_REQUEST`
13. over-limit body 返回 `413 REQUEST_BODY_TOO_LARGE`
14. unconfigured/file-store mutation 返回 `409 REGISTRY_MUTATION_UNAVAILABLE`
15. invalid registry graph 返回 `400 REGISTRY_MUTATION_INVALID`
16. cross-project mutation 返回 `403 REGISTRY_PARTITION_VIOLATION`
17. global capability/routing/snapshot change 返回 `403 REGISTRY_PARTITION_VIOLATION`
18. valid same-project partition mutation 会调用 registry-layer project partition replacer
19. partition validation 在 replacement transaction 内执行
20. success response 包含 partition project id、diff fingerprint、changed counts 和 registry fingerprints
21. failure audit 包含 partition evidence 但不含 secrets
22. success audit 包含 hosted principal evidence 但不含 raw keys/tokens
23. idempotency replay 返回 stored committed response
24. idempotency conflict 返回 `409 IDEMPOTENCY_KEY_CONFLICT`
25. gateway contract harness 映射 hosted project mutation permission，但不暴露 full import/replace
26. mutation 不 export、publish、reload，且不触达 Data Plane mutable reads

## Non-Goals

不要实现：

- public CRUD registry APIs
- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation/login/session lifecycle
- production gateway deployment
- durable hosted permission store
- provider onboarding workflow
- marketplace/provider submission
- credential vault writes
- plaintext credential storage
- billing or settlement state
- workflow runtime
- automatic snapshot export, publish, or Data Plane reload
- Data Plane reads from mutable Control Plane tables

## Acceptance Criteria

这份设计被接受的条件：

- method/path 已记录
- hosted/trusted principal requirements 明确
- project scope 只来自 resolved principal
- request wrapper 和 rejected override fields 已记录
- registry-layer transaction seam 明确
- idempotency scope 和 request fingerprint 已记录
- response shape 包含 partition evidence
- `REGISTRY_PARTITION_VIOLATION -> 403` 明确
- audit evidence 和 secret redaction rules 已记录
- snapshot propagation 保持 manual
- implementation test requirements 已命名
- public CRUD、OAuth/OIDC、production gateway deployment、vault、billing、marketplace、workflow runtime、provider onboarding、automatic propagation 和 Data Plane mutable-table reads 仍是 out of scope

## Recommended Next Task

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Implementation v0
```

该任务应实现 private hosted admin endpoint、registry-layer project partition replacement seam、permission constant、stable HTTP error mapping、tests 和 local dogfood proof。不要新增 public CRUD 或 automatic propagation。
