# API2Agent Tooling Re-entry Review + Tooling Expansion Plan v0

日期：2026-05-31

状态：已完成

## 摘要

现在暂停更深的 Control Plane 实现，回到 API2Agent Tooling Layer 是合适的。

这不是退回一次性 generator，而是带约束的 re-entry：

```text
API -> Agent-ready package -> default observable execution path -> real usage data
```

Tooling Layer 现在应该优化三个产品目标：

1. 更多真实调用数据
2. 更低 API/provider 接入成本
3. Agent API 调用响应更快

当前实现边界仍然保持 API-first。API2Agent 不能变成 workflow engine。

## 为什么现在合适

基础设施路线已经到达一个很好的暂停点：

- Go Data Plane 已经证明 execution、event ordering、retry/failover、credentials、timeout budgets、quota 和 durable event ingestion。
- Go Control Plane 已经证明 snapshot export、distribution、service API、Postgres load parity、runtime wiring、live Postgres dogfood、persistent audit writes、failure semantics 和 mutation boundary review。
- 下一项 Control Plane 任务是 import/replace transaction 的设计任务，不是紧急 runtime blocker。

因此项目可以安全回到漏斗顶部：让更多真实 API 更容易被转换成可靠的 Agent capabilities。

## Re-entry 决策

结论：

```text
暂停更深的 Control Plane 写侧工作。
在 Control/Data Plane 约束下恢复 API2Agent Tooling Layer 扩展。
```

实现语言决策：

```text
Tooling Re-entry 继续使用 Python 作为 reference tooling implementation。
production execution 和 control paths 继续由 Go 承担。
protocol artifacts 必须保持 language-neutral。
```

参见 `docs/cn-ZH/TOOLING_IMPLEMENTATION_LANGUAGE_DECISION.md`。

Tooling Layer 现在负责喂给 execution/data flywheel：

```text
更低接入成本
  -> 更多 generated packages
  -> 更多 calls 经过 observable paths
  -> 更多 usage/latency/cost/error data
  -> 更好的 routing 和 reliability
```

## 产品目标

### 目标 1：更多真实调用数据

Tooling 应该增加 API2Agent 能观测到的真实 API 调用数量。

Tooling 含义：

- generated packages 应该让 proxy/observable execution 更容易选择
- generated packages 应该保留 capability/provider/tool identity
- generated packages 应该输出足够 metadata，用于 usage、replay、routing 和 future receipts
- generated packages 应该把 credential intent 和 raw provider secrets 分离
- quickstarts 和 dogfoods 在安全时应该优先使用真实 API，而不是 synthetic examples

成功信号：

- 更多真实 API dogfoods 成功
- 更多 generated packages 可以不经手动修改跑通 proxy mode
- 更多 usage events 带有稳定的 `capability_id`、`provider_id`、`tool_id`、`execution_mode`、`credential_reference` 和 latency metadata

### 目标 2：更低 API/Provider 接入成本

Tooling 应该让 API onboarding 比手写 Agent tools 更便宜。

Tooling 含义：

- OpenAPI import 应该用更少人工 patch 处理常见真实 specs
- curl import 应该更好地推断 names、auth、parameters 和 defaults
- large specs 应该被过滤成 Agent-usable packages
- generated docs 应该展示最短可用调用路径
- generated smoke tests 应该默认安全，同时足够帮助验证 integration

成功信号：

- 从 OpenAPI/curl input 到第一次成功调用的时间降低
- generation 后需要的 manual edits 减少
- 模糊命名如 `api` 的 generated packages 减少
- large specs 生成 focused packages，而不是不可用的 endpoint dumps

### 目标 3：更快响应

Tooling 应该帮助 generated capabilities 更快返回有用结果。

Tooling 含义：

- generated packages 在已知时应保留 provider region metadata
- generated runners 应暴露 timeout controls 和合理 defaults
- benchmark helpers 应报告 p50/p95 latency
- docs 应引导开发者有意识地选择 direct/local/proxy modes
- generated provider metadata 应支持未来 location-aware routing

成功信号：

- generated package dogfoods 包含 latency results
- benchmark outputs 可见 p50/p95 latency
- API 暴露或用户配置 region 时，provider region metadata 存在
- direct local execution 中 generated runners 避免不必要 overhead

## 硬约束

### API-first

当前实现范围保持：

- OpenAPI
- curl
- HTTP/REST APIs
- generated capability package
- generated runner
- generated smoke test
- generated MCP server

### 不做 Workflow Engine

不实现：

- workflow engine execution
- Zapier/n8n/Temporal/Airflow orchestration
- local function runtime
- arbitrary script sandbox
- database runtime
- human task routing
- agent-as-provider runtime

Workflow systems 以后可以通过 API-like adapters 或 endpoints 被调用，但 API2Agent 不能变成 workflow engine。

### 不做 Marketplace 工作

不实现：

- marketplace UI
- provider public onboarding
- provider revenue share
- billing 或 settlement
- marketplace ranking edits

Marketplace 仍然是可靠 execution、control、routing、metrics 和 economics 之后的远期结果。

### 保持 Control Layer 兼容

Tooling work 必须保持：

- proxy mode
- credential-safe generated runners
- usage event identity fields
- routing decision compatibility
- replay/shadow/golden trace paths
- Protocol v0.2 direction
- generated packages 作为 provider candidates 时与 Go Data Plane snapshot compatibility 兼容

### 保持实现中立性

Python 是当前 Tooling Layer implementation，不是 protocol identity。

Tooling work 必须保持：

- JSON/YAML artifacts 作为稳定 contract boundary
- Go services 不隐式依赖 Python runtime internals
- 与 Go Data Plane 和 Go Control Plane contracts 重叠的路径保持语义兼容
- 未来 TypeScript、Rust、Java 或其他实现可以输出同样 API2Agent artifacts

## 扩展范围

### Track A：OpenAPI Reliability

目标：

让更多真实 OpenAPI specs 可以生成可用的 Agent capability packages。

候选任务：

- endpoint-level auth extraction
- base URL/server override hardening
- large spec filtering defaults
- operation naming improvements
- common real specs 的 schema edge-case handling
- generation diagnostics，解释 skipped 或 risky operations

### Track B：curl Reliability

目标：

让单条命令 API onboarding 接近即时可用。

候选任务：

- 更好的 curl capability/provider/tool naming
- 更好的 Bearer/API key/header/query auth inference
- 更强的 query/header/body default preservation
- 更安全的 write-operation smoke-test guidance
- curl-derived packages 的 generated README improvements

### Track C：Generated Package Observability Defaults

目标：

让 generated packages 自然喂给 API2Agent 的 control 和 metrics layers。

候选任务：

- generated package metadata audit
- proxy-mode setup simplification
- generated runner identity fields hardening
- generated README 中的 credential intent documentation
- generated runner paths 的 latency/timeout metadata propagation

### Track D：Real API Dogfood Harness

目标：

在不增加 hosted infrastructure 的情况下增加真实 execution data。

候选任务：

- 维护一小组安全的 read-only real API dogfoods
- generated packages 同时跑 direct 和 proxy modes
- 记录 onboarding steps、manual edits、first-call time、success、cost estimate 和 latency
- 输出 tooling benchmark report

### Track E：Speed and Region Readiness

目标：

让 generated packages 为更快 execution 和未来 location-aware routing 做准备。

候选任务：

- generated packages 中的 optional provider region metadata
- generated benchmark command/report for p50/p95 latency
- generated runner docs 中的 timeout defaults
- direct vs proxy latency comparison dogfood

## 优先 Sprint 计划

### Sprint 1：Tooling Baseline Audit

输出：

```text
API2Agent Tooling Baseline Audit v0
```

衡量：

- OpenAPI generation success
- curl generation success
- first successful call path
- manual edits required
- generated naming quality
- proxy compatibility
- credential safety
- safe calls 的 p50/p95 latency

推荐真实输入：

- GitHub REST read endpoint
- httpbin bearer/read endpoints
- ipify public IP
- Open-Meteo weather
- 一个 medium/large OpenAPI spec

### Sprint 2：Low-Cost Onboarding Fixes

目标 fixes：

- endpoint-level auth
- base URL override
- curl naming
- generated README guidance
- safer manual write-test path design

### Sprint 3：More Data by Default

目标 fixes：

- proxy-mode setup simplification
- generated runner identity metadata checks
- credential intent examples
- direct/proxy dogfood report

### Sprint 4：Faster Response Readiness

目标 fixes：

- generated package latency benchmark helper
- p50/p95 reporting
- optional provider region metadata
- direct vs proxy latency comparison

## 验收标准

Re-entry 成功的标准：

- 至少 5 个真实 API onboarding attempts 被文档化
- safe read paths 的 generated packages 可以不改源码运行
- credentials 允许时，generated packages 可以跑通 proxy mode
- usage events 包含稳定 identity 和 credential-safe metadata
- benchmark output 包含 latency data
- docs 清楚保留 API-first 和 no-workflow-engine 约束

## 建议下一项任务

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

Baseline audit、onboarding hardening、provider-region metadata、authenticated proxy credential dogfood、generated-package latency benchmark、endpoint-level auth inference、base URL override、manual write test path、large spec performance、curl naming residual review 和 Tooling Re-entry closeout slices 已完成。

Tooling Re-entry phase 现在暂停。Control Plane import/replace transaction design、CLI implementation、live Postgres dogfood 和 readiness review 也已完成，所以下一项工程任务是 private admin endpoint design。

## 非目标

- 本 re-entry plan 不做 Control Plane mutation API。
- 不做 workflow engine。
- 不做新的 non-API capability source runtime。
- 不做 hosted SaaS implementation。
- 不做 vault。
- 不做 billing。
- 不做 marketplace。
