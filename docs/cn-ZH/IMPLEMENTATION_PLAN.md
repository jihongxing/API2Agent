# API2Agent 实施计划

## 1. 当前构建目标

当前仓库实现的是 Free Tooling Layer：

```text
OpenAPI / curl
  -> API2Agent IR
  -> filtered capability package
  -> generated runner
  -> generated smoke test
  -> generated MCP server
```

这证明本地可用性。下一个战略构建目标是通过 API2Agent Proxy 实现 controlled execution。

## 2. 当前仓库结构

```text
api2agent/
  cli.py
  filters.py
  ir/
    models.py
  parsers/
    openapi.py
    curl.py
  generators/
    package.py
    runner.py
    tools.py
    mcp.py
    readme.py
    smoke_test.py
  safety/
    classifier.py
tests/
  fixtures/
docs/
  en-US/
  cn-ZH/
```

## 3. 已完成 Tooling Milestones

- Project skeleton
- API2Agent IR
- OpenAPI parser
- curl parser
- safety classifier
- package generator
- runner generator
- smoke test generator
- MCP server generator
- MCP stdio integration test
- tool filtering / selection
- bilingual docs
- open-core license

## 4. 剩余 Tooling Reliability 工作

这些仍然有价值，但不再是战略终点：

1. Endpoint-level auth
2. Base URL override
3. Manual write test path
4. Better curl naming
5. Large spec performance

在 proxy 和 metrics 存在之前，不要继续扩很多新输入格式。

## 5. 下一阶段主线：Control Layer MVP

目标：

```text
generated package
  -> API2Agent Proxy
  -> third-party API
  -> usage event
```

### Step 1：Usage Event Schema

定义中立事件模型：

- project_id
- capability_id
- provider_id
- tool_id
- timestamp
- method
- path
- status_code
- success
- latency_ms
- estimated_cost
- error_type

完成条件：

- event model 可以序列化为 JSON
- tests 覆盖 success 和 failure events

### Step 2：Proxy Call Contract

定义：

```http
POST /v1/proxy/call
```

Request：

```json
{
  "capability_id": "github_repos",
  "tool_id": "list_repos",
  "provider_id": "github",
  "params": {}
}
```

完成条件：

- contract 被文档化
- runner 可以生成 direct mode 或 proxy mode

### Step 3：Local Proxy Prototype

先构建最小 local service。

建议 stack：

- FastAPI or simple ASGI app
- SQLite for usage events
- httpx for forwarding
- pytest for proxy tests

完成条件：

- proxy 可以 forward 一个 generated tool call
- proxy 可以记录 usage event
- proxy 返回 structured success/error result

### Step 4：Quota MVP

添加 project-level quota：

- max calls per project
- quota exceeded error
- usage count query

完成条件：

- proxy 在 quota 超额后阻止调用
- quota event 被清晰记录

### Step 5：Metrics Report

添加 CLI 或 endpoint report：

- total calls
- success rate
- average latency
- estimated cost
- error type counts

完成条件：

- 用户可以看到某个 API capability 是否可靠、是否昂贵

## 6. Capability Layer MVP

这一层从最小 machine-readable schema 开始。

定义：

- Capability Schema v0.1
- Provider Candidate model
- tool 到 capability 的 mapping
- metrics snapshot per candidate

完成条件：

- 两个 provider 可以映射到同一个 capability
- metrics 可以比较

## 7. Routing Layer MVP

Routing v0 支持简单策略：

- random
- lowest estimated cost
- highest observed success rate
- lowest average latency
- balanced score

完成条件：

- 一次 capability request 可以路由到两个 providers 中的一个
- routing decision 被记录
- failover 可以尝试第二个 provider

CLI：

```bash
api2agent route capability-registry.json \
  --capability-id image_generation \
  --strategy lowest_cost \
  --db api2agent-usage.sqlite
```

最小 provider registry：

```json
{
  "providers": [
    {
      "id": "provider_a",
      "capability_id": "image_generation",
      "provider_id": "a",
      "tool_id": "generate",
      "estimated_cost": 0.02
    }
  ]
}
```

## 8. Credential Orchestration MVP

Credential orchestration 在 billing 和 marketplace 之前。

定义：

- Credential Schema v0.1
- owner types：user、project、platform、provider
- sources：env、config、inline、none
- resolver order
- injection patch contract
- usage event `credential_reference`
- redaction rules

完成条件：

- 一个 authenticated API 可以使用 resolved local credential 调用
- raw secrets 不会存入 usage events
- exact replay 需要 credential 但无法 resolve 时会 warning
- ledger 可以保留 credential attribution，且不暴露 secrets

下一项工程任务：

```text
Credential Schema v0.1 + Local Resolver Design
```

## 9. Marketplace 是后面的结果

在以下条件成立前，不要做 marketplace UI：

- proxy works
- credential orchestration exists
- metrics exist
- capability abstraction exists
- routing works
- pricing metadata exists

Marketplace 应该是 routing plus economics 的结果，不是起点。
