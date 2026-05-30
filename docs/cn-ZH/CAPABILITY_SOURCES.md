# Capability Sources

## 目的

API2Agent 从 API 起步，但长期产品不应该只局限于 API。

稳定边界是：

```text
anything executable -> API-like capability execution unit -> Agent-callable capability
```

API2Agent 不应该变成 workflow engine、agent framework、script runtime，或者 marketplace-first product。它应该把外部能力变成可执行、可观测、可路由，并最终可计量经济价值的能力。

## 核心规则

一个来源只有能被表示成下面结构，才适合接入 API2Agent：

```text
input -> execution -> output
```

如果不能被表示成这种结构，它就不属于 API2Agent 范围。

## MVP 边界

MVP 仍然坚持 API-first。

MVP 支持：

- OpenAPI
- curl
- HTTP/REST endpoints
- generated capability package
- proxy execution
- credential resolution
- usage、ledger、metrics
- provider routing 和 failover
- output normalization
- region-aware routing metadata

MVP 不支持：

- workflow engine execution
- local function runtime
- arbitrary script sandbox
- database query runtime
- human task routing
- agent-as-provider execution
- marketplace search
- payment 或 settlement

MVP 可以为未来来源预留 schema fields 或 adapter interfaces，但不能把这些来源作为一等 runtime 实现。

## 长期 Capability Sources

未来 API2Agent 可以通过 adapters 支持多种 capability sources。

| Source | Examples | API2Agent Role |
| --- | --- | --- |
| API | REST, GraphQL, gRPC, webhooks, SaaS APIs | 编译并执行为 routable capabilities |
| Workflow | Zapier, n8n, Temporal, Airflow, internal workflows | 调用 workflow endpoints；不变成 workflow engine |
| Local Function / Tool | Python function, CLI command, local script | 包装成具备 input/output schema 的 controlled executor |
| Stateful System | database, CRM, ERP, ecommerce backend, transaction system | 把安全 action 暴露为 capabilities |
| Human / Hybrid | human review, expert task, annotation | 把人工完成视为 execution provider |
| Agent-as-Provider | specialized agent, internal assistant | 把另一个 agent 包装在 capability contract 后面 |

## Capability Execution Unit

长期统一抽象是 Capability Execution Unit。

最小字段：

- `capability_id`
- `source_type`
- `input_schema`
- `output_schema`
- `executor`
- `provider_id`
- `auth`
- `cost_model`
- `latency_profile`
- `success_metrics`
- `region_metadata`
- `execution_mode`

初始 `source_type` values：

- `api`
- `workflow`
- `local_function`
- `cli`
- `database`
- `human`
- `agent`

## 实施顺序

推荐顺序：

1. v0.1-alpha：只做 API，但 execution abstraction 保持 source-neutral。
2. v0.2：Local Function adapter prototype。
3. v0.3：Workflow adapter prototype。
4. v1.0：多种 source types 共用同一套 control、routing、metrics 和 credential layers。

不要做 workflow engine。API2Agent 应该站在 workflow systems 之上，把它们变成 Agent-callable。

## 战略句子

MVP：

> API2Agent starts with APIs only, but every API is modeled as an executable capability so future workflow, function, and tool sources can reuse the same control, routing, metrics, and economic layers.

长期：

> API2Agent becomes the neutral capability execution layer that lets Agents discover, route, call, observe, and eventually pay for any external capability source.
