# Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0

日期：2026-06-02

状态：complete

## 决策

Hosted Permission Decision Persistence implementation slice 可以作为 v0 关闭。

仓库现在已经证明：local hosted admin gateway 可以为 authenticated allowed、denied 和 source-unavailable decisions 持久化非 secret hosted permission decision evidence，同时保留 gateway-local auth failures、fail-closed forwarding behavior、Control Plane second-gate authorization 和 secret-safe artifacts。

推荐下一项任务：

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Design v0
```

该任务应保持为 design/hardening task。重点应放在 duplicate decision integrity、partial-failure row semantics、sentinel/schema hardening options 和 metadata retention/privacy。不要新增 public role CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、policy write APIs，或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Gateway-Owned Persistence

已完成：

- local hosted admin gateway 的 `hosted_permission_decisions` persistence helper
- permission decision 解析后、allowed forwarding 前执行 append-only writes
- authenticated allowed、denied 和 source-unavailable decision persistence
- missing/invalid public auth persistence skip
- unknown route 和 unsupported method 仍保持在 persistence 之外
- source-unavailable sentinel subject 和 policy evidence
- bounded metadata：request、route、gateway key、status、error type、permission source 和 persistence version
- persistence write failures 的 local failure evidence

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

已完成：

- local Postgres schema apply
- hosted permission seed data 与 source-unavailable sentinel seed data
- trusted-gateway mode 下的 private Control Plane
- hosted read-model permission-source mode 且启用 decision persistence 的 gateway
- allowed、denied、source-unavailable、readonly、second-gate、partition、replay 和 import cases
- secret-safe persisted-row checks
- redacted JSON artifact output

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| gateway owns hosted permission decision persistence | passed |
| allowed authenticated decisions 在 forwarding 前持久化 | passed |
| denied authenticated decisions 在 local denial response 前持久化 | passed |
| source-unavailable authenticated decisions 在需要时用 sentinel evidence 持久化 | passed |
| missing/invalid public auth 不持久化 hosted decision rows | passed |
| unknown route/method 不持久化 hosted decision rows | passed |
| allowed decision persistence failure 在 forwarding 前 fail closed | passed |
| denied/source-unavailable persistence failure 保留原始 fail-closed response，并记录 local evidence | passed |
| persisted metadata 排除 public bearer tokens、`Authorization`、cookies、gateway secrets、OAuth tokens、plaintext credentials 和 vault material | passed |
| live dogfood 证明 expected persisted row count 和 row families | passed |
| gateway-local failures 下 Control Plane audit/idempotency boundaries 保持不变 | passed |
| public CRUD、OAuth/OIDC、production gateway、marketplace、vault、billing、workflow、automatic propagation、policy write APIs 和 Data Plane mutable reads 保持 out of scope | passed |
| duplicate decision id with different evidence 会触发 explicit integrity error | deferred risk |

## Dogfood Evidence

观察结果：

- `status=passed`
- `audit_counts.hosted_permission_decisions=15`
- `audit_counts.admin_audit_events=5`
- `audit_counts.idempotency_records=2`
- `permission_decision_rows_after_invalid_public_auth=0`
- `persistence_unavailable_status=503`
- `persistence_unavailable_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- decision status counts：`200=7`、`403=5`、`503=3`
- required permission counts：`validate=9`、`import_replace=2`、`project_partition_replace=4`

dogfood artifact 还证明：

- missing 和 invalid public auth 后 hosted decision rows 保持 `0`。
- unsupported path 返回 `404 PUBLIC_ROUTE_NOT_FOUND`。
- unsupported method 返回 `405 PUBLIC_METHOD_NOT_ALLOWED`。
- allowed persistence failure 在创建 Control Plane audit rows 前返回 `503 PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`。
- readonly mutation attempts 持久化 denied decision rows，且不创建 Control Plane audit/idempotency rows。
- forced insufficient forwarded permissions 先产生 allowed gateway decision，然后由 Control Plane second gate 返回 `403 AUTHZ_DENIED`。
- persisted rows 不包含 raw public tokens、caller `Authorization`/`Cookie` material 或 trusted gateway secret。

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence/report.json
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

这个 implementation slice 已完成 local v0。

上一 milestone 的主要风险是 permission decisions 能否在不削弱 hosted admin gateway contract 的前提下被记录。live proof 的答案是可以：public auth failures 仍是 gateway-local 且不创建 decision rows，authenticated decisions 会在 allow/deny 完成前持久化，allowed write failure 会阻止 forwarding，本地 denials 仍不会触达 Control Plane mutation/audit paths，private Control Plane 仍是 second authorization gate。

该实现仍刻意保持 local/dogfood-scoped。它证明的是 request-time ownership 和 evidence boundary，不是 production retention、policy mutation、public identity lifecycle 或 gateway operations。

## Remaining Risks

### Duplicate Decision Integrity Needs Hardening

实现使用 deterministic decision IDs 和 `ON CONFLICT (id) DO NOTHING`。这具备 deterministic behavior，但尚未证明 byte-equivalent duplicate evidence，也不会对 conflicting evidence 抛出 explicit integrity error。这应成为下一项 hardening design topic。

### Sentinel Fields Are A v0 Compatibility Choice

Source-unavailable decisions 使用 sentinel subject/actor/org/policy values 来满足当前 `NOT NULL` 和 FK constraints。这让 local proof 保持简单，但 production schema semantics 可能需要 nullable partial-failure fields、dedicated sentinel rows，或更严格的 failure-evidence table shape。

### Persistence Is Still Harness-Scoped

gateway harness 通过 local SQL execution 写入。Production gateway integration 仍需要明确 service/process boundary、connection lifecycle、retry/backoff、observability 和 rollout design。

### Retention And Tenant Privacy Are Deferred

Append-only decision records 对 auditability、debugging 和 abuse investigation 有价值，但 production retention、export、deletion 和 tenant privacy controls 尚未实现。

### No Real Public Identity Or Policy Write Lifecycle

Public token mapping 和 hosted permission seed data 仍是 local/dogfood。OAuth/OIDC、login/session/invitation lifecycle 和 hosted policy mutation APIs 仍是未来工作。

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
- policy write APIs
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Design v0
```

原因：

- persistence proof 现在已经在 live Postgres 上跑通。
- duplicate/conflicting decision evidence 是 persistence boundary 内最大的 remaining correctness gap。
- sentinel row semantics 对 v0 可接受，但在进入 production-shaped persistence 前应明确 harden。
- decision rows 成为 durable product data 前，需要 metadata retention/privacy design。
- 这可以在不启动 public CRUD、OAuth/OIDC、production gateway deployment、billing、marketplace、workflow 或 automatic propagation 的情况下先设计。

预期范围：

- 定义 duplicate decision conflict behavior 和 tests。
- 决定保留、约束或替换 partial failures 的 sentinel evidence。
- 定义 metadata allowlist、redaction 和 retention expectations。
- 定义 persistence integrity 所需的 schema/index/constraint changes。
- 定义 hardening slice 的 live dogfood evidence。

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
- policy write APIs
- Data Plane mutable Control Plane table reads
