# API2Agent 远期经济层策略

## 0. 范围边界

这是一份长期策略文档。

这份文档不是 active implementation roadmap。具体下一步做什么，以 `ROADMAP.md` 为准。

当前产品是 API2Agent：compiler、capability package、proxy、metrics、routing 和 reliable execution。

Marketplace 是远期可能结果。它不是当前产品，不是当前 MVP，也不是 active implementation phase。

## 1. 战略修正

API2Agent 不只是 API 转 tool 的工具。

更准确的判断是：

> API2Agent 是 Agent 发现、选择、调用、观测并最终支付 API-backed capabilities 的入口层。

产品应该按这个顺序演进：

```text
可用 -> 可控 -> 可计量 -> 可比较 -> 可路由 -> 可靠执行
```

经济层和 marketplace 只有在 API2Agent execution layer 可靠之后才有意义。

不要直接从“免费工具”跳到“支付收费”。中间缺失的关键层是控制权。

在控制权之后，下一个缺失的中间层是 credential orchestration：谁拥有调用权、使用哪个 credential、消耗的是谁的资源。

## 2. 正确阶段逻辑

### Phase 1：Free Tooling Layer

目标：

让 API 可以快速被 Agent 调用。

核心能力：

- OpenAPI/curl to tool schema
- API2Agent IR
- generated runner
- generated MCP server
- smoke test
- tool filtering

这一阶段创造 adoption，不直接追求收入。

### Phase 2：Control Layer

目标：

让执行路径经过 API2Agent。

必需能力：

- hosted proxy
- usage tracking
- success/failure tracking
- latency measurement
- cost estimation
- user/API/capability identity
- basic quotas

关键变化：

```text
Agent -> third-party API
```

变成：

```text
Agent -> API2Agent Proxy -> third-party API
```

这会创造未来计量、路由和收费的权利。

### Phase 2.5：Credential Orchestration Layer

目标：

在引入 payment 之前，先让受控流量可以归因到 credential owner。

必需能力：

- credential ownership model
- credential resolver
- credential injection
- credential masking
- usage event `credential_reference`
- BYOK、platform-key、provider-key 和 no-credential modes

关键变化：

```text
Agent -> API2Agent Proxy -> third-party API
```

变成：

```text
Agent -> API2Agent Proxy -> resolved credential -> third-party API
```

这会创造未来区分 user-paid calls、platform-paid calls、provider-sponsored calls 和 free/internal calls 的能力。

### Phase 3：Billing Layer

目标：

把受控流量变成可收费 usage。

可能的定价方式：

- developer subscription
- per-call usage billing
- quota upgrades
- team/enterprise plans
- API provider revenue share

第一天不需要支付系统，但系统必须设计成未来可以不改执行路径就接入 billing。

### Phase 4：Capability Layer

目标：

让 API 可以被比较。

API endpoint 不是市场对象，capability 才是。

例子：

```text
Capability: image_generation
  Candidate A: provider_api_a
  Candidate B: provider_api_b
  Candidate C: internal_workflow_c
```

每个候选实现应该暴露：

- semantic capability definition
- input/output contract
- execution adapter
- observed success rate
- observed latency
- estimated cost
- pricing model
- safety and policy metadata

### Phase 5：Routing Layer

目标：

把指标变成决策。

Routing 决定哪个候选实现应该响应一次 capability request。

早期策略：

- lowest cost
- lowest latency
- highest success rate
- balanced score
- failover on error
- quota-aware routing

这是平台化质变点。API2Agent 不再只是生成工具，而是开始决定谁获得 Agent 流量。

### Phase 6：Capability Marketplace

目标：

创建一个 Agent 可以发现和调用能力、供应商可以竞争履约的市场。

市场只有在三件事成立后才会出现：

- 可比较：多个 provider 映射到同一个 capability
- 可选择：routing 在 provider 之间做选择
- 有经济：调用有价格、额度和激励

Marketplace 是 capability abstraction + routing + economic rules 的结果，不是 API 目录。

## 3. 为什么不是 API Market

传统 API marketplace 面向人类开发者。

它展示的是：

- endpoints
- documentation
- pricing pages
- manual subscription flows

Agent 需要的是：

- semantic capability search
- machine-readable contracts
- observed quality metrics
- automatic provider selection
- safe execution
- metered usage

所以 API2Agent 应该瞄准 Agent Capability Marketplace，而不是传统 API marketplace。

## 4. Marketplace 对象模型

### Capability

一个语义化任务单元。

示例：

```json
{
  "name": "generate_marketing_poster",
  "description": "Generate an ecommerce marketing poster from product inputs.",
  "inputs": {},
  "outputs": {},
  "safety": "write"
}
```

### Provider Candidate

一个 capability 的具体实现。

可以是：

- third-party API
- internal API
- hosted workflow
- multi-step tool chain

### Metrics

真实执行数据：

```json
{
  "success_rate": 0.92,
  "avg_latency_ms": 1200,
  "estimated_cost_per_call": 0.02,
  "p95_latency_ms": 2100
}
```

### Pricing

经济合约：

```json
{
  "model": "per_call",
  "price": 0.02,
  "currency": "USD"
}
```

### Routing Policy

决策规则：

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

## 5. 第一个现实 MVP 升级

现在不要做 marketplace 网站。

先做最小 control-plane 路径：

```text
Agent
  -> generated tool / MCP server
  -> API2Agent Proxy
  -> third-party API
  -> usage event
  -> metrics store
```

最少记录数据：

- user id or local project id
- capability id
- tool id
- provider id
- request timestamp
- status code
- success/failure
- latency
- estimated cost
- error type

最小控制：

- per-project quota
- read-only default safety
- proxy API key
- no payment system yet

## 6. 战略规则

免费产品要创造 adoption，但不能放弃未来控制点。

规则是：

> 免费能力可以存在，但不可观测的直连执行不是未来平台路径。

本地生成可以继续开源。Hosted proxy、metrics、routing、registry、marketplace、billing 可以成为 open-core 的商业化表面。
