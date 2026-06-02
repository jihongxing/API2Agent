# API2Agent Quickstart

这份 quickstart 证明当前可发布候选版本的主路径：

```text
OpenAPI 3.x / curl / HAR / Postman / Insomnia / Bruno / workflow endpoint / GraphQL endpoint
  -> API2Agent IR
  -> Agent capability package
  -> OpenAI tools schema
  -> local runner
  -> MCP stdio server
  -> smoke test
```

当前发布重点是 Agent Capability Compiler。Routing、proxy、ledger、failover 和 hosted control 都是后续层，不是第一版可发布能力的必要证明。

## 1. 安装

```bash
python -m pip install -e ".[dev]"
python -m api2agent.cli --help
python -m pytest
```

期望测试结果：

```text
267 passed
```

## 2. 从 OpenAPI 生成

```bash
python -m api2agent.cli generate examples/openapi/basic.yaml --output api2agent-output --force
```

期望输出：

```text
Generated capability package: api2agent-output
Diagnostics: pass ...
```

生成目录包含：

- `capability.json`
- `tools.json`
- `diagnostics.json`
- `auth.env.example`
- `README.md`
- `runner.py`
- `smoke_test.py`
- `manual_write_test.py`
- `mcp_server.py`
- `examples/openai_agent.py`
- `examples/claude_desktop_config.json`

## 3. Inspect 生成包

```bash
python -m api2agent.cli inspect api2agent-output
```

这会展示生成后的 capability 名称、base URL、auth 形态、safety 摘要、tool 列表、参数要求和 response 摘要。

查看原始 JSON：

```bash
python -m api2agent.cli inspect api2agent-output --json
```

## 4. Diagnose 可用性

```bash
python -m api2agent.cli diagnose api2agent-output
```

Diagnostics 默认是 advisory，用来判断生成包是否足够安全、清晰，能不能接给 Agent 使用。

常见信号包括：

- 缺少 provider region metadata
- operation 描述缺失或过弱
- write/delete tools 需要人工明确测试
- 缺少 base URL 或 auth metadata
- schema 或 response shape caveat

## 5. 运行 Smoke Test

```bash
python -m api2agent.cli test api2agent-output
```

默认 smoke test 只运行安全的 read-only 路径。如果生成包只有 write/delete tools，只能在你控制的目标上显式使用 `--allow-write`：

```bash
python -m api2agent.cli test api2agent-output --allow-write
```

也可以直接运行某个生成 tool：

```bash
python -m api2agent.cli test api2agent-output --tool get_post --params "{\"post_id\": 1}"
```

## 6. 试用 OpenAI Tool Calling

生成包包含一个 Responses API 示例，会加载 `tools.json`，并把 tool call 分发给生成的 runner：

```bash
python -m pip install openai
OPENAI_API_KEY=...
python api2agent-output/examples/openai_agent.py
```

OpenAI SDK 不是 API2Agent 自身依赖；只有运行这个示例时才需要安装。

## 7. 启动 MCP Server

```bash
python -m api2agent.cli run api2agent-output
```

这会启动生成的 MCP stdio server，并保持进程打开，等待 MCP client 连接。

Claude Desktop 风格的配置入口在：

```text
api2agent-output/examples/claude_desktop_config.json
```

## 8. 从 curl 生成

如果还没有 OpenAPI 文件，可以先用 `--curl`：

```bash
python -m api2agent.cli generate \
  --curl="curl https://api.example.com/items?verbose=true --json '{\"name\":\"demo\"}'" \
  --output api2agent-curl-output \
  --force

python -m api2agent.cli inspect api2agent-curl-output
python -m api2agent.cli diagnose api2agent-curl-output
```

curl 生成出的 write tools 会刻意给出更强 diagnostics。这是好事：compiler 应该在 Agent 调用前把风险暴露出来。

## 9. 从 HAR Capture 生成

如果能在浏览器里抓到真实 network traffic，但还没有 OpenAPI 文件或 collection，可以使用 `--har`：

```bash
python -m api2agent.cli generate \
  --har tests/fixtures/har/basic_capture.har \
  --output api2agent-har-output \
  --force

python -m api2agent.cli inspect api2agent-har-output
python -m api2agent.cli diagnose api2agent-har-output
```

API2Agent 会把捕获到的 HTTP requests 转成 tools，过滤常见浏览器噪声 headers，并保留 query、body、auth hint 和 response-shape 证据。

## 10. 从 Postman Collection 生成

如果 API contract 在 Postman Collection 里，可以使用 `--postman`：

```bash
python -m api2agent.cli generate \
  --postman tests/fixtures/postman/basic_collection.json \
  --output api2agent-postman-output \
  --force

python -m api2agent.cli inspect api2agent-postman-output
python -m api2agent.cli diagnose api2agent-postman-output
```

Postman folders 会变成 tool tags，collection variables 可提供 base URL，request path/query/header/body 会被编译进同一套生成包格式。

## 11. 从 Insomnia 或 Bruno 生成

如果 API requests 保存在 Insomnia 或 Bruno collection 工具里，可以使用 `--insomnia` 或 `--bruno`：

```bash
python -m api2agent.cli generate \
  --insomnia tests/fixtures/insomnia/basic_export.json \
  --output api2agent-insomnia-output \
  --force

python -m api2agent.cli generate \
  --bruno tests/fixtures/bruno/basic_collection.json \
  --output api2agent-bruno-output \
  --force
```

这两个 adapter 会把 HTTP requests、folder tags、query/header parameters、JSON bodies、auth hints 和 generated runner calls 编译进同一套 capability package 格式。

## 12. 从 Workflow Endpoint 生成

如果已有 n8n、Zapier、Make 或自建 webhook 暴露了一个 HTTP endpoint，可以使用 `--workflow`：

```bash
python -m api2agent.cli generate \
  --workflow tests/fixtures/workflow/basic_manifest.json \
  --output api2agent-workflow-output \
  --force

python -m api2agent.cli inspect api2agent-workflow-output
python -m api2agent.cli diagnose api2agent-workflow-output
```

API2Agent 会把这个 endpoint 编译成一个 Agent-callable tool。它不会执行、持久化或编排 workflow steps。

## 13. 从 GraphQL Endpoint 生成

如果已有 GraphQL endpoint，并且希望把固定 query 或 mutation operation 暴露成 Agent-callable tools，可以使用 `--graphql`：

```bash
python -m api2agent.cli generate \
  --graphql tests/fixtures/graphql/basic_manifest.json \
  --output api2agent-graphql-output \
  --force

python -m api2agent.cli inspect api2agent-graphql-output
python -m api2agent.cli diagnose api2agent-graphql-output
```

Agent 只需要把 operation variables 作为 `body` 传入。生成的 runner 会在调用 GraphQL endpoint 前包装成 `query`、`operationName` 和 `variables`。

## 14. 收窄大型 API

大型 OpenAPI spec 通常会暴露太多 endpoints，不适合直接给 Agent 做 tool selection。生成前先过滤：

```bash
python -m api2agent.cli generate api.github.com.json \
  --include-tag repos \
  --include-path /repos \
  --include-operation listRepos \
  --max-tools 20 \
  --provider-region us-east \
  --output github-repos-agent \
  --force
```

过滤规则：

- 同一个 option 的多个值是 OR
- 不同 filter 类型之间是 AND
- `--max-tools` 在其他 filter 之后生效
- `--include-path` 支持精确路径、substring 或 glob pattern

## 15. 证明了什么

这个 release candidate 证明 API2Agent 可以：

- 解析 OpenAPI、curl、HAR、Postman Collection、Insomnia export、Bruno collection、workflow endpoint 和 GraphQL endpoint 描述
- 编译成中立的 capability model
- 生成 OpenAI-compatible tools
- 生成可运行的 OpenAI Responses API tool-calling 示例
- 生成本地 runner
- 生成 MCP stdio server
- 生成 docs、examples、diagnostics 和 test files
- 对安全的 read tools 做 smoke test
- 在生成包需要人工审查时提前给出 warning

本发布候选不包含：

- hosted SaaS
- marketplace 和 billing
- workflow runtime
- Hosted Control Plane
- production Data Plane deployment
- provider revenue share
