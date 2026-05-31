# Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0

日期：2026-05-31

状态：complete

## 决策

Hosted Admin Trusted Gateway Production Boundary implementation slice 可以关闭。

Control Plane 现在已经支持 production-shaped trusted-gateway boundary：

```text
active gateway secret set
  -> gateway bearer auth
  -> optional gateway key id
  -> trusted admin claims
  -> endpoint permission check
  -> secret-safe audit and idempotency evidence
```

推荐下一项任务：

```text
Go Control Plane Hosted Admin Gateway Contract Harness Design v0
```

该任务应设计一个 local gateway contract harness，用来证明 header stripping 和 trusted claim injection，不实现 OAuth/OIDC、public CRUD、provider onboarding、vault、billing、marketplace、workflow runtime 或 automatic propagation。

## What Is Now Complete

### Production Boundary Design

已完成：

- gateway-to-Control-Plane trust boundary
- trusted header strip/rewrite rules
- gateway authentication and secret rotation policy
- permission claim issuance assumptions
- audit/idempotency evidence contract
- failure semantics
- deployment and observability expectations
- implementation tests and dogfood requirements

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_DESIGN.md`

### Implementation

已完成：

- `--trusted-gateway-secrets`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRETS`
- legacy `--trusted-gateway-secret` compatibility
- rotation-compatible active secret set parsing
- active secret de-duplication
- fail-closed no-active-secret behavior
- active secret hashes 上的 constant-time matching
- `--trusted-gateway-key-id`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_KEY_ID`
- `X-API2Agent-Gateway-Key-ID`
- `registry.AdminPrincipal.GatewayKeyID`
- `registry.ImportReplaceOptions.GatewayKeyID`
- audit metadata `gateway_key_id`
- import/replace audit metadata `gateway_key_id`
- regression tests

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`

### Dogfood

已完成：

- hosted/trusted-gateway service 不传 `--admin-token` 即可启动
- old 和 new active secrets 在 rotation overlap 期间都可用
- service 仅用 new secret 重启
- 已移除 old secret 返回 `401 AUTH_ERROR`
- new secret 仍可执行 import/replace
- audit metadata 包含 non-secret `gateway_key_id`
- audit metadata 不包含 old/new raw gateway secrets
- idempotency scope 仍是 trusted project + trusted actor

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| accepted production boundary semantics 已实现 | passed |
| legacy single gateway secret 保持兼容 | passed |
| multiple active gateway secrets 可用 | passed |
| removed old gateway secret 被拒绝 | passed |
| no active gateway secret fail closed | passed |
| optional gateway key id 被解析为 non-secret evidence | passed |
| request key id 缺失时使用 configured gateway key id | passed |
| audit metadata 在存在时包含 `gateway_key_id` | passed |
| import/replace audit metadata 在存在时包含 `gateway_key_id` | passed |
| raw gateway secrets 不进入 audit metadata | passed |
| idempotency scope 仍是 trusted project + trusted actor | passed |
| local/private behavior 保持兼容 | passed |
| 未增加 public CRUD、vault、billing、marketplace、workflow、provider onboarding 或 automatic propagation | passed |

## Validation

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
python -m py_compile scripts\go_control_plane_hosted_admin_gateway_dogfood.py
python scripts\go_control_plane_hosted_admin_gateway_dogfood.py --output tmp\go_control_plane_hosted_admin_gateway_dogfood.json
```

## Closeout Judgment

这个 implementation slice 已完成。

Control Plane 现在具备 trusted gateway 需要的 production-side mechanics：

- active secret overlap 支持 no-downtime rotation
- old secret removal 可以被证明
- key id evidence 可以记录，且不暴露 raw secrets
- audit 和 idempotency 继续基于 trusted claims
- local/private mode 保持不变

剩余最高风险缺口不再是 Control Plane authenticator 内部，而是 gateway contract 本身：真实或本地 gateway layer 必须证明 public headers 会被 strip，trusted headers 会在 request 到达 Control Plane 前被 rewrite。

## Remaining Risks

### 还没有 Gateway Contract Harness

当前 live dogfood 仍直接用 simulated gateway headers 调用 Control Plane。它没有运行一个 gateway process 来 strip caller-supplied `X-API2Agent-*` headers 并注入 trusted claims。

### 还没有真实 Public Auth

OAuth/OIDC、sessions、invitations、login 和 user lifecycle 仍刻意不实现。

### Permission Source 仍在外部

Control Plane 会检查 endpoint permissions，但仍不会从 identity/project policy 派生 permissions。

### Deployment Boundary 尚未由 Infrastructure 强制

仓库文档说明 admin endpoints 应位于 gateway 后方的 private boundary，但还没有 deployment infrastructure 强制这一点。

### Tenant-Partitioned Mutation 仍是 Future Work

Project identity 会 scope audit 和 idempotency，但 registry import/replace 仍是 full-registry replacement。

### 没有增加 Automatic Propagation

Import/replace 继续与 snapshot export、publish 和 Data Plane reload 分离。

## Still Not Allowed

不要启动：

- public registry CRUD APIs
- provider self-onboarding
- marketplace provider submission
- credential vault writes
- plaintext secret storage
- billing or settlement state
- workflow engine support
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Next Task Rationale

下一项最高信号任务是：

```text
Go Control Plane Hosted Admin Gateway Contract Harness Design v0
```

原因：

- Control Plane 侧 trusted-gateway mechanics 已完成。
- 当前 dogfood 仍直接模拟 gateway output。
- gateway contract harness 可以在不实现真实 public auth 的情况下证明缺失的 edge behavior。
- scope 可以保持狭窄：strip public trusted headers、inject trusted claims、forward request id，并调用 Control Plane。

预期 design scope：

- local gateway harness responsibilities
- public header stripping matrix
- static test identity and permission policy
- trusted claim injection rules
- gateway secret and key-id forwarding
- request id propagation
- spoofed public headers 的 negative cases
- gateway-to-Control-Plane HTTP dogfood steps

不包含：

- OAuth/OIDC provider implementation
- production gateway deployment
- public registry CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime
