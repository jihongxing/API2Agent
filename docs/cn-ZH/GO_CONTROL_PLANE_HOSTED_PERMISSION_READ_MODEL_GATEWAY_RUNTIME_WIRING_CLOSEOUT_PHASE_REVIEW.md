# Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Closeout + Phase Review v0

日期：2026-06-02

状态：complete

## 决策

Hosted Permission Read Model Gateway Runtime Wiring slice 可以关闭。

仓库现在已经证明：local hosted admin gateway 可以在真实 local Postgres database 上把 internal hosted permission read model 作为 runtime permission source，同时保留 static fixture fallback、gateway-local fail-closed behavior、trusted-header safety、Control Plane second-gate authorization、zero decision persistence 和 secret-safe evidence。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Decision Persistence Design v0
```

该任务应先设计 append-only hosted permission decision persistence。它必须先保持为 design task，不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation，或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Runtime Wiring

已完成：

- 用于 gateway permission-source calls 的 local Go lookup helper
- local gateway harness 中的 hosted read-model permission-source mode
- 用于 focused tests 的 static fixture permission-source fallback
- read-model lookup 前本地消费 public bearer token
- 把非 secret public-principal evidence 映射为 external subject refs
- 把 read-model decisions 转换为 gateway-issued trusted headers
- stripping caller-supplied public/trusted identity headers
- Control Plane endpoint permission checks 仍作为 second gate
- 本 slice 不持久化 hosted decisions

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_READ_MODEL_GATEWAY_RUNTIME_WIRING_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

已完成：

- local Postgres 16 container startup
- 从 `services/control-plane/schema/postgres/001_persistent_registry_store.sql` apply schema
- 通过 `seed-postgres` seed registry
- 在 gateway dogfood database 中 seed hosted permission rows
- trusted-gateway mode 下的 private Control Plane
- hosted read-model permission-source mode 下的 local gateway harness
- 通过 HTTP 覆盖 success、denial、stale/no-policy、ambiguous-policy、spoofing 和 Control Plane second-gate cases
- redacted JSON artifact output

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-read-model-gateway-runtime-wiring/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| gateway runtime 有 hosted read-model permission-source mode | passed |
| static fixture mode 仍可用于 focused local tests | passed |
| real Postgres dogfood 证明 read-model-backed gateway decisions | passed |
| missing/invalid public auth 仍是 gateway-local `401` | passed |
| missing membership 以 gateway-local `403 PUBLIC_AUTHZ_DENIED` fail closed | passed |
| suspended membership 以 gateway-local `403 PUBLIC_AUTHZ_DENIED` fail closed | passed |
| revoked/missing grant 以 gateway-local `403 PUBLIC_AUTHZ_DENIED` fail closed | passed |
| no active policy 以 gateway-local `503 PERMISSION_SOURCE_UNAVAILABLE` fail closed | passed |
| ambiguous active policy 以 gateway-local `503 PERMISSION_SOURCE_UNAVAILABLE` fail closed | passed |
| readonly validate 成功，readonly mutation 本地失败 | passed |
| trusted header injection 使用 read-model decision evidence | passed |
| caller-supplied public/trusted identity headers 被 strip | passed |
| Control Plane second gate 拒绝 forced insufficient trusted permissions | passed |
| gateway-local denied requests 不创建 Control Plane audit/idempotency rows | passed |
| raw public tokens 和 gateway secret 不泄漏到 evidence | passed |
| v0 中 `hosted_permission_decisions` 保持为空 | passed |
| public CRUD、OAuth/OIDC、production gateway、marketplace、vault、billing、workflow、automatic propagation 和 Data Plane mutable reads 保持 out of scope | passed |

## Dogfood Evidence

观察结果：

- `status=passed`
- `missing_public_auth_status=401`
- `invalid_public_auth_status=401`
- `permission_source_unavailable_status=503`
- `missing_membership_status=403`
- `suspended_membership_status=403`
- `revoked_permission_status=403`
- `stale_policy_status=503`
- `ambiguous_policy_status=503`
- `readonly_validate_status=200`
- `readonly_import_status=403`
- `readonly_partition_status=403`
- `insufficient_forward_status=403`
- `partition_status=201`
- `partition_replay_status=200`
- `partition_violation_status=403`
- `import_status=201`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`
- `audit_counts.hosted_permission_decisions=0`

dogfood artifact 还证明：

- forwarded success cases 前，gateway-local failures 让 `admin_audit_events` 保持 `0`。
- trusted-header spoofing 没有影响 audit 中的 principal、actor、project、organization 或 token evidence。
- forced insufficient forwarded permissions 到达 private Control Plane second gate，并返回 `403 AUTHZ_DENIED`。
- audit 和 idempotency rows 不包含 gateway secrets 或 raw public bearer tokens。

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-read-model-gateway-runtime-wiring/report.json
git diff --check
git diff --cached --check
```

Go test 工作目录：

```text
services/control-plane
```

Python test 和 dogfood 工作目录：

```text
repository root
```

## Closeout Judgment

这个 runtime wiring slice 已完成。

上一 milestone 的主要风险是 hosted admin gateway 能否在不削弱既有 gateway contract 的情况下使用 internal read model。live proof 的答案是可以：public auth 仍是 gateway-local，project context 仍由 gateway 派生，read-model evidence 只有在 allow 后才变成 trusted header evidence，本地 denial 不会触达 Control Plane mutation/audit path，private Control Plane 仍作为 second gate 强制 endpoint permissions。

static fixture fallback 也仍然有价值。它让 focused contract tests 保持 fast/local，而 live dogfood 覆盖真实 Postgres/read-model path。

## Remaining Risks

### No Decision Persistence Yet

runtime permission decisions 已有 stable decision IDs 和 evidence，但 `hosted_permission_decisions` 仍为空。下一项风险是设计 append-only persistence，同时不泄漏 secrets，也不制造 write-path availability hazards。

### Lookup Helper Is Dogfood-Scoped

gateway harness 通过 local helper binary 调用 read model。对 local dogfood 来说可接受，但 production gateway 需要 in-process 或 service boundary design。

### No Real Public Identity Lifecycle

public token 到 principal 的映射仍是 local/dogfood。OAuth/OIDC、login、session、invitation 和 external subject lifecycle 仍是未来工作。

### No Policy Write Path

Hosted role、grant、membership 和 policy version mutation 仍是 out of scope。dogfood 仍使用 direct seed SQL。

### No Production Gateway Deployment

TLS、private networking、rollout、rate limits、observability、operational health 和 production routing 仍是未来工作。

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
Go Control Plane Hosted Permission Decision Persistence Design v0
```

原因：

- hosted permission decision table 已存在。
- read model 和 gateway runtime 现在已经产生 stable decision evidence。
- dogfood 当前断言 zero persisted decision rows；这个 contract 只有通过明确 design 才应改变。
- production-grade auditability、debugging 和 abuse investigation 之前需要 persistence。
- 这可以在不新增 public CRUD、OAuth/OIDC、production gateway deployment、billing、marketplace、workflow 或 automatic propagation 的情况下先设计。

预期范围：

- 设计 append-only decision persistence shape 和 write timing。
- 定义 success、denial、source-unavailable 和 lookup-error persistence semantics。
- 定义 secret-safe evidence 和 retention boundaries。
- 定义 persistence failures 如何影响 gateway allow/deny behavior。
- 定义 decision IDs 的 idempotency/deduplication expectations。
- 定义 implementation 前所需 tests 和 live dogfood。

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
