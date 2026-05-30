# MVP Exit Review

日期：2026-05-30

## 决策

API2Agent Python MVP 已经达到退出标准。

项目应该进入 MVP freeze，并切换到 Architecture Definition Phase。

这不是因为项目失败而暂停，而是因为 MVP 已经成功：它验证了 feasibility、DX shape、protocol shape 和 local execution loop。

## 证据

最新验证测试结果：

```text
pytest
143 passed
```

已验证的 proof points：

- OpenAPI/curl compiler
- API2Agent IR
- capability package generation
- generated runner
- MCP server
- smoke test
- local proxy
- usage events
- quota
- ledger
- credential resolver
- credential injection
- routing
- failover
- shadow
- replay
- golden trace
- output normalization
- region-aware routing
- provider-region semantics
- decision dataset seed

## 退出标准映射

MVP-1 已完成：

- local capability generation works
- generated runner works
- MCP server works
- smoke test works

MVP-2 已完成：

- generated runner 可以通过 API2Agent Proxy 调用
- proxy records usage events
- proxy enforces quota
- usage report 展示 success、cost、latency 和 errors

MVP-2.5 已完成：

- credential schema 已实现
- local resolver 支持 env/config/inline sources
- execution 可以注入 resolved credentials
- usage events 安全记录 credential references

## Freeze 决策

Python 保留为：

- reference implementation
- local development tool
- protocol proof harness
- dogfood runner

Python 不应该成为以下长期主实现：

- hosted high-throughput proxy
- low-latency routing engine
- multi-tenant control plane
- credential vault
- durable billing-ready ledger
- marketplace execution infrastructure

## 现在停止什么

除非能保护 protocol clarity，否则不要继续添加 Python MVP 功能。

停止：

- new capability source implementations
- marketplace UI
- billing and settlement
- SaaS productization
- more CLI polish
- broad runtime expansion

## 现在开始什么

进入 Architecture Definition Phase：

- Protocol v0.2 freeze plan
- Production Architecture RFC
- Control Plane vs Data Plane boundary
- data model finalization
- long-term language/runtime decision
- 从 Python reference implementation 迁移的路径

## 战略判断

API2Agent 不再是在验证 Agent 是否能调用 API。

下一阶段要回答的是：API2Agent 能不能成为 Agent 调用世界能力的中立协议和执行基础设施。
