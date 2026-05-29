# Failover Policy Dogfood 报告

日期：2026-05-30

## 目标

用真实 HTTP provider failure 验证 Failover Policy v0。

这次 dogfood 验证的是 API2Agent reliability policy，不验证 marketplace。

## Policy

```json
{
  "enabled": true,
  "max_attempts": 2,
  "retry_on_status_codes": [500]
}
```

预期行为：

- HTTP 500 应该 fallback 到下一个 provider。
- HTTP 400 应该停止，不 fallback。

## 场景 A：可重试 HTTP 500

Providers：

- `httpbin_500`: `https://httpbin.org/status/500`
- `ipify`: `https://api.ipify.org?format=json`

结果：

```json
{
  "ok": true,
  "final_provider_id": "ipify",
  "attempts": [
    {
      "provider_id": "httpbin_500",
      "ok": false,
      "status_code": 500
    },
    {
      "provider_id": "ipify",
      "ok": true,
      "status_code": 200
    }
  ]
}
```

## 场景 B：不可重试 HTTP 400

Providers：

- `httpbin_400`: `https://httpbin.org/status/400`
- `ipify`: `https://api.ipify.org?format=json`

结果：

```json
{
  "ok": false,
  "final_provider_id": null,
  "attempts": [
    {
      "provider_id": "httpbin_400",
      "ok": false,
      "status_code": 400
    }
  ]
}
```

## Ledger

```json
[
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "httpbin_400",
    "total_calls": 1,
    "successful_calls": 0,
    "failed_calls": 1,
    "success_rate": 0.0,
    "average_latency_ms": 2516.4781999774277,
    "estimated_cost": 0.003
  },
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "httpbin_500",
    "total_calls": 1,
    "successful_calls": 0,
    "failed_calls": 1,
    "success_rate": 0.0,
    "average_latency_ms": 2881.919600069523,
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
    "average_latency_ms": 2071.823799982667,
    "estimated_cost": 0.001
  }
]
```

## 产品结论

Failover 必须由 policy 驱动，不能只是 enabled / disabled。

最小可用 policy 需要：

- enabled
- max_attempts
- retry_on_status_codes
- retry_on_error_types

当前实现已经足够支撑本地 API2Agent reliability dogfood。下一步加固是：让 policy 出现在 CLI output，并持久化到 routing decision metadata。

## 追加验证

Failover policy metadata 现在已经包含在 routing decision response 中，并持久化到了本地 routing decision ledger。

验证输出：

```json
{
  "routing_decision_failover_policy": {
    "enabled": true,
    "max_attempts": 2,
    "retry_on_error_types": [
      "http_error",
      "http_status",
      "proxy_error",
      "output_normalization"
    ],
    "retry_on_status_codes": [500]
  },
  "stored_failover_policy": {
    "enabled": true,
    "max_attempts": 2,
    "retry_on_error_types": [
      "http_error",
      "http_status",
      "proxy_error",
      "output_normalization"
    ],
    "retry_on_status_codes": [500]
  }
}
```

下一步加固是提供一个专门的 routing-decision inspection command。
