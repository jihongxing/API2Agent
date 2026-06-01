# Go Control Plane Hosted Permission Store Contract Harness Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Hosted Permission Store Contract Harness implementation slice 可以关闭。

仓库现在已经在 local gateway harness 中证明 hosted permission-store lookup boundary：

```text
public authenticated principal
  -> hosted permission-store-shaped read model
  -> hosted subject
  -> project membership
  -> role bindings
  -> permission grants
  -> policy version/fingerprint/decision evidence
  -> gateway-issued trusted X-API2Agent-* claims
  -> Control Plane endpoint permission check
  -> Postgres audit/idempotency evidence
```

推荐下一项任务：

```text
Go Control Plane Hosted Permission Store Schema v0
```

该任务应引入 hosted permission store 的 durable schema/read boundary，但不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation 或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Design

已完成：

- durable hosted permission-store boundary
- subjects、project memberships、roles、role bindings、permission grants、policy versions 和 optional decisions 的 store model
- gateway lookup input/output contract
- 6 条 hosted admin routes 的 endpoint permission mapping
- unavailable、ambiguous、stale 或 denied policy 的 fail-closed semantics
- consistency 和 cache expectations
- secret-safe audit/report evidence requirements
- contract harness plan 和 non-goals

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_DESIGN.md`

### Contract Harness

已完成：

- hosted admin gateway harness 中的 store-shaped local fixture/read model
- public principal 到 hosted subject 的 resolution
- active project membership enforcement
- role binding 和 permission grant resolution
- policy source、version、fingerprint、required permission 和 decision id evidence
- 只作为 metadata forward 的 safe policy evidence headers
- 对 missing membership、suspended membership、revoked permission、unavailable store 和 stale policy 的 gateway-local fail-closed denial
- endpoint mapping 覆盖：
  - `POST /v1/admin/registry/validate`
  - `POST /v1/admin/registry/import-replace`
  - `POST /v1/admin/registry/project-partition/replace`
  - `POST /v1/admin/snapshots/export-artifact`
  - `GET /v1/admin/distribution/current`
  - `POST /v1/admin/distribution/publish`
- insufficient trusted permissions 的 Control Plane second-gate proof
- regression tests 覆盖 store lookup、failure typing、trusted header injection、policy evidence headers 和 endpoint permission mapping

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| gateway lookup contract 通过 local harness tests 证明 | passed |
| store-shaped subject、membership、role binding 和 grant lookup 明确 | passed |
| unavailable store 在 forwarding 前 fail closed | passed |
| missing membership 在 forwarding 前 fail closed | passed |
| suspended membership 在 forwarding 前 fail closed | passed |
| revoked permission 在 forwarding 前 fail closed | passed |
| stale policy view 在 forwarding 前 fail closed | passed |
| endpoint permission absence 在 forwarding 前 fail closed | passed |
| policy source/version/fingerprint/decision id evidence 存在 | passed |
| policy evidence 保持 secret-safe | passed |
| Control Plane second-gate denial 仍被覆盖 | passed |
| hosted project mutation 使用 `control_plane.registry.project_partition_replace` | passed |
| hosted project mutation 不要求 broad import/replace | passed |
| 未新增 public CRUD、OAuth/OIDC、production gateway、marketplace、vault、billing、workflow 或 automatic propagation scope | passed |

## Dogfood 证据

Live dogfood artifact：

```text
.dogfood/go-control-plane-hosted-permission-store-contract-harness/report.json
```

观察结果：

- `status=passed`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `permission_source=hosted-permission-store-fixture`
- `policy_version=hosted-policy-v1`
- `policy_fingerprint=sha256:hosted-permission-store-fixture-v1`
- permission decisions 包含 `decision_id` 和 `required_permission`
- endpoint permission map 覆盖全部 6 条 hosted admin routes
- gateway-local denials 未创建 Control Plane audit/idempotency rows
- insufficient trusted permissions 的 Control Plane second gate 返回 `403 AUTHZ_DENIED`
- partition mutation 成功，`partition_status=201`
- partition replay 返回 `partition_replay_status=200`
- partition violation 返回 `partition_violation_status=403`
- audit counts 为 `registry_revisions=3`、`admin_audit_events=5`、`idempotency_records=2`
- raw public tokens、gateway secrets、spoofed identities、session tokens 和 vault material 未出现在 evidence 中

## Validation

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-store-contract-harness/report.json
git diff --check
```

Go test 目录：

```text
services/control-plane
```

## Closeout Judgment

这个 implementation slice 已完成。

Contract harness 满足 hosted permission store v0 design，是一个 local proof。它证明了预期 read path、policy evidence、gateway-local fail-closed behavior 和 Control Plane second gate，同时没有新增 durable storage 或 public management surfaces。

该 harness 不是 production authorization。它足以作为 v0，因为它证明了 durable schema/read implementation 必须保留的 shape 和 safety properties。

## Remaining Risks

### No Durable Schema Yet

permission store 仍是 local fixture。下一项任务应在任何 production behavior 依赖它之前，引入 durable schema 和 read-model boundaries。

### No Policy Write Path

目前没有 mutation API、role CRUD、invitation flow 或 user-management lifecycle。在 durable read path 和 hosted product boundaries 更安全之前，这保持 intentional。

### No Real Public Identity Lifecycle

OAuth/OIDC、login、session、invitation 和 external subject lifecycle 仍是未来工作。

### No Production Gateway Deployment

gateway 仍是 local dogfood tooling。Production routing、TLS、private network enforcement、observability、rate limits 和 rollout 是未来工作。

### Cache/Consistency Is Still Contractual

harness 证明了 stale policy 的 fail-closed behavior，但还没有 durable transaction 或 policy version table。

### Provider Ownership Still Needs Hardening

Project-scoped mutation 已受约束，但 provider ownership 在 v0 仍基于 metadata。

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
Go Control Plane Hosted Permission Store Schema v0
```

原因：

- durable permission-store boundary 已完成设计
- local contract harness 已证明 lookup semantics 和 failure behavior
- 剩余 gap 是 durable schema/read model，用来保留 policy version、fingerprint、membership state、role bindings 和 permission grants
- schema work 可以保持 private/internal，避免 public CRUD、OAuth/OIDC 和 production gateway scope

预期范围：

- 定义并加入 hosted permission store tables/migrations 或等价 schema artifacts
- 保持 read-only/seeded implementation boundary
- 支持 subject、membership、role、role binding、permission grant、policy version 和 decision evidence
- 保持 gateway-local fail-closed behavior
- 增加 schema/read tests 和 secret-safe evidence checks

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
