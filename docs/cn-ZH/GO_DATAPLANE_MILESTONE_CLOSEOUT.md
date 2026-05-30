# Go Data Plane 阶段里程碑收口

日期：2026-05-30

状态：已完成

判断：API2Agent 已经可以进入 Phase 6 planning 和第一项 Go Control Plane minimum implementation slice。

## 1. 里程碑范围

这个里程碑收口的是本地 Go Data Plane hardening 阶段。

本阶段目标是：

```text
API2Agent -> local Go Data Plane execution + observability primitive
```

本阶段不做：

- hosted SaaS
- marketplace UI
- billing or settlement
- workflow runtime
- multi-region active-active deployment
- public provider onboarding

## 2. 已完成能力

Go Data Plane 现在支持：

- `/v1/execute` 本地执行
- `/healthz` runtime health metadata
- Protocol v0.2 execution graph records
- reusable Protocol v0.2 JSONL conformance validation
- 基于 local snapshots 的 deterministic routing
- ranked providers 之间的 retry 和 failover
- per-attempt `UsageEvent`
- final `DecisionLog` aggregation
- durable JSONL event writes 和 restart-safe sequence recovery
- request-level timeout budget semantics
- snapshot freshness fail-closed behavior
- local process-level project quota
- env-backed request credential resolution
- local JSON credential config loading
- redacted credential attribution
- credential audit metadata，包含 version、lifecycle、rotation hint 和 resolution timestamp
- ordered attempt correlation，包含 `parent_attempt_id` 和 `attempt_chain`

## 3. 证据

最近实现提交：

```text
4fa8362 Add attempt correlation metadata
114f0c7 Add credential audit metadata
4f22390 Implement credential config loading
f3e2811 Implement project quota gate
eb34cce Implement snapshot freshness gate
d0dbadc Implement timeout budget semantics
d9fa65c Harden Go data plane consolidation
efff899 Add durable ingestion and real retry dogfood
a9d295a Add Go failover dogfood and protocol conformance
```

Dogfood 证据：

- `docs/cn-ZH/GO_DATAPLANE_FAILOVER_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_DURABLE_EVENTS_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_REAL_EXTERNAL_PROVIDER_RETRY_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_PROVIDER_PROBE_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_TIMEOUT_BUDGET_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_FRESHNESS_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_PROJECT_QUOTA_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_CREDENTIAL_CONFIG_DOGFOOD_REPORT.md`

当前验证基线：

```text
go test ./...
python -m pytest
go_dataplane_failover_dogfood
go_dataplane_real_external_provider_retry_dogfood
go_dataplane_credential_config_dogfood
```

## 4. 退出标准检查

| 标准 | 状态 | 说明 |
|---|---|---|
| Protocol v0.2 schema 可被 Go Data Plane 使用 | 通过 | Execution graph records 可通过 `api2agent-conformance` 校验。 |
| Data Plane 可以端到端执行 capability | 通过 | `network.public_ip.get` 可通过本地和真实 providers 执行。 |
| Failover 可观测 | 通过 | 失败和 fallback attempts 会分别写入 usage events。 |
| Event ingestion 对 local alpha 足够 durable | 通过 | JSONL writer 使用 fsync 和 sequence recovery。 |
| Timeout semantics 有边界 | 通过 | Total request budget 会跨 attempts 执行。 |
| Snapshot policy 可审计 | 通过 | routing 前会检查 snapshot version 和 freshness。 |
| Project-level control point 存在 | 通过 | local quota gate 可以在 provider forwarding 前阻断。 |
| Credential boundary 存在 | 通过 | env/config credentials 可以注入 secrets，但不记录 raw values。 |
| Attempt graph 可解释 | 通过 | 已记录 parent attempt links 和 decision attempt chains。 |

## 5. 剩余缺口

这些缺口是预期内的，应进入 Phase 6 或更后阶段处理。

- 没有 hosted project model
- 没有 hosted API2Agent API key model
- 没有 hosted capability registry
- 没有 hosted provider registry
- 没有 hosted credential metadata store
- 没有 KMS-backed secret vault
- 没有 persistent database-backed quota accounting
- 没有 snapshot distribution service
- 没有 analytics API 或 dashboard
- 没有 billing
- 没有 marketplace

## 6. 阶段判断

API2Agent 不应该默认继续增加更多 local Go Data Plane hardening。

下一阶段应该开始：

```text
Phase 6: Go Control Plane Minimum
```

这个判断是有条件的：

- 可以开始 Phase 6 design 和第一项 implementation slice
- 还不能进入 hosted public alpha
- 还不能做 billing
- 还不能做 marketplace

## 7. 建议的 Phase 6 入口任务

Phase 6 的第一项任务应该是：

```text
Go Control Plane Minimum v0
```

范围：

1. Project model
2. API2Agent project API key model
3. Capability registry model
4. Provider registry model
5. Credential metadata model，不包含 secret storage
6. Routing snapshot export format，供现有 Go Data Plane 消费

退出标准：

- Control Plane 可以生成 versioned local snapshot。
- Go Data Plane 可以使用 Control Plane code 生成的 snapshot 执行。
- 现有 Data Plane dogfoods 继续通过。
- 不包含 hosted deployment、billing 或 marketplace 工作。

## 8. 战略判断

项目已经从 Python MVP validation 进入了 local production primitive 阶段。

下一步最重要的问题已经不是：

```text
Can an Agent call an API through API2Agent?
```

这件事已经被证明了。

下一步的问题是：

```text
Can API2Agent manage projects, provider metadata, credentials, and routing snapshots as a control plane?
```

这才是正确的下一阶段。
