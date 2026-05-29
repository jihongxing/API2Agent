# API2Agent Benchmark v0.1

日期：2026-05-30

## 目标

用一个 capability 的两个真实 providers 跑第一份 SDK E2E benchmark。

Capability：

- `weather.get`

Providers：

- `open_meteo`
- `wttr_in`

Input：

```json
{
  "city": "San Francisco"
}
```

## 方法

两个 providers 都通过以下 SDK 调用：

```python
from api2agent import call

call("weather.get", {"city": "San Francisco"}, provider_id="open_meteo")
call("weather.get", {"city": "San Francisco"}, provider_id="wttr_in")
```

两次调用都会写入：

- routing decision
- usage event
- ledger row

重复 benchmark 使用：

```python
from api2agent.benchmark import run_weather_benchmark

run_weather_benchmark(
    city="San Francisco",
    iterations=3,
    db=".dogfood/weather-benchmark-repeat.sqlite",
)
```

benchmark 写入 metrics 后，再对同一个 database 执行一次不指定 `provider_id` 的默认 SDK 调用，用来验证 provider selection 是否真的被 observed metrics 影响。

## 结果

| Provider | Calls | Success Rate | p50 Latency | p95 Latency | Estimated Cost | Observed Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `open_meteo` | 3 | 100% | 3368.97 ms | 5958.40 ms | 0.0 | 0.0 |
| `wttr_in` | 3 | 100% | 2161.30 ms | 3307.59 ms | 0.0 | 0.0 |

后续默认 SDK 调用选择了：

```json
{
  "provider_id": "wttr_in",
  "ranked_provider_ids": ["wttr_in", "open_meteo"],
  "ok": true
}
```

benchmark 加默认调用后的本地 ledger summary：

| Provider | Execution Mode | Calls | Success Rate | Average Latency |
| --- | --- | ---: | ---: | ---: |
| `open_meteo` | `direct` | 3 | 100% | 4246.34 ms |
| `wttr_in` | `direct` | 4 | 100% | 2303.71 ms |

## 证明了什么

API2Agent 现在可以在同一个 capability 下，用真实 execution data 比较两个 providers。

SDK 也已经能在下一次调用中使用这些数据。在同一个 local usage store 内，默认 routing 会按最低 observed latency 排序，并选择 `wttr_in`。

这是未来 routing data flywheel 的第一种可见形态：

```text
call
  -> usage event
  -> ledger row
  -> provider metrics
  -> next routing decision
```

## 当前限制

- 每个 provider 只有三次 benchmark 调用
- 没有 observed paid cost
- routing 现在只用简单 observed average latency，还没有使用 p50/p95 或 weighted policy
- 还没有 identity 和 hosted control plane

## 下一步

继续加固 SDK core loop：

- 把 benchmark 和 failover examples 补进 developer docs
- 在 protocol docs 中定义 SDK-facing error 和 retry policy defaults
- 保持 benchmark data 本地、透明
