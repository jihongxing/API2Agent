# Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Tenant-Partitioned Registry Mutation Contract Harness slice 可以关闭。

仓库现在有一个 registry-layer local contract proof，用于 hosted project partition mutation：

```text
current registry
  + proposed full registry
  + resolved project scope
  -> partition diff validation
  -> allow same-project metadata/provider changes
  -> reject cross-project and platform/global changes
  -> stable partition decision evidence
```

推荐下一项任务：

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Design v0
```

该任务应设计 private hosted admin endpoint 如何在 registry replacement 前使用 partition validator，但不要实现 endpoint。不得新增 public CRUD、public project/user/role CRUD、provider onboarding、marketplace、vault、billing、workflow runtime、automatic propagation、production gateway deployment 或 Data Plane mutable-table reads。

## 现在已完成

### Design

已完成：

- tenant/project ownership boundary
- global/platform read-only object rules
- v0 harness 的 provider ownership metadata fallback
- partition diff validation algorithm
- 未来 project partition mutation 的独立 permission 和 endpoint shape
- idempotency 和 audit evidence contract
- snapshot boundary preservation
- contract harness test plan

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_DESIGN.md`

### Implementation

已完成：

- `ValidateProjectPartitionMutation(current, proposed, projectID)`
- `ProjectPartitionMutationDecision`
- `ProjectPartitionMutationViolation`
- `ProjectPartitionMutationCounts`
- `registry.project_partition_replace` operation constant
- stable `REGISTRY_PARTITION_VIOLATION` errors
- missing project scope fail-closed 为 `AUTHZ_DENIED`
- partition decisions 前执行 full-registry validation
- `metadata.owner_project_id` 缺失时，provider 默认视为 platform-owned
- 只有 owner metadata 匹配 principal project 时，才允许 project-owned provider mutation
- provider ownership transfer rejection
- global capability、routing policy 和 snapshot config rejection
- tests 覆盖 project-isolated idempotency fingerprint

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| partition validation helper exists | passed |
| same-project project/API-key/credential metadata cases pass | passed |
| caller-owned provider metadata changes pass | passed |
| cross-project project/API-key/credential changes fail | passed |
| platform credential changes fail | passed |
| global routing policy changes fail | passed |
| active snapshot config changes fail | passed |
| capability changes fail | passed |
| platform-owned provider changes fail | passed |
| provider ownership transfer fails | passed |
| new provider without ownership fails | passed |
| invalid proposed registry fails before partition mutation | passed |
| missing project scope fails closed | passed |
| project-scoped idempotency fingerprint evidence is covered | passed |
| 未新增 HTTP endpoint、public CRUD、production gateway deployment、automatic propagation 或 Data Plane mutable reads | passed |

## Validation

已通过：

```text
go test ./internal/registry
go test ./...
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
git diff --check
```

Go test 目录：

```text
services/control-plane
```

## Closeout Judgment

这个 contract harness slice 已完成。

Local helper 足以作为 v0，因为它在增加 service surface 前证明了 hosted mutation 的核心问题：

- project-scoped actors 只能修改自己的 project partition
- global/platform objects 继续受保护
- provider ownership 保持显式且保守
- partition violations 是 machine-readable
- idempotency evidence 包含 project scope
- snapshot export、distribution publish 和 Data Plane reload 保持分离

该实现刻意不持久化 project-partition mutation、不暴露 HTTP route、不写 audit rows。这些是下一项 design concern，不是 contract harness slice 的缺口。

## Remaining Risks

### No Endpoint Uses The Validator Yet

Helper 还没有接入 HTTP handler。下一项设计必须定义 request/response shape、required headers、principal requirements、error mapping，以及 helper 如何与 `ReplacePersistentRegistry` 组合。

### Audit Persistence Is Not Implemented

Decision object 有 evidence shape，但尚未写入 `registry.project_partition_replace` audit row。

### Provider Ownership Is Metadata-Based

Harness 使用 `provider.metadata.owner_project_id` 作为 v0-compatible proof。Production schema 最终应使用 first-class owner fields。

### Project Row Policy Is Still Narrow

Helper 允许 caller project row changes，但 service design 仍需定义 hosted mode 中哪些 fields 可改。

### Durable Permission Store Is Still Future Work

Gateway permission source 仍是 static dogfood policy。真实 hosted authorization 仍需在 mutation scope 安全后设计 durable policy。

### No Automatic Propagation Was Added

Partitioned mutation 之后仍必须显式执行 snapshot export、distribution publish 和 Data Plane reload。

## Still Not Allowed

不要开始：

- public registry CRUD APIs
- public project/user/role CRUD
- OAuth/OIDC provider integration
- invitation/login/session lifecycle
- provider onboarding workflow
- marketplace/provider submission
- credential vault writes
- plaintext credential storage
- billing or settlement state
- workflow runtime
- production gateway deployment
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Design v0
```

原因：

- partition rules 已在本地证明
- hosted project mutation 需要先有 private endpoint contract，再进入 implementation
- 设计应决定 validator 如何与 auth、idempotency、audit 和 existing replacement mechanics 组合
- 这能在不引入 public CRUD 和 automatic propagation 的前提下，从 helper proof 推进到真实 hosted admin path

预期 design scope：

- endpoint method/path 和 wrapper shape
- required hosted/trusted principal behavior
- required permission name
- request size 和 validation ordering
- partition validator invocation point
- registry replacement transaction composition
- idempotency operation 和 replay semantics
- success/failure partition decisions 的 audit mapping
- `REGISTRY_PARTITION_VIOLATION` error mapping
- 后续 implementation slice 的 tests 和 dogfood requirements

Out of scope：

- endpoint implementation
- public CRUD
- OAuth/OIDC
- provider onboarding
- marketplace
- vault
- billing
- workflow runtime
- automatic publish/reload
- production gateway deployment
- Data Plane mutable Control Plane table reads
