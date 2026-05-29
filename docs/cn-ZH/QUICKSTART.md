# API2Agent Quickstart

这份 quickstart 复现 v0.1-alpha loop：

```text
one capability
  -> two providers
  -> benchmark comparison
  -> failover
  -> usage ledger
```

当前 alpha capability：

- legacy ID：`weather.get`
- 目标命名规则：`weather.current.get`

`weather.get` 会为了兼容暂时保留，alpha 命名规则会逐步引入。

## 1. 安装

```bash
python -m pip install -e ".[dev]"
pytest
```

期望结果：

```text
132 passed
```

## 2. 第一次 SDK 调用

```python
from api2agent import call

result = call(
    "weather.get",
    {"city": "San Francisco"},
    agent_id="quickstart_agent",
    db=".dogfood/quickstart.sqlite",
)

print(result["ok"])
print(result["provider_id"])
print(result["output"])
```

这会记录：

- routing decision
- usage event
- ledger row

## 3. Benchmark 两个 Providers

```python
from api2agent.benchmark import run_weather_benchmark

result = run_weather_benchmark(
    city="San Francisco",
    iterations=3,
    db=".dogfood/quickstart-benchmark.sqlite",
)

print(result)
```

这会比较：

- `open_meteo`
- `wttr_in`

Metrics 包括：

- total calls
- success rate
- p50 latency
- p95 latency
- estimated vs observed cost

当 metrics 存在后，默认 SDK 调用会按本地 observed latency 排序：

```python
from api2agent import call

result = call(
    "weather.get",
    {"city": "San Francisco"},
    db=".dogfood/quickstart-benchmark.sqlite",
)

print(result["provider_id"])
print(result["routing_decision"]["ranked_provider_ids"])
```

## 4. Failover Demo

这个 demo 会强制 primary provider 失败，然后 fallback 到真实 `wttr_in` provider。

```python
from api2agent import sdk
from api2agent.adapters.models import AdapterResult, CostEstimate


class ControlledFailingWeatherAdapter:
    capability_id = "weather.get"
    provider_id = "open_meteo"
    tool_id = "get_current_weather"

    def call(self, input):
        return AdapterResult(
            ok=False,
            capability_id=self.capability_id,
            provider_id=self.provider_id,
            status_code=500,
            latency_ms=12.0,
            cost=CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared"),
            error_type="PROVIDER_ERROR",
            error_message="controlled quickstart failure",
        )

    def estimate_cost(self, input):
        return CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared")


sdk.OpenMeteoWeatherAdapter = ControlledFailingWeatherAdapter

result = sdk.call(
    "weather.get",
    {"city": "San Francisco"},
    strategy="first",
    failover=True,
    max_attempts=2,
    agent_id="quickstart_failover_agent",
    db=".dogfood/quickstart-failover.sqlite",
)

print(result["ok"])
print(result["provider_id"])
print(result["attempts"])
```

期望结果：

- 第一次 attempt：`open_meteo`，失败，`500`
- 第二次 attempt：`wttr_in`，成功，`200`

## 5. Shadow Demo

Shadow mode 会额外执行 providers 来采集 benchmark data，但不改变主结果：

```python
from api2agent import call

result = call(
    "weather.get",
    {"city": "San Francisco"},
    strategy="first",
    shadow=True,
    db=".dogfood/quickstart-shadow.sqlite",
)

print(result["provider_id"])
print(result["shadow_attempts"])
```

期望结果：

- main result provider：`open_meteo`
- shadow provider：`wttr_in`
- ledger 同时包含 `direct` 和 `shadow` execution modes

Shadow metrics 默认会进入 routing aggregates。CLI routing path 可以用以下参数排除：

```bash
--exclude-shadow-metrics
```

## 6. Inspect Ledger

如果已经安装 `api2agent` console script：

```bash
api2agent ledger --db .dogfood/quickstart-failover.sqlite --capability-id weather.get --group-by-mode --json
```

更通用的方式：

```bash
python -m api2agent.cli ledger --db .dogfood/quickstart-failover.sqlite --capability-id weather.get --group-by-mode --json
```

期望 ledger shape：

- 一条失败的 `open_meteo` row
- 一条成功的 `wttr_in` row
- 两条都是 `direct` execution mode

## 7. Replay Preflight

`replay` 默认是 preflight 和 audit view。加上 `--execute` 后，可以重新执行 supported SDK 或 no-credential HTTP events。

```bash
python -m api2agent.cli replay <usage_event_id> --db .dogfood/quickstart-failover.sqlite --json
```

当前期望结果：

- 返回 usage event
- 返回 routing decision
- 列出 exact replay 缺失字段

当 `replayable` 为 `true` 时，可以执行 replay：

```bash
python -m api2agent.cli replay <usage_event_id> --db .dogfood/quickstart-failover.sqlite --execute --json
```

也可以把 replay execution 记录进 ledger，但不影响 routing metrics：

```bash
python -m api2agent.cli replay <usage_event_id> --db .dogfood/quickstart-failover.sqlite --execute --record --json
```

## 8. Golden Trace Marker

把 known-good usage event 标记为 golden trace：

```bash
python -m api2agent.cli golden <usage_event_id> --db .dogfood/quickstart-failover.sqlite --json
```

列出 golden traces，并把 ledger 过滤到 golden baselines：

```bash
python -m api2agent.cli golden --list --db .dogfood/quickstart-failover.sqlite --capability-id weather.get --json
python -m api2agent.cli ledger --db .dogfood/quickstart-failover.sqlite --golden-only --json
```

Golden traces 是 replay、benchmark、scoring 和 regression tests 的基准。

## 9. 生成本地 Capability Package

```bash
api2agent generate examples/openapi/basic.yaml --force
api2agent inspect api2agent-output
api2agent test api2agent-output
```

更通用的方式：

```bash
python -m api2agent.cli generate examples/openapi/basic.yaml --force
python -m api2agent.cli inspect api2agent-output
python -m api2agent.cli test api2agent-output
```

当 generated packages 被注册为 providers 后，也支持本地 reliability loop：

```bash
python -m api2agent.cli call capability-registry.json \
  --capability-id public_ip_lookup \
  --shadow \
  --json

python -m api2agent.cli replay <generated_package_usage_event_id> \
  --db api2agent-usage.sqlite \
  --execute \
  --json
```

这证明 compiler path 和 SDK execution loop 可以同时工作，包括 shadow observations 和 local package replay。

## 10. 证明了什么

API2Agent v0.1-alpha 证明：

- Agent 可以调用 capability，而不是 raw API
- 多个 providers 可以在同一个 capability 下比较
- provider 失败可以被记录，并通过 failover 恢复
- shadow providers 可以在不改变主结果的情况下采集 benchmark data
- 每个 attempt 都可以通过 ledger 审计
- 失败 attempt 可以通过 replay preflight 检查
- generated package attempts 可以本地 shadow 和 replay
- known-good attempts 可以被标记、列出，并作为 golden traces 过滤

Marketplace、hosted SaaS 和 payment 都刻意不在当前范围内。
