# Control、Receipt 与 Trust Layer Strategy

日期：2026-05-31

状态：战略方向，不是当前 active implementation task

判断：API2Agent 应该从 API-to-Agent tooling 演进为 controlled execution、receipt、routing 和 trust layer。这个策略不改变当前下一项工程任务，下一项仍然是 `Go Control Plane Persistent Registry Store Schema v0`。

## 1. 为什么重要

API2Agent 当前路径是正确的：

```text
API -> Tooling -> Proxy -> Usage -> Metrics -> Routing
```

战略风险是停得太早。

如果 API2Agent 只是：

```text
API -> Agent tool generator + optional proxy
```

用户生成 tool 后就可以绕过系统。API2Agent 会失去真实执行数据、routing leverage 和长期平台权力。

长期目标应该更强：

```text
API -> Capability -> Controlled Execution -> Receipt -> Routing Decision -> Trust / Settlement
```

## 2. 权力分层模型

### Layer 1: Tooling Layer

状态：方向上已实现。

API2Agent 已经支持：

- OpenAPI/curl to IR
- capability package generation
- generated runner
- generated MCP server

这是入口，不是护城河。

### Layer 2: Control Layer

状态：部分实现。

API2Agent 已经具备：

- proxy execution
- usage events
- metrics
- quota
- Go Data Plane execution

只有当真实调用持续经过 API2Agent 时，这一层才真正有价值。

### Layer 3: Credential Orchestration

状态：本地已实现，但还没有战略武器化。

API2Agent 已经具备：

- credential ownership
- injection
- attribution
- local config and env resolution

长期看，credential ownership 会成为 trust weighting 和 abuse resistance 的一部分。

### Layer 4: Capability and Routing Layer

状态：已设计并部分 dogfood。

API2Agent 已经有 capability abstraction、provider candidates 和 routing policies。下一项战略要求是让 routing 依赖真实执行数据，而不只是静态配置。

### Layer 5: Receipt, Trust, and Settlement Layer

状态：尚未实现。

这是未来 protocol-level power layer。

它最终应该支持：

- verifiable call receipts
- trust-weighted metrics
- anti-gaming controls
- routing confidence
- settlement-ready execution records

Marketplace 仍然是远期结果，不是当前产品。

## 3. 核心判断

护城河不是 tool generation。

护城河是：

```text
Routing Control
+ Policy Layer
+ Receipt / Trust Data
```

API2Agent 应该让 Agent 依赖它对执行的解释：

```text
What was called?
Who called it?
Which credential was used?
Which provider executed?
Did it succeed?
How much did it cost?
How long did it take?
Should this provider be chosen next time?
Can the record be trusted?
```

## 4. Usage Event vs Receipt

当前 `UsageEvent` 不应该立刻删除或重命名。

推荐拆分：

```text
UsageEvent = internal execution observation
Receipt = protocol-grade, verifiable execution evidence
```

`UsageEvent` 仍然服务于 local observability、debugging、metrics 和 replay。

`Receipt` 应该成为未来用于 routing、trust 和 settlement 的 externalizable structure。

## 5. Receipt v0.1 候选字段

Receipt v0.1 应该从现有 execution records 派生。

候选字段：

- `receipt_id`
- `schema_version`
- `request_id`
- `routing_decision_id`
- `attempt_id`
- `parent_attempt_id`
- `project_id`
- `agent_id`
- `capability_id`
- `capability_version`
- `provider_id`
- `provider_version`
- `tool_global_id`
- `credential_reference`
- `input_hash`
- `output_hash`
- `status_code`
- `success`
- `error_type`
- `error_scope`
- `latency_ms`
- `estimated_cost`
- `observed_cost`
- `cost_source`
- `client_region`
- `provider_region`
- `created_at`
- `signing_key_id`
- `signature`

设计规则：

```text
Do not replace UsageEvent now.
Add Receipt later as a signed or hash-bound derivative once execution semantics are stable.
```

## 6. Proxy 作为默认路径

Proxy 必须逐步成为 generated tools 的默认路径。

目标方向：

```text
generated tool
  -> API2Agent proxy
  -> provider
```

Direct execution 仍然应该保留，用于：

- local development
- air-gapped use
- debugging
- privacy-sensitive self-hosted deployments

但 direct execution 应明确标记为 routing、receipt 和 trust properties 较弱。

## 7. Routing 必须尽早真实发生

Routing 一开始不需要复杂。

但它必须真实影响 execution。

未来最小规则：

```text
if provider_a.weighted_success_rate < provider_b.weighted_success_rate:
    route to provider_b
```

战略里程碑是 Agent/provider selection 开始依赖 API2Agent-collected data。

## 8. Receipt Farming 风险

未来风险：

API providers 可能通过 API2Agent 生成假流量或低质量流量，刷高自己的 routing rank。

这就是 `Receipt Farming`。

防御方向：

- identity-weighted metrics
- project trust scores
- 真实用户 credential 绑定的 BYOK calls 权重更高
- anonymous 或 low-trust traffic 权重更低
- rate limits and anomaly detection
- credential quality signals
- 带 confidence 和 sample size 的 metrics windows
- 分离 test、shadow、replay 和 production traffic
- 标记 suspicious provider self-traffic 的 audit flags

设计含义：

```text
Not every receipt should have equal routing weight.
```

## 9. Privacy and Edge-Mesh Proxy

只有 Hosted Proxy 可能会阻碍 enterprise adoption。

很多 Agent builders 不希望 raw API keys、business inputs 或 provider outputs 经过第三方 hosted proxy。

API2Agent 应该支持两条 execution tracks：

### Hosted Proxy

适合：

- individual developers
- simple BYOK flows
- low-sensitivity workloads
- easiest onboarding

API2Agent 可以接收更完整的 execution data。

### Edge-Mesh Proxy

适合：

- enterprise users
- private APIs
- regulated data
- internal agent workflows

本地或客户控制的 proxy 负责：

- credential injection
- raw request execution
- input/output redaction
- local policy enforcement

只把安全 metadata 上报：

- request hashes
- output hashes
- status code
- error taxonomy
- latency
- cost metadata
- credential reference
- provider identity
- routing decision id
- signed receipt metadata

设计含义：

```text
API2Agent must collect trustworthy execution metadata without always collecting raw payloads.
```

## 10. Roadmap 影响

这个策略应该影响未来 protocol 和 architecture 工作，但不应该打断当前 persistence roadmap。

近期：

- 继续 `Go Control Plane Persistent Registry Store Schema v0`
- 保留 `UsageEvent`
- 保留 `DecisionLog`
- 保留当前 snapshot contract

未来 protocol 工作：

- Receipt v0.1
- signed/hash-bound execution evidence
- receipt-derived routing metrics
- identity-weighted metrics
- Edge-Mesh Proxy metadata contract
- anti-farming trust policy

未来 architecture 工作：

- Data Plane 或 Edge Proxy 中的 receipt signer
- Control Plane receipt ingestion
- trust-weighted metrics pipeline
- 消费 trusted receipts 的 routing policy
- provider self-traffic 的 audit model

## 11. 非目标

现在不要实现：

- payment settlement
- public receipt exchange
- marketplace ranking UI
- full trust score system
- cryptographic receipt network
- mandatory hosted proxy
- enterprise Edge-Mesh product

## 12. 实施前置条件

Receipt 工作应该在以下条件满足后开始：

- 当前 UsageEvent 和 DecisionLog semantics 稳定
- Control Plane persistence 存在或正在实现
- routing 已经消费真实 metrics
- credential references 被稳定写入
- proxy 或 local edge execution 成为 generated path 的默认路径

## 13. 战略判断

API2Agent 不应该停在 API-to-Agent compiler。

长期机会是成为：

```text
the layer that records, verifies, interprets, and routes Agent calls to real-world capabilities
```

这就是 useful tool 和 infrastructure 的区别。
