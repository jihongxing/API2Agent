# Go Data Plane 阶段复盘与巩固计划

日期：2026-05-30

状态：`efff899` 之后的阶段性巩固 checkpoint。

## 1. 当前定位

API2Agent 当前处在 Go Data Plane hardening 阶段。

当前目标不是 marketplace、billing、hosted SaaS 或大规模支持非 API 能力源。当前目标是：

```text
API2Agent -> local Go Data Plane execution + observability primitive
```

Python 继续保留为 reference implementation 和 local dogfood harness。Go 是 production Data Plane 方向。

## 2. 已经证明的能力

| 领域 | 状态 | 证据 |
|---|---|---|
| Protocol v0.2 | 已完成 | `docs/cn-ZH/API2AGENT_PROTOCOL_V0_2.md` 和 `schemas/api2agent/v0.2/protocol.schema.json` |
| Production architecture | 已完成 | `docs/cn-ZH/PRODUCTION_ARCHITECTURE_RFC.md` |
| Go Data Plane skeleton | 已完成 | `/v1/execute`、`/healthz`、local snapshots、deterministic routing |
| Protocol conformance | 已可用 | Go tests 会校验 `RequestContext`、`RoutingDecision`、`UsageEvent` 和 `DecisionLog` 是否符合 schema |
| Controlled retry/failover | 已完成 | `docs/cn-ZH/GO_DATAPLANE_FAILOVER_DOGFOOD_REPORT.md` |
| Credential resolution | skeleton 已完成 | env-backed credential intent、injection、redacted attribution |
| Durable local event ingestion | local slice 已完成 | fsync-backed JSONL writes 和 restart sequence recovery |
| Real external retry | dogfood 已完成 | `httpbin/status/500` fallback 到 `httpbin/ip` |

## 3. 需要加固的地方

这些不是新产品功能，而是在进入 hosted control plane 前必须完成的巩固工作。

### 3.1 Reusable Protocol Conformance Validator

当前 conformance 逻辑还嵌在 `execute_test.go` 里。

风险：

- dogfood scripts 无法复用
- 未来其他服务可能偏离 Protocol v0.2
- schema validation 还不是共享 contract gate

需要加固：

- 把 conformance validation 提取成可复用 Go package 或共享脚本
- Go tests 改成复用这个 validator
- JSONL dogfood output records 也能基于 schema snapshot 校验

### 3.2 Event Write Failure Policy

JSONL writer 已经具备 durable 写入能力，但 handler 调用点目前仍把 event write 当成 best-effort。

风险：

- execution 成功，但 audit / usage 数据静默丢失
- 未来 billing 和 routing dataset 不可信

需要加固：

- 定义不同 event type 的 fail-open / fail-closed 行为
- 增加 writer failure behavior 测试
- 让 event write failures 在 health 或 response semantics 中可见

### 3.3 Runtime Provider Availability Probe

真实外部 dogfood 发现：`api.ipify.org` 在本地 Go runtime 中可能被远端断开，即使这个 API 文档上可用。

风险：

- routing decision 假设 provider 可用，但没有 runtime proof
- 如果不从真实 execution runtime 测量，provider performance data 会失真

需要加固：

- 增加最小 provider probe dogfood
- 从 Data Plane runtime 记录 provider reachability
- 这一步只做 observability，不做 marketplace ranking

### 3.4 Timeout Budget Semantics

当前 timeout 是 per attempt 维度。

风险：

- 多次 retry 后，总请求时延可能超过 Agent 预期

需要加固：

- 明确定义 total budget vs per-attempt budget
- 把选择的 policy 持久化到 routing / request metadata
- 测试 budget exhaustion 下的 retry 行为

## 4. 下一步任务

下一步任务：

```text
Go Data Plane Consolidation Hardening v0
```

范围：

1. 提取 reusable Protocol v0.2 conformance validator。
2. Go tests 和 dogfood output validation 都复用这个 validator。
3. 定义 event write failure policy。
4. 增加 event writer / handler integration 的 failure-path tests。
5. 增加一个小型 runtime provider availability probe dogfood。

退出标准：

- conformance validation 不再是 test-local helper
- dogfood JSONL events 可以基于 Protocol v0.2 校验
- event write failures 有明确行为
- provider reachability 从 Go runtime 中测量
- roadmap 和 implementation plan 指向下一个明确 slice

## 5. 非目标

本轮 consolidation 不做：

- hosted database
- billing
- marketplace UI
- provider onboarding portal
- workflow runtime
- multi-region data plane
- queue-backed ingestion pipeline

这些仍然属于后续阶段。
