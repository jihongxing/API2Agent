# Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

已实现 private hosted admin endpoint，用于 project-scoped registry replacement：

```text
POST /v1/admin/registry/project-partition/replace
```

endpoint 要求 trusted-gateway、non-local、project-scoped principal，并具备：

```text
control_plane.registry.project_partition_replace
```

它不暴露 public CRUD，也不会自动 export、publish、reload，或让 Data Plane 读取 mutable Control Plane tables。

## 变更内容

- 新增 `PermissionRegistryProjectPartitionReplace`。
- HTTP service 新增 `RegistryProjectPartitionReplacer`。
- 注册 `POST /v1/admin/registry/project-partition/replace`。
- request handling 覆盖：
  - `X-Request-ID` required
  - `Idempotency-Key` required
  - 2 MiB body cap
  - wrapper body parsing
  - `dry_run=true` rejection
  - 通过 strict JSON decoding 拒绝 unknown identity/project override fields
- 新增 trusted hosted principal guard：
  - 拒绝 local/private principals
  - 要求 `trusted_gateway`
  - 要求 project 和 actor scope
  - 要求 `control_plane.registry.project_partition_replace`
- response 返回 evidence：
  - `partition_project_id`
  - `partition_diff_fingerprint`
  - `partition_counts`
  - registry fingerprints 和 object counts
  - replay flag
- `REGISTRY_PARTITION_VIOLATION` 映射到 `403`。
- `serve` runtime 在 Postgres mutation mode 下注入 project partition replacer。
- local hosted gateway contract harness endpoint permission map 加入新 endpoint。

## Registry-Layer Transaction Seam

新增：

```go
registry.ReplaceProjectPartitionRegistry(ctx, db, proposed, opts)
```

registry layer 拥有 serializable write transaction：

1. validate/canonicalize proposed registry
2. begin serializable write transaction
3. acquire registry mutation lock
4. 在 transaction 内加载 current persistent registry
5. 调用 `ValidateProjectPartitionMutation(current, proposed, principal.ProjectID)`
6. partition validation 之后再 reserve idempotency
7. validation 通过后才 replace mutable rows
8. 在同一 transaction 内写 registry revision、admin audit 和 idempotency completion

partition violations 会在 mutable row replacement 前返回。

## Idempotency

新 endpoint 使用：

```text
operation = registry.project_partition_replace
project_id = principal.ProjectID
actor_id = principal.ActorID
```

idempotency request summary 存储 partition evidence，包括 diff fingerprint。冲突判断 fingerprint 使用稳定 caller request fields 和 proposed registry fingerprint，因此 replay 不会仅因为 current registry 已变成第一次请求的 committed target 而冲突。

cached idempotency responses 包含完整 partition result，包括 `partition_decision`。

## Audit Evidence

success/failure audit action：

```text
registry.project_partition_replace
```

audit metadata 包含：

- hosted principal evidence
- `partition_project_id`
- `partition_diff_fingerprint`
- changed counts
- rejected counts when safe
- registry fingerprints
- idempotency key hash/prefix only

该路径不会写 raw public tokens、gateway secrets、raw idempotency keys 或 credential secrets。

## Tests

新增和更新覆盖：

- registry-layer project partition replacement success
- mutable row replacement 前在同一 transaction 内执行 partition validation
- partition violation 返回 `REGISTRY_PARTITION_VIOLATION`
- partition violation 不 replace mutable rows
- project-scoped idempotency operation 和 cached partition response
- idempotency replay 返回 cached partition evidence
- HTTP endpoint registration
- local/private principal rejection
- broad import/replace permission 不足以通过
- required request/idempotency headers
- invalid JSON/body wrapper
- identity override rejection
- partition evidence response shape
- replay headers 和 `200 OK`
- `REGISTRY_PARTITION_VIOLATION -> 403`
- gateway permission map 包含新 endpoint

## Validation

已通过：

```text
go test ./...
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
```

Go test directory：

```text
services/control-plane
```

## Non-Goals Preserved

未新增：

- public CRUD
- OAuth/OIDC
- public user/project/role CRUD
- invitation/login/session lifecycle
- production gateway deployment
- durable hosted permission store
- provider onboarding
- marketplace
- vault writes
- billing
- workflow runtime
- automatic snapshot export/publish/reload
- Data Plane reads from mutable Control Plane tables

## Recommended Next Task

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Live Dogfood + Closeout v0
```

该任务应通过 local hosted gateway harness，对 real service process 和 live Postgres 跑 endpoint，然后在 evidence 确认 trusted-only access、partition rejection、audit/idempotency evidence 和 no automatic propagation 后关闭该 slice。
