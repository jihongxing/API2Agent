# API2Agent Control Layer Dogfood 报告

## 1. 目标

本轮 dogfood 验证 roadmap 的 Phase 2：

```text
generated runner
  -> API2Agent Proxy
  -> third-party API
  -> usage event / metrics / quota
```

目标不是 marketplace routing。目标是验证 generated packages 能否经过 API2Agent 控制点执行，并产生有用的调用数据。

## 2. 设置

Local proxy：

```bash
api2agent proxy --db .dogfood/usage.sqlite --port 8765 --quota 3
```

Generated runners 使用 proxy mode：

```bash
API2AGENT_PROXY_URL=http://127.0.0.1:8765
API2AGENT_PROJECT_ID=phase2-dogfood
API2AGENT_ESTIMATED_COST=0.001
```

## 3. 样本

| 样本 | 输入 | Tool | 预期 |
|---|---|---|---|
| JSONPlaceholder | `curl https://jsonplaceholder.typicode.com/posts/1` | `get_posts_1` | public read success |
| GitHub | `curl https://api.github.com/rate_limit` | `get_rate_limit` | public read success |
| httpbin | `curl https://httpbin.org/get?source=api2agent` | `get_get` | query param forwarded |
| JSONPlaceholder quota check | repeat first call | `get_posts_1` | blocked by quota |

## 4. 结果

| 样本 | Proxy Result | Status | 备注 |
|---|---:|---:|---|
| JSONPlaceholder | success | 200 | body returned through proxy |
| GitHub | success | 200 | rate limit body returned through proxy |
| httpbin | success | 200 | query param preserved |
| JSONPlaceholder quota check | blocked | quota exceeded | proxy blocked before forwarding |

Usage summary：

```json
{
  "project_id": "phase2-dogfood",
  "total_calls": 4,
  "successful_calls": 3,
  "failed_calls": 1,
  "success_rate": 0.75,
  "average_latency_ms": 2772.82,
  "estimated_cost": 0.003,
  "error_counts": {
    "quota_exceeded": 1
  }
}
```

## 5. 观察

### 有效的部分

- Generated runners 可以通过环境变量切换到 proxy mode。
- Proxy 可以 forward 真实第三方 API 请求。
- Successful 和 blocked calls 都会记录 usage events。
- Query parameters 在 runner -> proxy -> API 路径中被保留。
- 第 4 次调用被 quota 在 forward 前阻断。
- Usage summary 已经能暴露 success rate、latency、cost estimate 和 error counts。

### 仍然薄弱的部分

- 当前 proxy 接收 generated runner 构造好的 HTTP request payload。作为 local MVP 可以接受，但 hosted mode 应该把 credentials 移到 vault。
- Cost 通过 `API2AGENT_ESTIMATED_COST` 传入，还没有绑定 provider pricing metadata。
- Quota 只是 project-level call count，不是 capability/provider 维度。
- Usage events 和 routing decisions 还不能关联，因为 routing execution loop 未实现。
- 还没有 hosted multi-project isolation。

## 6. 结论

Phase 2 local Control Layer MVP 成立。

不要跳到 marketplace。

下一步符合 roadmap 的工作应该是：

1. 用至少一个 authenticated API dogfood proxy mode。
2. 改进 provider/capability metadata，让 cost 不再依赖 env var。
3. 在实现 routing execution loop 前，先定义 routing decision event。
4. Hosted proxy 放到后续 phase，等 local proxy semantics 稳定后再做。

## 7. Authenticated API 补充验证

新增样本：

```text
curl https://httpbin.org/bearer -H "Authorization: Bearer dogfood-token"
```

Generated package：

```text
capability: httpbin_bearer
tool: get_bearer
auth env: HTTPBIN_BEARER_TOKEN
```

Proxy mode 环境：

```bash
API2AGENT_PROXY_URL=http://127.0.0.1:8765
API2AGENT_PROJECT_ID=auth-dogfood
API2AGENT_ESTIMATED_COST=0.002
HTTPBIN_BEARER_TOKEN=dogfood-token
```

结果：

```json
{
  "ok": true,
  "proxied": true,
  "status_code": 200,
  "body": {
    "authenticated": true,
    "token": "dogfood-token"
  }
}
```

Usage summary：

```json
{
  "project_id": "auth-dogfood",
  "total_calls": 1,
  "successful_calls": 1,
  "failed_calls": 0,
  "success_rate": 1.0,
  "average_latency_ms": 2548.44,
  "estimated_cost": 0.002,
  "error_counts": {}
}
```

缺少 auth 时的行为：

```json
{
  "ok": false,
  "error": {
    "type": "missing_auth",
    "env": "HTTPBIN_BEARER_TOKEN"
  }
}
```

观察：

- Bearer auth 可以通过 generated runner -> proxy -> third-party API。
- 缺少 auth 时在 proxy forwarding 前失败，所以不会调用第三方 API，也不会记录 usage event。
- 对 MVP 来说这是安全行为，但未来 hosted mode 可能需要单独记录 local preflight failures。
