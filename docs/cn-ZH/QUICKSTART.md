# API2Agent Quickstart

这份 quickstart 证明当前可发布候选版本的主路径：

```text
OpenAPI 3.x / curl
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
239 passed
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

## 9. 收窄大型 API

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

## 10. 证明了什么

这个 release candidate 证明 API2Agent 可以：

- 解析 OpenAPI 和 curl API 描述
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
