# Go Control Plane Tenant-Partitioned Registry Mutation Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 hosted Control Plane mutation primitive 应是 tenant-partitioned registry mutation boundary，而不是 public CRUD，也不是另一个 full-registry replacement endpoint。

推荐下一项 implementation task：

```text
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness v0
```

该 implementation 应增加 local contract tests 或 dogfood-only helpers，先证明 partition validation rules，再改变 production mutation behavior。

## 为什么现在做

Hosted admin identity、trusted gateway authentication、gateway header stripping、gateway-issued permissions 和 idempotency scope 已经在本地证明。

剩余 hosted risk 是 mutation scope：

```text
trusted project-scoped principal
  -> currently can call registry.import_replace
  -> full mutable registry graph can be replaced
```

这对 local/private administration 可以接受。对 hosted administration 来说太宽。Project-scoped actor 不应该能删除或改写另一个 project、另一个 project 的 credential metadata、platform routing policy、platform snapshot config，或 shared capability definitions。

## Current Baseline

当前 mutable registry graph 包含：

- `projects`
- `api_keys`
- `capabilities`
- `providers`
- `credential_metadata`
- `routing_policies`
- `snapshot_configs`

当前 import/replace implementation：

- validates the full registry graph
- deletes all mutable registry rows
- inserts the replacement graph
- writes `registry_revisions`
- writes `admin_audit_events`
- completes idempotency records scoped by `project_id + actor_id + operation + idempotency_key_hash`

现有 project-owned 或 project-related 字段：

- `api_keys.project_id`
- `credential_metadata.owner_type=project`
- `credential_metadata.owner_id=<project_id>`
- admin principal `ProjectID`
- admin audit metadata `project_id`
- idempotency `project_id`

v0 中仍然实际属于 platform/global 的对象：

- `capabilities`
- 没有显式 owner metadata 的 provider candidate definitions
- active global `routing_policy`
- active `snapshot_config`

## Goals

- 定义 hosted project identity 如何约束 registry mutation scope
- 定义安全的 project partition envelope
- 阻止 cross-project deletion、overwrite 或 ownership transfer
- 保护 global/platform registry objects，不允许 project-scoped mutation 修改
- 保持 full-registry validation before commit
- 保持 registry revision、audit 和 idempotency evidence
- 保持 snapshot export/publish/reload separation
- 为后续 implementation slice 定义 stable failure semantics 和 tests

## Non-Goals

不实现：

- public CRUD APIs
- public project/user/role CRUD
- OAuth/OIDC provider integration
- invitation/login/session lifecycle
- production gateway deployment
- durable hosted permission store
- provider onboarding workflow
- marketplace/provider submission
- credential vault writes
- plaintext credential storage
- billing or settlement state
- workflow runtime
- automatic snapshot export、publish 或 Data Plane reload
- Data Plane reads from mutable Control Plane tables

## Boundary Model

引入一个概念 mutation mode：

```text
project_partition_replace
```

该 mode 接收一个完整 registry document 作为 proposed target view，但只允许 authenticated principal 的 project partition 内部发生变化。

Project partition 来自：

```text
partition_project_id = resolved AdminPrincipal.ProjectID
```

它不能来自：

- request body
- public headers
- `X-Actor-ID`
- public caller 提供的 URL path parameters
- query parameters

对 local/private mode，`project_partition_replace` 应保持 disabled，除非 tests 显式注入 hosted-style principal。Local/private full import/replace 仍可用于 operator administration。

## Project Partition Definition

### Owned By The Project

当 owner 精确等于 resolved `ProjectID` 时，这些 rows 可以被 project-scoped hosted mutation 修改：

| Object | Project ownership rule |
| --- | --- |
| `projects` | 仅 `id == principal.ProjectID` 的 row；status/name/default-mode policy 必须显式定义 |
| `api_keys` | 仅 `project_id == principal.ProjectID` 的 rows |
| `credential_metadata` | 仅 `owner_type == "project"` 且 `owner_id == principal.ProjectID` 的 rows |
| project-owned providers | 仅带有显式未来 `owner_project_id == principal.ProjectID` 或等价 metadata 的 rows |

### Read-Only For Project-Scoped Mutation

v0 中这些 rows 不得被 `project_partition_replace` create、delete 或 change：

| Object | Rule |
| --- | --- |
| `capabilities` | v0 中只属于 platform/global |
| 无显式 project owner 的 providers | v0 中只属于 platform/global |
| 另一个 project owned providers | reject |
| user/platform/provider owners 的 `credential_metadata` | reject |
| `scope_type=global` 的 `routing_policies` | reject |
| 另一个 project 的 `routing_policies` | reject |
| active `snapshot_configs` | platform/global only |

Project-scoped routing policy 可在未来设计，但 v0 不应 mutation routing policy rows，除非 resolver/export semantics 已经知道如何应用它们且不改变 snapshot contract。

## Provider Ownership

Provider candidates 当前没有 first-class project ownership。因此 v0 不允许 project-scoped mutation 修改 provider rows，除非先显式表示 ownership。

推荐未来 schema field：

```text
providers.owner_type in ('platform', 'project')
providers.owner_id
```

Contract harness 可使用的最小 v0-compatible alternative：

```text
provider.metadata.owner_project_id
```

规则：

- missing owner metadata 表示 platform-owned。
- platform-owned providers 对 project-scoped mutation 只读。
- `owner_project_id` 必须等于 `principal.ProjectID` 才能 project mutation。
- project-scoped mutation 不允许改变 provider ownership。
- existing project-owned provider 的 `capability_id` 或 `capability_version` 不允许被改变，除非目标 capability 已存在且仍然 platform-approved。
- provider metadata 仍不得包含 secrets。

## Mutation Algorithm

围绕现有 full-registry validation 设计 validator：

```text
current persistent registry
  + proposed registry
  + principal project id
  -> partition diff
  -> allow/reject decision
```

步骤：

1. Resolve admin principal and required permission。
2. Require hosted/trusted project scope。
3. Parse proposed registry wrapper。
4. Canonicalize and validate proposed full registry。
5. 在同一个 serializable write transaction 中 load current persistent registry。
6. 按 stable object keys 计算 logical diff。
7. Reject caller project partition 之外的任何 create/update/delete。
8. Reject ownership transfers。
9. Reject global routing policy 或 snapshot config changes。
10. Reject capability changes in v0。
11. partition diff 通过后，才用 existing registry-wide mutation lock 执行 replacement。
12. 在同一 transaction 写 registry revision、admin audit 和 idempotency completion。

这保持 database write primitive 简单，同时增加 pre-commit safety gate。

## Permission Model

不要复用 broad full-registry replacement permission 作为 hosted project-scoped mutation 权限。

推荐 permissions：

| Operation | Permission |
| --- | --- |
| full local/private import/replace | `control_plane.registry.import_replace` |
| hosted project partition replace | `control_plane.registry.project_partition_replace` |
| partition validation only | `control_plane.registry.project_partition_validate` |

Gateway permission source 后续可把 dogfood principals 映射到这些权限，但本设计不修改 permission source。

## Endpoint Shape For Later Implementation

优先使用独立 private admin endpoint，避免静默改变 full import/replace semantics：

```text
POST /v1/admin/registry/project-partition/replace
```

Required：

- hosted/trusted gateway principal
- `X-Request-ID`
- `Idempotency-Key`
- 带 `registry` 的 request wrapper

v0 中拒绝：

- local/private principal，除非 contract tests 显式启用
- request body project override
- bypass validation semantics 的 dry-run execution

现有 endpoint 保持：

```text
POST /v1/admin/registry/import-replace
```

它继续面向 operator/full-registry，不应作为 public hosted project mutation surface 暴露。

## Idempotency Scope

使用 resolved principal：

```text
project_id = principal.ProjectID
actor_id = principal.ActorID
operation = registry.project_partition_replace
idempotency_key_hash = hash(Idempotency-Key)
```

Request fingerprint 应包含：

- operation
- method/path
- partition project id
- proposed registry fingerprint
- partition diff fingerprint
- source

Same key and same request replay committed response。

Same key and different request 返回：

```text
409 IDEMPOTENCY_KEY_CONFLICT
```

不同 projects 可以独立复用同一个 raw idempotency key，因为 `project_id` 是 scope 的一部分。

## Audit Evidence

Required action：

```text
registry.project_partition_replace
```

Required audit metadata：

- `project_id`
- `organization_id` when available
- `principal_subject_id`
- `auth_method`
- `token_id` when available
- `gateway_key_id` when available
- `partition_project_id`
- `mutation_mode=project_partition_replace`
- `registry_fingerprint`
- `previous_registry_fingerprint`
- `partition_diff_fingerprint`
- affected object counts by class：
  - `projects_changed`
  - `api_keys_changed`
  - `credential_metadata_changed`
  - `providers_changed`
- failure 时 safe 的 rejected object counts by class
- 只记录 idempotency key hash/prefix，不记录 raw key

Audit metadata 不得包含：

- raw public bearer token
- trusted gateway secret
- provider credential secret
- plaintext API key material

## Snapshot Boundary

Partitioned mutation 仍然只改变 Control Plane mutable state。

它不得自动：

- export a snapshot artifact
- publish distribution `current.json`
- reload Data Plane instances
- 让 Data Plane 读取 mutable Control Plane tables

后续仍是显式流程：

```text
project_partition_replace
  -> snapshot export
  -> distribution publish
  -> Data Plane reload
```

Snapshot export 继续生成 full immutable routing snapshot。Project partitioning 约束的是 mutation authority；它不会让 Data Plane 消费 partial mutable views。

## Failure Semantics

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| missing/invalid hosted identity | 401 | `AUTH_ERROR` | caller | false |
| missing required permission | 403 | `AUTHZ_DENIED` | caller | false |
| principal missing project scope | 403 | `AUTHZ_DENIED` | caller | false |
| local/private principal used on hosted partition endpoint | 403 | `AUTHZ_DENIED` | caller | false |
| invalid JSON/body wrapper | 400 | `INVALID_REQUEST` | caller | false |
| invalid full registry graph | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| proposed change outside partition | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| ownership transfer attempted | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| global object changed | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| idempotency key conflict | 409 | `IDEMPOTENCY_KEY_CONFLICT` | caller | false |
| concurrent mutation lock conflict | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

Gateway-local auth/authz denials 保持 gateway-local，不应创建 Control Plane audit/idempotency rows。

Control Plane partition violations 发生在 trusted forwarding 之后；audit sink 可用时应创建 failure audit。

## Validation Rules

Partition validator 应 reject：

- 删除 `principal.ProjectID` 之外的任何 project row
- 修改另一个 project row
- 删除另一个 project 的 API key metadata
- 为另一个 project 增加 API key metadata
- 修改另一个 project owned `credential_metadata`
- 修改 `owner_type != project` 的 `credential_metadata`
- 修改 platform-owned providers
- 修改另一个 project owned providers
- 修改 provider ownership metadata
- 增加没有 explicit project ownership 的 provider rows
- 修改 capabilities
- 修改 active global routing policy
- 修改 active snapshot config
- 任何导致 existing `Registry.Validate()` 失败的 registry graph change

Validator 可以允许：

- 更新 caller 自己 project row 上允许的 fields
- 增删改 caller-project API key metadata，仍不能包含 plaintext key material
- 增删改 caller-project credential metadata，仍是 metadata-only
- 在 provider ownership 已表示后，增删改显式 caller-owned provider rows

## Contract Harness Plan

下一项 implementation 应先证明规则，再改变 production endpoints。

建议 harness/tests：

1. Same-project API key metadata change passes。
2. Same-project credential metadata change passes。
3. Another project's API key deletion fails with `REGISTRY_PARTITION_VIOLATION`。
4. Another project's credential metadata change fails with `REGISTRY_PARTITION_VIOLATION`。
5. Global routing policy change fails with `REGISTRY_PARTITION_VIOLATION`。
6. Active snapshot config change fails with `REGISTRY_PARTITION_VIOLATION`。
7. Capability change fails with `REGISTRY_PARTITION_VIOLATION`。
8. Platform-owned provider change fails with `REGISTRY_PARTITION_VIOLATION`。
9. Project-owned provider change 只有 owner metadata 匹配 principal project 时通过。
10. Provider ownership transfer fails。
11. Same idempotency key can be reused by different project scopes。
12. Same idempotency key with different request in one project fails。
13. Failure audit includes partition evidence but no secrets。
14. Successful mutation does not export、publish、reload，或 touch Data Plane mutable reads。

## Acceptance Criteria

本设计被接受的条件：

- project partition ownership rules 明确
- global/platform read-only objects 明确
- provider ownership gap 和 migration options 明确
- mutation algorithm 明确
- 后续 implementation 的 endpoint 和 permission shape 明确
- idempotency 和 audit evidence 明确
- snapshot boundary 保持明确
- failure semantics 明确
- tests/dogfood expectations 已命名
- public CRUD、OAuth/OIDC、production gateway deployment、vault、billing、marketplace、workflow runtime、provider onboarding、automatic propagation 和 Data Plane mutable-table reads 保持 out of scope

## 推荐下一项任务

```text
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness v0
```

该任务只应实现 local validation helpers、tests 或 dogfood harness coverage 来证明 partition rules。不要暴露 public CRUD surface，也不要部署 production gateway。
