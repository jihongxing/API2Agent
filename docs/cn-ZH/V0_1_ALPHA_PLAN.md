# API2Agent v0.1-alpha 计划

状态：planned

## 1. Alpha 定位

API2Agent v0.1-alpha 是：

> 面向 Agent API 调用的本地执行与可观测层，用于提升 multi-provider API calls 的可靠性。

对用户来说，最锋利的承诺不是“把 API 变成工具”。

更锋利的承诺是：

> 让 Agent 调 API 比直接调用 provider 更可靠、可计量、可调试。

Marketplace 仍然不在当前范围内。

## 2. 必须存在的产品抓手

alpha 必须证明开发者为什么要用 API2Agent，而不是直接调用 API。

alpha 选择的抓手是：

```text
Reliability + Observability
```

用大白话说：

- 一个 provider 失败时，API2Agent 可以 fail over
- 两个 providers 提供同一能力时，API2Agent 可以比较它们
- 生产调用失败时，API2Agent 可以告诉开发者发生了什么
- provider 质量变化时，API2Agent 有数据影响未来 routing

## 3. Alpha Demo

核心 alpha demo 应该是：

```text
one capability
  -> two providers
  -> primary failure
  -> fallback success
  -> usage ledger
  -> benchmark comparison
```

建议 demo capability：

- `weather.current.get`

建议 providers：

- `open_meteo`
- `wttr_in`

demo 必须输出：

- attempts
- selected provider
- fallback provider
- success rate
- p50/p95 latency
- ledger rows
- routing decision

demo 要让产品价值变得肉眼可见：

```text
不用 API2Agent：直接 provider call 可能失败且难以追踪
使用 API2Agent：失败被记录，fallback 成功，metrics 被保留
```

## 4. Alpha 范围

必须包含：

- local compiler
- SDK call path
- provider adapters
- routing strategy
- failover
- usage events
- ledger
- benchmark helper
- replay design
- capability naming rule
- execution mode matrix

可以包含：

- local replay command
- shadow execution mode
- golden trace marker

不包含：

- marketplace UI
- hosted SaaS
- payment
- provider revenue share
- public provider onboarding

## 5. Capability 命名规则

alpha 应该强制一个最小命名约定：

```text
<domain>.<resource>.<action>
```

示例：

- `weather.current.get`
- `github.repo.list`
- `payment.charge.create`
- `crm.contact.lookup`

类似 `weather.get` 的临时 legacy ID 可以为了兼容暂时保留，但新的文档和示例应该优先使用 alpha 命名规则。

## 6. Execution Mode Matrix

API2Agent execution modes：

| Mode | 状态 | 目的 |
| --- | --- | --- |
| `direct` | 已实现 | 不经过 proxy 的本地执行 |
| `proxy` | 已实现 | 通过 API2Agent Proxy 的受控执行 |
| `shadow` | 计划中 | 调用额外 providers 采集 benchmark 数据，但不影响主结果 |
| `race` | 未来 | 并发调用多个 providers，返回符合条件的最佳结果 |

`shadow` 是从 benchmark tooling 走向 routing data 的关键桥梁。

## 7. Replay

Replay 是 alpha 必须设计的能力。

目标：

```text
api2agent replay <usage_event_id>
```

Replay 应该帮助开发者：

- debug failed calls
- 复现 provider behavior
- 从真实调用生成 regression tests
- 审计 routing decisions

最小 replay 要求：

- usage event lookup
- routing decision lookup
- request metadata reconstruction
- credentials 安全脱敏
- 当无法完全 replay 时给出清晰 warning

## 8. Golden Trace

Golden trace 是被标记为“已知正确”的 execution。

草案字段：

```json
{
  "is_golden": true
}
```

用途：

- regression testing
- provider scoring
- routing evaluation
- future benchmark baselines

Golden trace 不要求第一轮代码就实现，但 contract 不应该阻塞它。

## 9. Alpha 退出标准

v0.1-alpha 完成时必须满足：

- repo 有 clean baseline commit
- `pytest` passes
- README 和 Quickstart 能复现 alpha demo
- 一个 capability 可以跑两个 providers
- failover 记录失败和成功 attempts
- benchmark 报告 p50/p95 latency 和 success rate
- ledger 可以按 provider 和 execution mode 检查调用
- replay 已设计，并且要么本地实现，要么明确标记为下一项 alpha task

## 10. 下一步实施顺序

1. repo baseline and CHANGELOG
2. alpha quickstart
3. capability naming rule
4. replay design and local command
5. shadow execution mode
6. golden trace field
7. SDK and CLI demo cleanup
