# 真实 Two-Provider Dogfood 报告

## 1. 目标

验证当前 Capability / Provider / Metrics / Routing 模型能否支撑两个真实 API 映射到同一个 capability。

Capability：

```text
public_ip_lookup
```

Providers：

- ipify：`GET https://api.ipify.org?format=json`
- httpbin：`GET https://httpbin.org/ip`

## 2. 设置

两个 generated packages 使用同一个 capability name：

```text
public_ip_lookup
```

Provider identity 通过环境变量设置：

```bash
API2AGENT_PROVIDER_ID=ipify
API2AGENT_PROVIDER_ID=httpbin
```

两个 providers 都通过 API2Agent Proxy 调用 3 次。

## 3. 原始 Provider 输出

ipify：

```json
{
  "ip": "108.174.61.76"
}
```

httpbin：

```json
{
  "origin": "108.174.61.76"
}
```

它们 fulfill 同一个 intent，但返回结构不同。

## 4. Metrics

| Provider | Total Calls | Success Rate | Avg Latency | Estimated Cost / Call |
|---|---:|---:|---:|---:|
| `ipify` | 3 | 100% | 2445 ms | 0.001 |
| `httpbin` | 3 | 100% | 3007 ms | 0.002 |

## 5. Routing 结果

| Routing Policy | Selected Provider | 原因 |
|---|---|---|
| `lowest_cost` | `ipify` | cost 更低 |
| `lowest_latency` | `ipify` | latency 更低 |
| `reliability_first` | `ipify` | 两者都是 100% success，由 latency/cost 打破平局 |
| `cost_first` | `ipify` | cost 更低 |

## 6. 验证了什么

- 两个真实 API 可以映射到同一个 capability。
- Proxy usage events 可以聚合到同一个 `capability_id`，同时保留不同 `provider_id`。
- Routing 可以使用真实 observed metrics 选择 provider。
- Routing decision events 包含 selected provider、ranked providers、strategy/preset 和 metrics。

## 7. 暴露了什么

在 routing execution loop 前，必须先有 output normalization。

目标标准化输出：

```json
{
  "ip": "108.174.61.76"
}
```

Provider-specific mappings：

```json
{
  "ipify": {
    "ip": "$.ip"
  },
  "httpbin": {
    "ip": "$.origin"
  }
}
```

没有这层 metadata，routing 可以选择 provider，但无法保证 Agent 拿到稳定的 capability output。

## 8. 结论

当前 Capability / Provider / Metrics / Routing 模型通过了第一轮真实 two-provider dogfood。

符合 roadmap 的后续工作是 Capability Schema v0.2：

- output normalization metadata
- provider-specific output mapping
- normalized result contract

在 normalization metadata 存在前，不要实现 routing execution loop。

状态：

- v0.2 output normalization metadata 已定义在 `docs/cn-ZH/CAPABILITY_SCHEMA.md`。
