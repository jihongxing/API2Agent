# API2Agent 技术方案

## 1. 当前实现决策

API2Agent 当前使用 Python 做本地 compiler 和 MVP 生成 runtime。

这是实现路径，不是产品边界。

```text
Product goal: language-neutral, model-neutral, runtime-neutral
Current MVP: Python compiler and generated Python MCP runtime
```

## 2. 更新后的架构方向

架构现在分成两个主要平面。

### Local Tooling Plane

```text
OpenAPI / curl
  -> Parser
  -> API2Agent IR
  -> Tool Filter
  -> Capability Package
  -> runner.py / mcp_server.py / smoke_test.py
```

目的：

- fast local adoption
- open-source distribution
- 证明 API 可以变成 Agent-callable tools

### Hosted Control Plane

```text
Agent / generated runtime
  -> API2Agent Proxy
  -> third-party API
  -> Usage Event
  -> Metrics Store
  -> Quota / Cost / Routing
```

目的：

- control traffic
- observe success/cost/latency
- enable quota and future billing
- enable capability routing
- 保留未来商业化可选路径，但不把 marketplace 当作当前范围

## 3. 分层系统设计

### 3.1 Compiler Layer

职责：

- parse inputs
- normalize into API2Agent IR
- filter tools
- generate local and hosted runtime artifacts

当前代码：

```text
api2agent/
  cli.py
  filters.py
  parsers/
  ir/
  generators/
  safety/
```

### 3.2 Runtime Layer

职责：

- execute a generated tool
- validate params
- attach auth
- call direct API or proxy
- return structured result

当前 MVP runtime 是 generated Python code。

未来 runtime modes：

- direct local mode
- proxied hosted mode
- self-hosted enterprise mode

### 3.3 Proxy Layer

职责：

- receive normalized tool calls
- enforce project identity
- attach provider credentials
- forward to third-party APIs
- record usage events
- return structured success/error response

最小 proxy API：

```http
POST /v1/proxy/call
Authorization: Bearer <project_proxy_key>
Content-Type: application/json
```

Body：

```json
{
  "routing_decision_id": "route_123",
  "capability_id": "github_repos",
  "tool_id": "list_repos",
  "provider_id": "github",
  "params": {}
}
```

### 3.4 Metrics Layer

职责：

- store usage events
- aggregate success rate
- aggregate latency
- estimate cost
- expose usage reports

最小事件字段：

- routing_decision_id
- project_id
- capability_id
- provider_id
- tool_id
- timestamp
- success
- status_code
- latency_ms
- estimated_cost
- error_type

Routing decision ledger 字段：

- id
- project_id
- capability_id
- strategy
- preset
- selected_provider_id
- ranked_provider_ids
- metrics snapshot
- created_at

### 3.5 Capability Layer

职责：

- define semantic capability objects
- connect provider candidates
- define compatible inputs/outputs
- attach metrics snapshots
- attach pricing and safety metadata

### 3.6 Routing Layer

职责：

- select provider candidate
- apply routing policy
- fail over on errors
- respect quota and safety constraints
- log routing decisions

Routing 应该在 proxy metrics 存在后构建。没有 metrics，routing 只是猜。

## 4. 数据模型方向

### Capability

```json
{
  "id": "text_to_speech",
  "name": "Text to Speech",
  "description": "Generate spoken audio from text.",
  "input_schema": {},
  "output_schema": {},
  "safety": "write"
}
```

### Provider Candidate

```json
{
  "id": "openai_tts",
  "capability_id": "text_to_speech",
  "source": "api",
  "tool_id": "create_speech",
  "pricing": {
    "model": "per_call",
    "estimated_cost": 0.01
  }
}
```

Provider registry files 在 route 或 call execution 前会先做 schema validation：

```json
{
  "providers": [
    {
      "id": "ipify_public_ip",
      "capability_id": "public_ip_lookup",
      "provider_id": "ipify",
      "tool_id": "get",
      "estimated_cost": 0.001,
      "output_mapping": {
        "ip": "$.ip"
      },
      "metadata": {
        "package_dir": ".dogfood/ipify"
      }
    }
  ]
}
```

无效 registry JSON 应该在 routing 前失败，避免错误 provider metadata 悄悄污染 metrics 或 ledger output。

### Usage Event

```json
{
  "project_id": "proj_123",
  "capability_id": "text_to_speech",
  "provider_id": "openai_tts",
  "tool_id": "create_speech",
  "success": true,
  "status_code": 200,
  "latency_ms": 950,
  "estimated_cost": 0.01,
  "error_type": null
}
```

### Routing Policy

```json
{
  "strategy": "balanced",
  "weights": {
    "success_rate": 0.5,
    "latency": 0.3,
    "cost": 0.2
  }
}
```

### Usage Correlation

```json
{
  "routing_decision_id": "route_123",
  "usage_event_id": "evt_456",
  "selected_provider_id": "github",
  "success": true,
  "latency_ms": 950,
  "estimated_cost": 0.01
}
```

这条关联是 API2Agent 在本地支持 cost reporting、quota、routing audit，以及未来 hosted economic layer 前所需的最小 ledger。

### Failover Policy

Failover 是显式 policy，不是隐藏的 provider preference。

最小 policy 字段：

- enabled
- max_attempts
- retry_on_error_types
- retry_on_status_codes

默认可重试 status codes：

- 408
- 429
- 500
- 502
- 503
- 504

### Local Usage Ledger

本地 ledger 按以下维度聚合 direct 和 proxied usage：

- project_id
- capability_id
- provider_id

每一行报告：

- total_calls
- successful_calls
- failed_calls
- success_rate
- average_latency_ms
- estimated_cost

这不是 billing。它是负责任地设计 billing 之前必须先有的计量层。

### Direct Mode vs Proxy Mode Audit

API2Agent 支持两种 execution audit mode。

Direct local mode：

- generated runner 直接调用 provider API
- `execute_capability` 记录本地 usage event
- 适合 local dogfood 和 offline development
- 不执行 proxy quota 或 proxy auth

Proxy mode：

- generated runner 调用 API2Agent Proxy
- proxy 转发 provider API request
- proxy 记录 usage event
- 支持 quota、auth 和 centralized control

两种模式都会写入带 `routing_decision_id` 的 usage events，所以 `api2agent decision` 和 `api2agent ledger` 在两条路径下都可用。

两种模式也都会写入 `execution_mode`：

- `direct`
- `proxy`
- `shadow`

Proxy mode 仍然是 controllable execution 和未来经济计量的首选路径。

计划中的 execution modes：

- `race`：并发执行多个 providers，返回符合条件的最佳结果

`shadow` 可以让 API2Agent 在不增加用户 routing 风险的前提下采集 provider comparison data。

## 5. 为什么现在仍然适合 Python

Python 作为当前 compiler 仍然合理，因为：

- 第一批用户是 Agent builders
- OpenAPI/YAML/HTTP/testing 生态成熟
- MCP Python SDK 可以支持 MVP
- 迭代速度比高吞吐更重要

但 hosted control plane 未来可能使用混合栈：

```text
Python compiler workers
TypeScript/Node API service or dashboard
Postgres metrics store
Queue workers
Sandboxed execution workers
```

具体选择应该等 proxy 和 metrics requirements 更清楚后决定。

## 6. 近期技术优先级

### Priority 1：保持 Local Compiler 稳定

维护：

- API2Agent IR
- generated package
- tool filtering
- smoke tests
- MCP integration tests

### Priority 2：设计 Proxy Mode

后续增加生成选项：

```bash
api2agent generate openapi.yaml --proxy https://api.api2agent.com
```

Generated runner 应该能选择调用 proxy，而不是直连 third-party API。

### Priority 3：定义 Usage Event Schema

做 billing 前，先定义 event contract。

### Priority 4：定义 Capability Schema v0.1

要让 provider comparison 和 routing 可靠，先定义什么叫两个 API 可以在同一个 capability 下比较。

### Priority 5：构建 Routing v0

从简单 routing 开始：

- random
- lowest estimated cost
- highest observed success rate

### Priority 6：v0.1-alpha 产品抓手

alpha 产品抓手是 Reliability + Observability。

技术工作应该优先：

- deterministic replay design
- capability naming rule：`<domain>.<resource>.<action>`
- `shadow` execution mode
- golden trace marker
- two-provider failover + benchmark demo

## 7. Open-Core 边界

开源：

- compiler
- local package generation
- local runtime templates
- local tests

商业：

- hosted proxy
- metrics store
- quota enforcement
- credential vault
- routing
- registry
- billing

远期商业化选项，不属于当前产品范围：

- marketplace

这符合产品策略：free capabilities，但不放弃平台控制点。

## 8. 技术原则

技术北极星是：

> 每一次 Agent API call 都应该 executable、observable、comparable，并最终 routable。
