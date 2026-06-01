# Go Control Plane Hosted Permission Store Schema Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Hosted Permission Store Schema implementation slice 可以关闭。

仓库现在有了 hosted permission-store lookup 的 durable Postgres schema boundary：

```text
hosted_subjects
  -> hosted_project_memberships
  -> hosted_role_bindings
  -> hosted_roles
  -> hosted_permission_grants
  -> hosted_policy_versions
  -> hosted_permission_decisions
```

推荐下一项任务：

```text
Go Control Plane Hosted Permission Store Read Model v0
```

该任务应在 schema 上增加 internal read model，并证明它可以返回与 local harness 相同的 permission decision shape。不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation，或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Design

已完成：

- durable permission-store entities and relationships
- gateway lookup input/output contract
- 6 条 hosted admin routes 的 endpoint permission mapping
- unavailable、ambiguous、stale、missing、revoked 或 denied policy 的 fail-closed semantics
- consistency 和 cache expectations
- policy source/version/fingerprint/decision evidence requirements
- public CRUD、OAuth/OIDC、production gateway、marketplace、vault、billing、workflow 和 automatic propagation 的 non-goals

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_DESIGN.md`

### Contract Harness

已完成：

- store-shaped local fixture/read model
- public principal 到 subject 的 resolution
- membership、role binding 和 permission grant lookup
- policy source/version/fingerprint/decision evidence
- gateway-local missing membership、suspended membership、revoked permission、unavailable store 和 stale policy denial
- Control Plane second-gate denial proof

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`

### Schema

已在 `services/control-plane/schema/postgres/001_persistent_registry_store.sql` 中完成：

- `hosted_subjects`
- `hosted_project_memberships`
- `hosted_roles`
- `hosted_role_bindings`
- `hosted_permission_grants`
- `hosted_policy_versions`
- `hosted_permission_decisions`

新增 constraints 和 indexes：

- non-empty external subject references unique
- 每个 subject/project 一条 membership
- membership project/status lookup
- active role binding uniqueness
- role binding project/status lookup
- active permission grant uniqueness
- permission/status grant lookup
- policy source/version uniqueness
- 每个 policy source 一个 active policy version
- 按 subject/project/resolved time 查询 decision
- 按 policy version 查询 decision
- `sha256:` policy fingerprint format

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| durable schema/read boundary 明确 | passed |
| schema 表达 hosted subjects | passed |
| schema 表达 project memberships 以及 active/suspended/revoked state | passed |
| schema 表达 hosted roles | passed |
| schema 表达 role bindings | passed |
| schema 表达 permission grants | passed |
| schema 表达 policy versions 和 active version uniqueness | passed |
| schema 表达 permission decision evidence | passed |
| schema 可以保留 policy source/version/fingerprint/decision id | passed |
| schema 支持 membership、revocation、stale policy 和 endpoint permission denial 的 fail-closed lookup semantics | passed |
| raw public tokens、raw session tokens、OAuth tokens、gateway secrets、plaintext API keys 和 vault material 保持不进 schema | passed |
| runtime read wiring 保持 deferred | passed |
| 未新增 public CRUD、OAuth/OIDC、production gateway、marketplace、vault、billing、workflow 或 automatic propagation scope | passed |

## Dogfood 证据

Live dogfood artifact：

```text
.dogfood/go-control-plane-hosted-permission-store-schema/report.json
```

观察结果：

- `status=passed`
- schema apply 在新增 hosted permission tables 后成功
- service health 返回 `status=ok`
- gateway health 返回 `status=ok`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `import_status=201`
- audit counts 为 `registry_revisions=3`、`admin_audit_events=5`、`idempotency_records=2`
- audit/idempotency rows 不包含 gateway secrets、raw public tokens 或 spoofed public identity

## Validation

已通过：

```text
go test ./internal/registry -run "TestPersistentRegistrySQLSchemaContainsHostedPermissionStoreBoundary|TestHostedPermissionStoreSchemaDoesNotPersistRawSecrets|TestPersistentRegistrySQLSchemaContainsRequiredTablesAndConstraints"
go test ./...
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-store-schema/report.json
git diff --check
```

Go test 目录：

```text
services/control-plane
```

## Closeout Judgment

这个 implementation slice 已完成。

schema 满足 hosted permission-store v0 boundary。它可以表达 contract harness 的 read path 和 evidence shape，同时不存储 raw public tokens、gateway secrets、plaintext API keys、OAuth tokens、session tokens 或 vault material。

schema 仍然刻意没有接入 runtime gateway lookup。这种分离正是本片的意义：让下一项 read-model task 有 durable boundary 可以对齐，同时把 public management surfaces 和 production gateway behavior 留在范围之外。

## Remaining Risks

### No Runtime Read Model Yet

schema 已存在，但还没有 Go read model 从中解析 hosted permission decisions。

### No Seed Or Migration Lifecycle Beyond The Draft Schema

当前项目仍使用单一 schema draft 做 local dogfood。Migration ordering、rollbacks 和 production deployment lifecycle 仍是未来工作。

### No Policy Write Path

仍没有 public 或 internal policy mutation API。Role/user/project management 继续保持 out of scope。

### No Real Public Identity Lifecycle

OAuth/OIDC、login、session、invitation 和 external subject lifecycle 仍是未来工作。

### No Production Gateway Deployment

gateway 仍是 local dogfood tooling。Production routing、TLS、private network enforcement、observability、rate limits 和 rollout 仍是未来工作。

### Cache/Consistency Still Needs Runtime Proof

schema 有 policy version 和 fingerprint fields，但 runtime transaction/read consistency 还没有实现。

### Provider Ownership Still Needs Hardening

Project-scoped registry mutation 已受约束，但 provider ownership 在 v0 仍基于 metadata。

## Still Not Allowed

不要开始：

- OAuth/OIDC provider integration
- public user/project/role CRUD
- invitation/login/session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Hosted Permission Store Read Model v0
```

原因：

- lookup contract 已完成设计
- local harness 已证明 behavior
- durable schema 已存在
- 下一项风险是 Go code 能否从 schema 解析同样的 decision shape，同时保留 fail-closed semantics 和 secret-safe evidence

预期范围：

- 在 hosted permission tables 上新增 internal Go read model
- 解析 subject、membership、role binding、grants、active policy version 和 decision evidence
- 返回与 gateway contract 兼容的 local decision shape
- 证明 missing membership、suspended membership、revoked grants、stale/no active policy 和 missing permission fail closed
- v0 保持 private/internal，并以 test-only 或 seeded 方式验证

Out of scope：

- public CRUD
- OAuth/OIDC
- invitation/session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- vault writes
- billing
- workflow runtime
- automatic publish/reload
- Data Plane mutable Control Plane table reads
