# Shadow Mode Dogfood 报告

日期：2026-05-30

## 目标

验证 API2Agent 能否在不改变主 SDK 结果的情况下，额外用 `shadow` mode 执行另一个 provider。

Capability：

- `weather.get`

Main provider：

- `open_meteo`

Shadow provider：

- `wttr_in`

## 方法

SDK 调用：

```python
from api2agent import call

result = call(
    "weather.get",
    {"city": "San Francisco"},
    strategy="first",
    shadow=True,
    db=".dogfood/shadow-weather.sqlite",
)
```

## 结果

主结果：

```json
{
  "ok": true,
  "provider_id": "open_meteo"
}
```

Shadow attempt：

```json
{
  "provider_id": "wttr_in",
  "ok": true,
  "status_code": 200,
  "latency_ms": 1786.19
}
```

Ledger rows：

| Provider | Execution Mode | Calls | Success Rate | Average Latency |
| --- | --- | ---: | ---: | ---: |
| `open_meteo` | `direct` | 1 | 100% | 3342.38 ms |
| `wttr_in` | `shadow` | 1 | 100% | 1786.19 ms |

## 证明了什么

API2Agent 可以在不改变用户可见结果的情况下采集 provider comparison data。

这是 benchmark data path 的第一版实现：

```text
main provider result
  -> returned to caller
shadow provider result
  -> recorded as metrics
  -> available for future routing
```

## 当前限制

- 先在 SDK path 实现
- generated package CLI execution 还不支持
- shadow events 当前会进入 aggregate metrics
