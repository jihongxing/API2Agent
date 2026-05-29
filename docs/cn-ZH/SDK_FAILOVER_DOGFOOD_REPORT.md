# SDK Failover Dogfood 报告

日期：2026-05-30

## 目标

验证 hand-written SDK core loop 是否可以从失败 provider attempt fail over 到 fallback provider，同时把两个 attempts 都记录在同一个 routing decision 下面。

Capability：

- `weather.get`

Primary provider：

- `open_meteo`

Fallback provider：

- `wttr_in`

## 方法

这次 dogfood 对 `open_meteo` 使用 controlled failing adapter，返回：

```json
{
  "ok": false,
  "status_code": 500,
  "error_type": "PROVIDER_ERROR"
}
```

fallback provider 使用真实 `wttr_in` adapter，并调用 live API。

SDK 调用：

```python
from api2agent import sdk

result = sdk.call(
    "weather.get",
    {"city": "San Francisco"},
    strategy="first",
    failover=True,
    max_attempts=2,
    db=".dogfood/sdk-failover-real-fallback.sqlite",
)
```

## 结果

SDK 通过 fallback provider 返回成功：

```json
{
  "ok": true,
  "provider_id": "wttr_in",
  "attempts": [
    {
      "provider_id": "open_meteo",
      "ok": false,
      "status_code": 500,
      "error_type": "PROVIDER_ERROR"
    },
    {
      "provider_id": "wttr_in",
      "ok": true,
      "status_code": 200,
      "error_type": null
    }
  ]
}
```

Ledger rows：

| Provider | Execution Mode | Calls | Success | Failure | Average Latency |
| --- | --- | ---: | ---: | ---: | ---: |
| `open_meteo` | `direct` | 1 | 0 | 1 | 12.00 ms |
| `wttr_in` | `direct` | 1 | 1 | 0 | 1894.06 ms |

routing decision 存储了：

- `strategy`: `first`
- `selected_provider_id`: `open_meteo`
- `ranked_provider_ids`: `["open_meteo", "wttr_in"]`
- `failover_policy.enabled`: `true`
- `failover_policy.max_attempts`: `2`

## 证明了什么

SDK path 现在具备和 CLI execution path 一样的可靠性形态：

```text
route
  -> primary attempt
  -> usage event
  -> failover decision
  -> fallback attempt
  -> usage event
  -> ledger
```

失败 provider 不会从 metrics 中消失，而是进入 observability 和 routing feedback loop。

## 当前限制

- primary failure 是 controlled failure，不是真实 provider outage
- fallback provider 是真实 live API
- 还没有 hosted identity、quota 或 credential vault
