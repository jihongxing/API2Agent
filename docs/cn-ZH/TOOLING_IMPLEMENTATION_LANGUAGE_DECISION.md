# Tooling 实现语言决策

日期：2026-05-31

状态：已接受

## 决策

API2Agent Tooling Re-entry 继续使用 Python。

Python 保留为 Tooling Layer 的 reference implementation、本地 CLI surface、package generator 和 dogfood harness。这不代表 API2Agent 变成 Python 绑定项目。

项目的技术中立性由 language-neutral 的稳定 contracts 保证：

- API2Agent IR
- capability package metadata
- generated tool schemas
- provider candidate metadata
- credential intent metadata
- usage、routing、ledger、replay、shadow、golden trace 和 receipt-ready event contracts
- Go Data Plane 消费的 Control Plane snapshots

实现分工：

```text
Python：
  OpenAPI/curl parsing
  IR generation
  package generation
  generated README/smoke test/MCP server
  local CLI
  Tooling baseline audits
  local dogfood harness

Go：
  production Data Plane
  production proxy path
  routing hot path
  retry/failover
  timeout budget enforcement
  durable event ingestion
  Control Plane registry、snapshot、distribution 和 persistence
```

## 为什么这不破坏中立性

API2Agent 的中立性是 protocol 和 artifact 的属性，不要求早期每个实现都立刻多语言重写。

中立边界是：

```text
API input -> language-neutral API2Agent artifacts -> runtime-specific implementations
```

Python 可以作为最快的 reference tooling implementation，但必须满足：

- generated artifacts 是 JSON/YAML contract objects，而不是 Python-only objects
- generated packages 保留 protocol identity fields
- Go services 可以消费相关 artifacts，不 import Python runtime internals
- Python 和 Go 路径重叠时，tests 和 dogfoods 验证语义兼容
- 未来 TypeScript、Rust、Java 或其他 SDK/tooling implementations 可以输出同样 artifacts

## 为什么现在不把 Tooling 重写成 Go

当前 Tooling Re-entry 目标是：

1. 更多真实调用数据
2. 更低 API/provider 接入成本
3. 更快 Agent API 响应可见性

这些目标主要由 parser quality、generation quality、generated documentation、smoke tests、proxy compatibility、credential-safe defaults 和 latency metadata 驱动。现在把 compiler/generator stack 重写成 Go，会拖慢 onboarding-cost 工作，却不能显著解决当前瓶颈。

Go 仍然是 production execution 和 control infrastructure 的正确方向，但并不要求每一次 tooling iteration 都用 Go。

## 护栏

Python Tooling 可以继续改进：

- OpenAPI reliability
- curl reliability
- operation naming
- endpoint-level auth inference
- base URL override handling
- generated package metadata
- generated smoke tests
- generated documentation
- local benchmark 和 dogfood helpers

Python Tooling 不能扩展成：

- hosted production Data Plane
- production proxy hot path
- production routing engine
- durable event ingestion service
- hosted Control Plane
- billing、settlement 或 credential vault
- workflow engine 或 non-API runtime

如果未来变更需要 production execution semantics，应优先用 Go 实现，或先放到 language-neutral contract 后面。

## 交接规则

后续贡献者不应该把“继续使用 Python”理解成“继续往 Python 里加 production runtime features”。

真正含义是：

```text
用 Python 改善 API-first onboarding 和 reference tooling。
用 Go 承担 production execution 和 control paths。
保持 protocol 和 emitted artifacts language-neutral。
```

