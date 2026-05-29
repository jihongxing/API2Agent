# API2Agent Dogfood 报告

## 1. 目标

本轮 dogfood 的目标不是证明所有 API 都能完美支持，而是用真实 API 暴露 Phase 2 最应该解决的问题。

验证路径：

```text
真实 OpenAPI / 真实 curl
  -> api2agent generate
  -> api2agent inspect
  -> api2agent test
```

## 2. 样本

| 样本 | 类型 | 目标 |
|------|------|------|
| Swagger Petstore | OpenAPI | 小型公开 OpenAPI |
| GitHub REST API | OpenAPI | 大型真实 OpenAPI |
| httpbin curl POST | curl | curl query/header/json body 推断 |
| GitHub rate_limit curl | curl | read endpoint + Bearer auth 场景 |

## 3. 结果摘要

| 样本 | Generate | Inspect | Test | 结论 |
|------|----------|---------|------|------|
| Swagger Petstore | 成功 | 成功 | 失败 | 相对 server URL 和 auth 判断需要改进 |
| GitHub REST API | 成功 | 成功 | 成功 | 大型 spec 可跑，但输出过大 |
| httpbin curl POST | 成功 | 成功 | 跳过 | 安全策略正确阻止 write smoke test |
| GitHub public curl | 成功 | 成功 | 成功 | curl read happy path 成功 |
| GitHub auth curl | 成功 | 成功 | 失败 | Bearer auth 识别成功，但 env/name 太泛 |

## 4. 详细观察

### 4.1 Swagger Petstore

输入：

```text
https://petstore3.swagger.io/api/v3/openapi.json
```

结果：

- `generate` 成功
- `inspect` 成功
- tools 和 schema 展示清楚
- `test` 失败

失败 1：

```text
missing_auth: SWAGGER_PETSTORE_OPEN_API_3_0_API_KEY
```

原因：

当前 parser 只要看到 security scheme，就把 auth 提升为 capability-level auth。但真实 OpenAPI 里，不是所有 endpoint 都需要同一种 auth。

失败 2：

给 dummy auth 后继续失败：

```text
Request URL is missing an 'http://' or 'https://' protocol.
```

原因：

Petstore 的 server URL 是相对路径：

```text
/api/v3
```

当前 runner 需要绝对 base URL。

### 4.2 GitHub REST API

输入：

```text
https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json
```

结果：

- `generate` 成功
- `inspect` 成功
- `test` 成功
- smoke test 调用 `GET /` 返回 200

观察：

- 大型 spec 可以生成。
- 生成耗时约 25 秒。
- inspect 输出巨大，不适合人读。
- 大量 tools 直接暴露给 Agent 不现实。

### 4.3 httpbin curl POST

输入：

```powershell
api2agent generate '--curl=curl https://httpbin.org/anything?verbose=true -H "X-Trace-Id: trace-123" --json "{\"name\":\"demo\",\"active\":true}"'
```

结果：

- `generate` 成功
- `inspect` 成功
- query/header/body 推断成功
- `test` 跳过

inspect 输出：

```text
- post_anything: POST /anything [write] required=body
  query: verbose string default=true
  header: X-Trace-Id string default=trace-123
  body: object {name:string, active:boolean} required
```

test 输出：

```text
No read-only endpoint was detected. Add a manual test before calling write/delete tools.
```

结论：

这是正确的默认安全策略。write endpoint 不应该自动 smoke test。

### 4.4 GitHub curl

公开 read endpoint：

```text
curl https://api.github.com/rate_limit
```

结果：

- `generate` 成功
- `test` 成功
- 返回 200

Bearer auth curl：

```text
curl https://api.github.com/rate_limit -H "Authorization: Bearer ghp_fake"
```

结果：

- Bearer auth 识别成功
- `inspect` 显示 `Auth: bearer via Authorization`
- `test` 因缺少 env 失败，这是正确行为

问题：

生成 capability name 是：

```text
api
```

env 是：

```text
API_TOKEN
```

原因：

curl parser 从 host 的第一个段推断名称，`api.github.com` 被推成 `api`，太泛。

## 5. Phase 2 优先级建议

### P0：Tool Filtering / Selection

GitHub REST API 证明大型 spec 可以生成，但不能把所有 endpoint 全部倾倒给 Agent。

建议：

- `--include-tag`
- `--include-path`
- `--include-operation`
- `--max-tools`
- inspect 默认 summary，不默认刷全部 tools

### P0：Endpoint-level Auth

Petstore 暴露了 capability-level auth 太粗。

建议：

- IR 中 tool 增加 auth override
- parser 解析 global/path/operation security
- smoke test 选择不需要 auth 的 read endpoint
- 只有 endpoint 需要 auth 时才要求 env

### P1：Base URL Override

相对 server URL 在真实 spec 中存在。

建议：

- `api2agent generate spec.json --base-url https://petstore3.swagger.io/api/v3`
- 对相对 server URL 给出明确错误
- 从 URL 输入下载 spec 时可以推断 origin

### P1：Write Tool Manual Test

curl POST 可以生成，但默认 smoke test 跳过。安全正确，但用户需要手动验证路径。

建议：

- `api2agent test --allow-write`
- README 生成 manual write test 示例
- 对 write/delete 明确提示风险

### P1：curl Naming

`api.github.com` -> `api` 太泛，影响 env 和 package 可读性。

建议：

- 对 `api.{domain}.com` 使用 `{domain}`
- 对 `{service}.com` 使用 `{service}`
- 支持 `--name` 并在 README 中强调

### P2：Large Spec Performance

GitHub spec 生成约 25 秒。

建议：

- profile parser/generator
- lazy schema formatting
- limit generation by selected tools
- avoid expensive full inspect output

## 6. 结论

MVP 主链路成立：

```text
OpenAPI/curl -> IR -> capability package -> smoke test / MCP server
```

但 Phase 2 不应该继续盲目加更多输入格式。

下一阶段应该优先提高真实 API 可用性：

1. tool filtering
2. endpoint-level auth
3. base URL override
4. manual write test
5. curl naming

