# Routing Ledger Dogfood 报告

日期：2026-05-30

## 目标

验证 API2Agent 能否把一个 semantic capability 通过 routing、proxy、usage tracking、routing-decision correlation、output normalization 和 local usage ledger 跑通。

这次 dogfood 验证的是 API2Agent 本身，不验证 marketplace。

## 场景

Capability：

- `public_ip_lookup`

Providers：

- `ipify`
  - source: `https://api.ipify.org?format=json`
  - output mapping: `ip <- $.ip`
  - estimated cost: `0.001`
- `httpbin`
  - source: `https://httpbin.org/ip`
  - output mapping: `ip <- $.origin`
  - estimated cost: `0.002`

执行路径：

```text
execute_capability
  -> route provider
  -> generated runner
  -> local API2Agent Proxy
  -> real provider API
  -> usage event with routing_decision_id
  -> normalized capability output
  -> local usage ledger
```

## 结果

两个真实 providers 都通过 proxy 成功。

Normalized outputs：

```json
{
  "ipify": {
    "ip": "108.174.61.76"
  },
  "httpbin": {
    "ip": "108.174.61.76"
  }
}
```

Ledger rows：

```json
[
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "httpbin",
    "total_calls": 1,
    "successful_calls": 1,
    "failed_calls": 0,
    "success_rate": 1.0,
    "average_latency_ms": 5657.604599837214,
    "estimated_cost": 0.002
  },
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "ipify",
    "total_calls": 1,
    "successful_calls": 1,
    "failed_calls": 0,
    "success_rate": 1.0,
    "average_latency_ms": 2206.9931000005454,
    "estimated_cost": 0.001
  }
]
```

Usage summary：

```json
{
  "project_id": "local",
  "total_calls": 2,
  "successful_calls": 2,
  "failed_calls": 0,
  "success_rate": 1.0,
  "average_latency_ms": 3932.2988499188796,
  "estimated_cost": 0.003,
  "error_counts": {}
}
```

## 发现的问题

### 1. Semantic capability ID 没有传给 proxy

Generated runners 原来会把 package name 作为 `capability_id` 传给 proxy。Routing execution 需要的是 semantic capability ID，比如 `public_ip_lookup`。

修复：

- `execute_capability` 现在会设置 `API2AGENT_CAPABILITY_ID`。
- generated runners 优先使用 `API2AGENT_CAPABILITY_ID`，没有时再 fallback 到 package name。

### 2. curl 参数 default 没有被 generated runner 使用

ipify curl package 保存了 `format=json` 这个参数 default，但 runner 在 params 为空时没有把 default 带上。结果 ipify 返回 plain text，导致 output normalization 失败。

修复：

- generated runners 现在会在没有显式 params 时，为 query、header 和 path 参数应用 schema default。

## 产品结论

当前模型站得住：

- routing decision 可以持久化
- proxy usage event 可以通过 `routing_decision_id` 关联
- provider 级别的 success、latency 和 estimated cost 可以进入 ledger
- 不同 provider 的返回结构可以 normalize 成同一个 capability output

经济层应该继续先做 measurement layer。Payment、settlement 和 marketplace mechanics 仍然不属于当前范围。

