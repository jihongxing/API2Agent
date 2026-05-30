# API2Agent 产品需求文档

## 1. 产品愿景

API2Agent 是把 API 转化成 Agent-callable capabilities 的中立基础设施。

MVP 坚持 API-first。长期边界更大：任何能被表示为 `input -> execution -> output` 的来源，未来都可以通过 adapter 变成 Agent-callable capability。详见 `docs/cn-ZH/CAPABILITY_SOURCES.md`。

项目从 Agent capability compiler 开始：

```text
OpenAPI / curl
  -> API2Agent IR
  -> capability package
  -> MCP server / tool runtime
```

当前产品主线是 API2Agent 本身：

- 把 API descriptions 编译成 Agent capabilities
- 可靠执行 generated capabilities
- 让调用经过可观测控制点
- 收集 success、cost、latency 数据
- 长期收集 region-aware latency 和 routing data
- 让 capabilities 可比较、可路由
- 最大化真实执行数据
- 最小化 API/provider 接入成本
- 坚持 API onboarding first，同时为未来 source-neutral capability execution 预留抽象

长期产品可以变得更大：

```text
Agent request
  -> Capability Layer
  -> Routing Layer
  -> Credential Orchestration
  -> API2Agent Proxy
  -> API-like capability execution unit
  -> metrics, quota, pricing
```

Marketplace 是远期结果，不是当前产品目标。

## 2. 战略定位

旧定位：

> 把任意 API 转化成经过验证的 Agent 能力。

当前定位：

> 构建 API2Agent：让 Agent 可靠使用 API 的 capability compiler、proxy、metrics 和 routing layer。

v0.1-alpha 定位：

> 面向 Agent API 调用的本地执行与可观测层，用于提升 multi-provider API calls 的可靠性。

alpha 产品抓手是 Reliability + Observability：

- provider 失败时可以 fail over
- 按 success、cost、latency 比较 providers
- 有 location data 时，按 region-aware latency 比较 providers
- 每个 attempt 都进入 ledger
- 让失败调用可 replay、可 debug

战略权重更新：

- API2Agent 应该拥有最多真实执行数据。
- API2Agent 应该具备最低 API onboarding cost。
- 这两个目标是 routing quality 形成护城河的飞轮。

API2Agent 不只是 “Agent 时代的 Stainless”。Stainless 帮人类用 SDK 调 API，API2Agent 应该帮 Agent 通过中立基础设施选择和执行能力。

## 3. 核心判断

当前真正要赢的产品不是 marketplace。

当前真正要赢的产品是 API2Agent：可靠的 Agent capability infrastructure layer。

区别是：

- API 是实现方式。
- Capability 是意图。
- Metrics 让候选实现可比较。
- Routing 把 metrics 变成决策。
- Credentials 定义谁有调用权，以及消耗的是谁的资源。
- Economics 未来可以把 usage 变成商业化产品。

所以 API2Agent 必须从 generation 走向 controlled execution。

## 4. 产品层级

### Layer 1：Tooling Layer

把 API 描述转成可运行 Agent tools。

包括：

- OpenAPI/curl parser
- API2Agent IR
- tool filtering
- generated runner
- generated MCP server
- smoke test
- capability package

### Layer 2：Control Layer

让执行路径经过 API2Agent。

包括：

- hosted proxy
- project identity
- API credential handling
- usage tracking
- quotas
- structured logs
- latency/success/failure measurement

### Layer 3：Credential Orchestration Layer

在 economics 之前，API2Agent 需要 credential orchestration layer。

包括：

- credential ownership
- credential resolution
- credential injection
- credential masking
- usage events 中的 `credential_reference`
- BYOK、platform-key、provider-key 和 no-credential modes

这不是 payment。它是 payment 可信之前必须具备的 permission and attribution layer。

### Layer 3.5：Economic Layer

让 usage 未来可收费。

包括：

- cost estimation
- pricing metadata
- free quotas
- usage records
- billing integration later
- provider revenue share later

现在不需要支付，但必须先有 metering。

### Layer 4：Capability Layer

把多个实现归到同一个语义能力下。

示例：

```text
Capability: text_to_speech
  Candidate: elevenlabs_tts
  Candidate: openai_tts
  Candidate: internal_voice_service
```

这一层让 API 可以被比较。

### Layer 5：Routing Layer

为一次 capability request 选择最佳候选实现。

策略：

- lowest cost
- lowest latency
- highest success rate
- balanced score
- failover
- quota-aware routing
- policy-aware routing
- future location-aware routing

Routing 是 API2Agent 的决策引擎。

Location-aware routing 是未来 routing requirement，不是 v0.1 requirement。速度应建模为：

```text
total_latency =
  network_rtt
  + provider_processing_latency
  + api2agent_overhead
```

详见 `docs/cn-ZH/LOCATION_AWARE_ROUTING.md`。

### Layer 6：远期 Marketplace Layer

让 capability providers 竞争 Agent 流量。这不是当前构建重点。

Marketplace 只有在这些条件成立后才成立：

- 每个 capability 有多个 provider
- 有真实 metrics
- 有 routing 决策
- 有 pricing 和 quota rules
- 有 trust and safety policies

## 5. 目标用户

### 核心 ICP：Agent Builders

他们需要：

- 快速 API-to-tool conversion
- 可靠执行
- hosted proxy option
- usage visibility
- simple quotas
- 不用手写每个 API 的选择逻辑，也能选择最佳 capability provider

### 次级 ICP：API Providers

他们需要：

- official Agent-ready capabilities
- usage and success metrics
- 分发到 Agents
- 未来 revenue share
- 模型中立渠道

### 未来 ICP：Agent Platforms

他们需要：

- capability discovery
- routing infrastructure
- policy controls
- capability registry access
- quality and cost signals

## 6. MVP 范围

当前 MVP 仍然是 Free Tooling Layer。

MVP 目标：

> 把 OpenAPI/curl 转成本地 capability package，并证明至少一个生成工具可以被调用。

支持：

- REST JSON APIs
- OpenAPI JSON/YAML
- curl commands
- API key / Bearer token
- local runner
- MCP stdio server
- smoke test
- tool filtering

当前 MVP 不做：

- hosted proxy
- database
- billing
- marketplace UI
- routing
- OAuth
- multi-provider capability matching

但架构不能阻塞 Control Layer。

## 7. 近期产品升级

本地生成之后，下一个重要阶段不是继续加输入格式。

而是：

```text
generated tool -> API2Agent Proxy -> third-party API -> usage event
```

最小 proxy MVP：

- generated packages 可以选择调用 API2Agent proxy，而不是直连 API URL
- proxy 转发请求到 third-party APIs
- proxy 记录 usage events
- usage events 包含 success、status code、latency、tool id、capability id、provider id、estimated cost
- project-level quota 生效

## 8. 北极星指标

早期 tooling 指标：

> Time to First Successful Local Tool Call <= 3 分钟。

长期平台指标：

> 经过 API2Agent 路由且具备 cost、latency、outcome 数据的 Agent API 调用占比。

远期 marketplace 指标：

> 在竞争 providers 之间被路由的 capability fulfillment volume。

辅助指标：

- first-call success rate
- generated tool count after filtering
- proxy call success rate
- p50/p95 latency
- estimated cost per successful call
- quota hit rate
- routing win rate by strategy
- provider success rate by capability

## 9. 核心数据对象

### API2Agent IR

API operations 的中立描述。

### Capability Package

本地或 hosted 的可运行 tool package。

### Capability

Agent 想完成的语义任务。

### Provider Candidate

某个 capability 的一个具体实现。

### Usage Event

一次执行尝试的记录。

### Credential

调用 provider API 的权利，包含 ownership、injection 和 safe usage attribution metadata。

### Metrics Snapshot

用于 routing 和远期 marketplace 比较的 success/cost/latency 聚合数据。

### Routing Policy

选择 provider candidate 的机器可读决策策略。

## 10. 商业模式

Open-core 拆分：

开源：

- local compiler
- CLI
- local package generation
- local MCP/runtime templates
- basic tests

商业化表面：

- hosted proxy
- hosted metrics
- quotas
- credential orchestration
- credential vault
- routing
- private registry
- marketplace distribution later
- billing and revenue share
- enterprise policy controls

正确顺序：

```text
free tooling -> controlled usage -> metered usage -> paid usage -> far-term marketplace
```

## 11. 风险

### 风险：停留在一次性生成器

如果用户永远直连第三方 API，API2Agent 就没有 usage data、routing power 和 economic layer。

缓解：

- 尽早设计 proxy mode
- 在 billing 前让 hosted execution 本身有价值
- 让 metrics 对用户可见

### 风险：缺少 Credential Ownership

如果 API2Agent 不能说明用了哪个 credential、credential 属于谁，那么 usage data 就无法成为可信的 quota、routing、billing 或 marketplace data。

缓解：

- 定义 Credential Schema v0.1
- 构建 local credential resolver
- 尽可能通过 proxy 注入 credentials
- raw secrets 不进入 usage events 和 replay metadata

### 风险：过早做 Marketplace

没有 routing 和 metrics 的 marketplace 只是目录。

缓解：

- 先做 proxy 和 metrics
- 再做 capability grouping
- 再做 routing
- 最后做 marketplace

### 风险：Capability 抽象太弱

如果每个 endpoint 都被当成独立对象，API 无法竞争。

缓解：

- 定义 Capability Schema v0.1
- 把多个 provider 映射到同一个 capability
- 收集可比较 metrics

### 风险：Provider 或模型厂商锁定

缓解：

- API2Agent IR 保持 canonical
- MCP first, not MCP only
- provider-specific formats 都是 adapters

## 12. 成功标准

MVP 成功：

- 真实 API 可以生成可用本地 capability packages
- safe smoke tests 可以成功运行
- generated MCP server 可以被 Agent runtime 调用

Control Layer 成功：

- generated package 可以通过 API2Agent Proxy 调用
- proxy 可以记录 usage events
- quota 和 latency/success metrics 可用

Capability Layer 成功：

- 两个或更多 provider 可以映射到同一个 capability
- metrics 可以比较

Routing Layer 成功：

- routing 可以根据 policy 在 providers 之间选择
- failover 提升完成成功率

远期 marketplace 成功：

- providers 竞争 capability traffic
- Agents 或 Agent builders 可以基于真实 quality、cost、latency 选择能力
