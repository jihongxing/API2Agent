# Go Control Plane Hosted Admin Gateway Contract Harness Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Hosted Admin Gateway Contract Harness implementation slice 可以关闭。

仓库现在有一个 local、dogfood-only gateway harness，已经通过真实 HTTP 证明 hosted admin trust boundary：

```text
public dogfood request
  -> local gateway harness
  -> public auth stub
  -> trusted header stripping
  -> static trusted claim injection
  -> Control Plane trusted-gateway auth
  -> private admin endpoint
  -> Postgres audit/idempotency evidence
```

推荐下一项任务：

```text
Go Control Plane Hosted Admin Gateway Permission Source Design v0
```

该任务应设计未来 hosted gateway 如何从 authenticated principal/project policy source 推导 trusted roles 和 permissions。不要实现 OAuth/OIDC、public CRUD、marketplace、vault、billing、workflow runtime、provider onboarding、automatic snapshot propagation，或 Data Plane 从 mutable Control Plane tables 读取。

## 现在已完成

### Design

已完成：

- local gateway harness responsibilities
- static public auth and identity policy
- public header stripping matrix
- trusted claim injection rules
- request id and idempotency propagation
- negative spoofing cases
- dogfood evidence requirements

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_DESIGN.md`

### Implementation

已完成：

- `scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py`
- standard-library `ThreadingHTTPServer` local gateway harness
- public bearer token policy stubs
- safe request header preservation
- caller-supplied `X-API2Agent-*` stripping
- public identity、cookie、proxy auth 和 public `Authorization` stripping
- trusted gateway authorization 和 key-id injection
- static principal、actor、project、organization、token、role 和 permission injection
- local `401`、`404` 和 `405` gateway failures
- Control Plane propagated `403 AUTHZ_DENIED`
- live Postgres audit/idempotency evidence checks

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| local gateway harness 作为 dogfood-only tooling 已实现 | passed |
| `/healthz` 可通过 harness 调用 | passed |
| public admin auth 可通过 harness 调用 registry validation | passed |
| caller-supplied trusted headers 被 strip | passed |
| harness-injected trusted claims 到达 Control Plane | passed |
| caller-supplied gateway authorization 被替换 | passed |
| missing public auth 在 gateway 本地返回 `401` | passed |
| local public auth failure 不创建 Control Plane audit rows | passed |
| readonly public auth 返回 Control Plane `403 AUTHZ_DENIED` | passed |
| admin import/replace 通过 harness 返回 `201` | passed |
| audit rows 使用 harness-injected identity | passed |
| idempotency row 使用 harness-injected project 和 actor | passed |
| audit metadata 包含 harness gateway key id | passed |
| raw public bearer tokens 和 raw gateway secret 未出现在 evidence/report artifacts | passed |
| 未增加 public CRUD、vault、billing、marketplace、workflow、provider onboarding 或 automatic propagation | passed |

## Validation

已通过：

```text
python -m py_compile scripts\go_control_plane_hosted_admin_gateway_contract_dogfood.py
```

已通过：

```text
go test ./...
```

目录：

```text
services/control-plane
```

已通过：

```text
python scripts\go_control_plane_hosted_admin_gateway_contract_dogfood.py --output tmp\go_control_plane_hosted_admin_gateway_contract_dogfood.json
```

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

最高风险的 gateway contract gap 已经从 unproven 变成 dogfooded：

- public callers 不能通过 harness 覆盖 trusted `X-API2Agent-*` identity 或 permission claims
- public `Authorization` 会在本地消费，不会到达 Control Plane
- request correlation 和 idempotency headers 可以穿过 gateway hop
- Control Plane authorization 仍然对 endpoint permissions 保持权威
- audit 和 idempotency evidence 反映 harness-issued trusted identity
- secret/token evidence 在 report artifacts 中保持 redacted

该实现刻意不是 production gateway。它是 contract proof，让项目可以进入下一个 hosted-readiness gap，同时不把 static dogfood auth 误认为真实 public auth。

## Remaining Risks

### Static Public Auth Only

Harness 使用 static dogfood bearer tokens。目前仍没有 OAuth/OIDC、login、session、invitation 或 user lifecycle model。

### Static Permission Policy Only

Roles 和 permissions 在 harness 中 hard-code。下一项设计应定义 permission source boundary，用于从 authenticated principal/project policy 推导 trusted gateway claims。

### No Production Gateway Deployment

Harness 是 local dogfood tooling。Production routing、TLS、WAF/rate limits、gateway observability、private network enforcement 和 secret distribution 仍是未来工作。

### Tenant-Partitioned Mutation Is Still Future Work

Project identity 会 scope audit 和 idempotency evidence，但 registry import/replace 仍是 full-registry replacement。

### No Automatic Propagation Was Added

Import/replace 仍然与 snapshot export、publish 和 Data Plane reload 分离。

## Still Not Allowed

不要开始：

- public registry CRUD APIs
- provider self-onboarding
- marketplace provider submission
- credential vault writes
- plaintext secret storage
- billing or settlement state
- workflow engine support
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables
