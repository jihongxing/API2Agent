# Failover Ledger Dogfood 报告

日期：2026-05-30

## 目标

验证 API2Agent 是否会把失败 provider attempt 记录进 usage ledger，并且能在同一个 routing decision 下 fallback 到第二个 provider。

这次 dogfood 验证的是 API2Agent reliability，不验证 marketplace。

## 场景

Capability：

- `public_ip_lookup`

Providers：

- `httpbin_500`
  - source: `https://httpbin.org/status/500`
  - expected result: HTTP 500
  - estimated cost: `0.003`
- `ipify`
  - source: `https://api.ipify.org?format=json`
  - output mapping: `ip <- $.ip`
  - estimated cost: `0.001`

Routing policy：

- strategy: `first`
- failover: `true`

执行路径：

```text
route selected httpbin_500
  -> httpbin_500 through proxy
  -> HTTP 500 usage event
  -> failover to ipify through proxy
  -> HTTP 200 usage event
  -> normalized output
  -> one routing_decision_id links both attempts
```

## 结果

最终通过 failover 成功。

```json
{
  "ok": true,
  "final_provider_id": "ipify",
  "normalized_body": {
    "ip": "108.174.61.76"
  }
}
```

Attempts：

```json
[
  {
    "provider_id": "httpbin_500",
    "ok": false,
    "status_code": 500,
    "error": {
      "type": "http_status",
      "message": "HTTP 500"
    }
  },
  {
    "provider_id": "ipify",
    "ok": true,
    "status_code": 200,
    "error": null
  }
]
```

Ledger rows：

```json
[
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "httpbin_500",
    "total_calls": 1,
    "successful_calls": 0,
    "failed_calls": 1,
    "success_rate": 0.0,
    "average_latency_ms": 2600.8213001769036,
    "estimated_cost": 0.003
  },
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "ipify",
    "total_calls": 1,
    "successful_calls": 1,
    "failed_calls": 0,
    "success_rate": 1.0,
    "average_latency_ms": 2380.0826999358833,
    "estimated_cost": 0.001
  }
]
```

Usage summary：

```json
{
  "project_id": "local",
  "total_calls": 2,
  "successful_calls": 1,
  "failed_calls": 1,
  "success_rate": 0.5,
  "average_latency_ms": 2490.4520000563934,
  "estimated_cost": 0.004,
  "error_counts": {
    "http_status": 1
  }
}
```

## 实现变化

成功 failover 的返回现在也会包含 `attempts` array，因此调用方可以在最终成功时仍然看到前面失败的 provider attempts。

## 产品结论

可靠性模型站得住：

- failed provider attempts 可见
- failed provider attempts 会进入 ledger
- successful fallback attempts 也进入同一个 ledger
- 两次 attempts 共享同一个 `routing_decision_id`
- provider 失败后，最终 capability output 仍然可以成功

这是 API2Agent reliability 和未来经济计量的正确地基。下一步应该把它升级成 policy：什么时候允许 failover，哪些失败类型可以 fallback。

