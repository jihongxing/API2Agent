# API2Agent 核心概念

## 1. 这份文档回答什么

这份文档解释 API2Agent 的底层模型。Marketplace 是远期结果，不是当前构建目标。

它回答：

- 为什么 API2Agent 不只是 API-to-tool generator
- 什么是 API2Agent IR
- 什么是 capability package
- 为什么 proxy 和 usage tracking 重要
- 什么是 Capability Layer
- 什么是 Routing Layer
- 为什么 marketplace 不会从数据里自动长出来

## 2. 核心战略转向

API2Agent 起步是：

> Agent capability compiler。

但它应该演进为：

> Agent 调用、比较、路由并可靠执行 API-backed capabilities 的基础设施层。

简化成一句：

```text
API2Agent IR = 内部统一语言
Capability Package = 可运行交付物
Proxy = 控制点
Usage Metrics = 决策燃料
Capability Layer = 可比较性
Routing Layer = 决策引擎
Marketplace = 经济网络
```

## 3. API2Agent IR

大白话：

> API2Agent IR 是用 provider-neutral 方式描述 API operations 的内部统一语言。

输入会不同：

```text
OpenAPI
curl
Postman
GraphQL
API docs
SDK source
```

输出也会不同：

```text
MCP
OpenAI tools
Anthropic tools
Gemini function calling
TypeScript runtime
Hosted proxy route
```

IR 避免 `N * M` 集成爆炸。

当前 IR 描述：

- capability metadata
- auth
- tools
- parameters
- request body
- response shape
- safety level
- tags and operation ids

未来 IR 或相邻平台 metadata 还必须连接：

- capability ids
- provider candidate ids
- pricing hints
- routing hints
- observability metadata

## 4. Capability Package

大白话：

> Capability package 是 Agent runtime 真的可以使用的可运行 API 工具包。

它包含：

- `capability.json`
- `tools.json`
- `runner.py`
- `mcp_server.py`
- `smoke_test.py`
- `auth.env.example`
- README and examples

Capability package 仍然重要，但它不是终局。它是证明一个 API 可以被调用的 packaging format。

## 5. Proxy

大白话：

> Proxy 是把 API2Agent 从 generator 变成 infrastructure 的控制点。

没有 proxy：

```text
Agent -> third-party API
```

API2Agent 看不到流量。

有 proxy：

```text
Agent -> API2Agent Proxy -> third-party API
```

API2Agent 可以测量：

- 谁调用了
- 调用了哪个 tool/capability
- 是否成功
- 耗时多少
- 估算成本
- 错误类型
- quota 消耗

所以正确路径不是“免费然后收费”，而是：

```text
可用 -> 可控 -> 可收费
```

## 6. Usage Metrics

Usage metrics 是未来 routing 和 marketplace decision 的燃料。

最小事件：

```json
{
  "project_id": "proj_123",
  "capability_id": "image_generation",
  "provider_id": "provider_a",
  "tool_id": "generate_image",
  "success": true,
  "status_code": 200,
  "latency_ms": 1200,
  "estimated_cost": 0.02,
  "error_type": null
}
```

重要指标：

- success rate
- cost per successful call
- average latency
- p95 latency
- failure type distribution
- quota usage

数据本身不会创造 marketplace。数据只有进入 capability comparison 和 routing 后才有价值。

## 7. Capability Layer

大白话：

> Capability Layer 把很多 API 变成同一个 Agent intent 下的可比较候选项。

示例：

```text
Capability: text_to_speech
  Candidate: elevenlabs_tts
  Candidate: openai_tts
  Candidate: internal_voice_api
```

没有这一层，API2Agent 只有孤立 endpoints。孤立 endpoints 不能竞争。

Capability Layer 应定义：

- semantic name
- description
- input contract
- output contract
- safety level
- candidate providers
- compatibility rules
- observed metrics

## 8. Routing Layer

大白话：

> Routing Layer 决定哪个 provider candidate 应该完成一次 capability request。

Routing strategies：

- choose cheapest
- choose fastest
- choose highest success rate
- balanced score
- failover after failure
- respect quotas
- respect safety policies

Routing 是 API2Agent 变成平台的关键时刻，因为它开始决定谁获得 Agent 流量。

## 9. Marketplace

Marketplace 不会因为 API2Agent 有数据就自动出现。

Marketplace 需要：

- comparable capabilities
- multiple provider candidates
- routing decisions
- observed success/cost/latency metrics
- pricing rules
- provider incentives

所以正确顺序是：

```text
Tooling Layer
  -> Control Layer
  -> Economic Layer
  -> Capability Layer
  -> Routing Layer
  -> Marketplace
```

## 10. MCP First, Not MCP Only

MCP 仍然是第一个重要 Agent runtime target，因为它开放且可执行。

但 API2Agent 不能被定义成 MCP generator。

MCP 是输出。

IR、proxy、metrics、capability abstraction 和 routing 才是战略核心。

## 11. 最重要的产品判断

API2Agent 的护城河不应该是“我们能生成 schema”。

护城河应该变成：

- many API inputs normalized into IR
- runnable capability packages
- observed execution data
- comparable capability providers
- routing policies
- marketplace trust and economics

一句话：

> API2Agent 是把 API 变成 routable、measurable，并最终 marketable Agent capabilities 的基础设施层。
