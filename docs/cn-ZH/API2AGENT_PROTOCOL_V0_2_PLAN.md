# API2Agent Protocol v0.2 Plan

状态：已被 frozen contract draft 取代。

Frozen contract：`docs/cn-ZH/API2AGENT_PROTOCOL_V0_2.md`

Schema snapshot：`schemas/api2agent/v0.2/protocol.schema.json`

Infra audit 后补强项：

- `RequestContext` 作为顶层 invocation context
- capability、provider 和 output mapping evolution 的 version fields
- aggregate cost、latency 和 reliability metrics 的 `metrics_window`
- 明确 `RoutingDecision` 是 pre-execution plan，`DecisionLog` 是 post-execution observation
- execution properties、credential resolution strategy 和 error scope

## 目的

Protocol v0.2 要把当前可运行的 MVP contracts 升级为工业级基础设施 contracts。

目标不是继续增加 runtime 功能，而是防止 Python reference implementation 把 protocol 锁死在 local MVP 假设里。

## Freeze 原则

v0.2 必须先稳定 contracts，再进入 production reimplementation。

稳定 contracts 应该是 language-neutral、runtime-neutral、model-neutral、source-neutral。

## 必须补强的内容

### 1. Latency Profile

当前 MVP 记录 aggregate latency。v0.2 需要结构化 latency：

- `latency_ms`
- `latency_p50_ms`
- `latency_p95_ms`
- `latency_p99_ms`
- `latency_cold_start_ms`
- `latency_network_ms`
- `latency_provider_ms`
- `latency_overhead_ms`
- `latency_region`

### 2. Network Topology

Routing 需要 topology awareness：

- `client_region`
- `edge_region`
- `api2agent_region`
- `provider_region`
- `selected_provider_region`
- `route_path`

### 3. Execution Class

v0.1 是 API-first。v0.2 必须为 source-neutral execution classes 预留字段：

- `api`
- `workflow`
- `tool`
- `model`
- `human`
- `async_job`

这些只是 protocol fields，不代表 v0.2 要实现所有 execution sources。

### 4. Reliability Profile

Routing 需要比 success rate 更完整的 reliability metrics：

- `reliability_score`
- `timeout_rate`
- `error_rate`
- `retry_rate`
- `failover_rate`
- `sla_confidence`

### 5. Decision Log

Decision records 必须保留：

- candidate providers
- candidate regions
- selected provider
- selected provider region
- routing policy
- routing context
- cost estimate
- latency estimate
- reliability estimate
- outcome

### 6. Capability Source Contract

Capability source 必须显式：

- `source_type`
- `execution_class`
- `executor_ref`
- `input_schema`
- `output_schema`
- `auth`
- `region_metadata`

## 非目标

Protocol v0.2 不实现：

- marketplace UI
- payment settlement
- all capability source adapters
- workflow engine
- hosted SaaS product

## 退出标准

Protocol v0.2 ready 的条件：

- schema fields 已文档化
- 定义 v0.1 backward compatibility
- Python MVP 可以 cleanly map into v0.2
- production architecture 可以实现 v0.2，且不继承 Python runtime 假设
