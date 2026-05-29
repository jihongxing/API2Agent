# API2Agent MVP 计划

## 1. MVP 定义

API2Agent 现在是分阶段 MVP。

```text
MVP-1：可用
  OpenAPI/curl -> capability package -> runner/MCP -> successful local call

MVP-2：可控
  generated package -> API2Agent Proxy -> third-party API -> usage event / metrics / quota

MVP-2.5：Credential-aware
  generated package/proxy -> credential resolver -> provider API -> usage event with credential_reference
```

MVP-1 证明 API 可以变成 Agent-callable tools。

MVP-2 证明 API2Agent 可以观测和控制执行路径，这是 billing、routing 和 marketplace 的前置条件。

MVP-2.5 证明 API2Agent 可以归因 API execution rights，而不是直接变成 payment system。

## 2. 当前实现状态

MVP-1 状态：已实现。

MVP-2 状态：第一版本地实现已完成，等待 dogfood。

已经实现的 MVP-2 能力：

- local `api2agent proxy`
- generated runner 通过 `API2AGENT_PROXY_URL` 进入 proxy mode
- SQLite usage event storage
- `api2agent usage`
- project-level quota
- success/failure/status/latency/cost recording

已经提前实现的相邻能力：

- Capability Schema v0.1 code model
- Provider Candidate model
- Metrics Snapshot model
- Routing Policy model
- `api2agent route`

这些相邻能力不代表可以继续越过路线图。Routing execution loop 必须等对应 roadmap phase 被接受后再实现。

Credential orchestration 状态：已文档化，尚未实现。

## 3. MVP 承诺

面向用户的承诺：

> 粘贴 OpenAPI 或 curl，得到一个可工作的 Agent tool package，可以本地直连，也可以通过 API2Agent Proxy 调用。

内部承诺：

> 先完成第一次成功 API 调用，再记录它是否成功、耗时多久、可能花费多少。

战略边界：

> Payment、full billing、routing、marketplace 不在 MVP 内。Proxy、usage events、quota 在 MVP-2 内。

> Credential schema 和 local resolver 属于 MVP-2.5，因为 credential ownership 是 API2Agent 成为 billing-ready infrastructure 的前置条件。

## 4. MVP 命令

Local tooling：

```bash
api2agent generate ./openapi.yaml --name my-api
api2agent inspect ./api2agent-output
api2agent test ./api2agent-output
api2agent run ./api2agent-output
```

Control layer：

```bash
api2agent proxy --db api2agent-usage.sqlite --port 8765 --quota 1000
api2agent usage --db api2agent-usage.sqlite --project-id local
```

Generated runners 通过环境变量启用 proxy mode：

```bash
API2AGENT_PROXY_URL=http://127.0.0.1:8765
API2AGENT_PROJECT_ID=local
API2AGENT_PROVIDER_ID=example_api
```

## 5. MVP 输出

生成目录：

```text
api2agent-output/
  README.md
  capability.json
  tools.json
  mcp_server.py
  runner.py
  auth.env.example
  smoke_test.py
  examples/
    openai_agent.py
    claude_desktop_config.json
```

Proxy artifacts：

```text
api2agent-usage.sqlite
usage_events table
usage summary report
```

## 6. MVP-1 功能需求：可用

CLI 必须：

- parse OpenAPI JSON/YAML
- parse curl commands
- normalize to API2Agent IR
- filter tools by tag/path/operation/max-tools
- generate a runnable capability package
- generate a local runner
- generate an MCP stdio server
- generate a smoke test

生成的 runner 必须：

- validate required parameters
- substitute path parameters
- attach query parameters
- attach JSON body
- attach auth header from env var
- make direct HTTP requests by default
- return structured success/error results

## 7. MVP-2 功能需求：可控

Proxy 必须：

- receive normalized call requests
- forward requests to third-party APIs
- measure latency
- record usage events
- classify success/failure
- estimate per-call cost when provided
- enforce project-level quota
- return structured success/error results

生成的 runner 必须：

- direct mode 仍然作为默认模式
- 当 `API2AGENT_PROXY_URL` 存在时切换到 proxy mode
- proxy call 中包含 project/capability/provider/tool metadata
- 向 proxy 发送 normalized HTTP request payload

Usage reporting 必须展示：

- total calls
- successful calls
- failed calls
- success rate
- average latency
- estimated cost
- error counts

## 7.5 MVP-2.5 功能需求：Credential-Aware

Credential resolver 必须：

- 支持 env/config/inline sources
- 表达 credential owner 和 provider
- 返回 injection patch，但不暴露 raw secrets
- 把 `credential_reference` 挂到 usage events
- 从 replay metadata 和 logs 中 redacts secrets

Proxy path 应该：

- 尽可能优先使用 proxy-side credential injection
- hosted mode 下避免 generated packages 保存 provider secrets

## 8. MVP 非功能需求

### Reliability

- 生成 Python 文件不能有语法错误。
- 缺少 auth 时必须给出清晰说明。
- Proxy errors 必须是结构化的。
- Quota exceeded 必须在 forward 前安全失败。

### Developer Experience

- 不需要 SaaS signup。
- Local direct mode 不依赖 proxy。
- Proxy mode 可以本地运行。
- README 解释两条路径。

### Safety

- Smoke tests 默认只跑 read-only endpoints。
- Write/delete tools 默认不自动测试。
- Proxy quota 限制滥用。

### Neutrality

- MCP 是第一个 runtime target，不是产品边界。
- API2Agent IR 保持 canonical。
- Proxy 和 usage events 是 model-neutral。

## 9. MVP 验收测试

### 测试 1：Local Usability

预期：

- `api2agent generate examples/openapi/basic.yaml` 可运行
- generated package 包含 runner/MCP/smoke test
- smoke test 可以调用一个安全 endpoint

### 测试 2：Tool Filtering

预期：

- large specs 可以在 package generation 前收敛
- selected tools 出现在 `capability.json`

### 测试 3：Proxy Forwarding

预期：

- 当 `API2AGENT_PROXY_URL` 存在时，generated runner 发送 proxy payload
- proxy forwards the request
- proxy 返回 structured result

### 测试 4：Usage Event

预期：

- 每次 proxied call 都记录 usage event
- event 包含 project、capability、provider、tool、success、status、latency、cost、error type

### 测试 5：Quota

预期：

- proxy 在 quota exceeded 后阻止调用
- quota failure 被记录并清晰返回

### 测试 6：Credential Resolution

预期：

- resolver 可以为 provider 选择 env/config credential
- execution 会把 credential 注入 provider request
- usage event 包含 `credential_reference`
- raw secret 不存入 usage event metadata

## 10. MVP 退出标准

MVP-1 完成条件：

- local capability generation works
- generated runner works
- MCP server works
- smoke test works

MVP-2 完成条件：

- generated runner 可以通过 API2Agent Proxy 调用
- proxy 记录 usage events
- proxy enforce quota
- usage report 展示 success/cost/latency

MVP-2.5 完成条件：

- credential schema 已实现
- local resolver 支持 env/config/inline sources
- execution 可以注入 resolved credentials
- usage events 安全记录 credential references

MVP-2.5 之后，下一阶段是加固 capability naming 和设计 hosted control plane。
