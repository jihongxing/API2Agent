# E2E Core Loop 报告

日期：2026-05-30

## 目标

用一个真实世界 API 打通第一条 API2Agent end-to-end loop。

链路：

```text
Agent request
  -> API2Agent SDK
  -> static router
  -> provider adapter
  -> real API call
  -> normalized output
  -> routing decision
  -> usage event
  -> ledger row
```

## Capability

Capability：

- `weather.get`

SDK：

```python
from api2agent import call

result = call(
    "weather.get",
    {"city": "San Francisco"},
    agent_id="demo_agent",
)
```

Provider：

- `open_meteo`

## Adapter

已实现：

- `ProviderAdapter` protocol
- `AdapterResult`
- `CostEstimate`
- `OpenMeteoWeatherAdapter`

Adapter contract：

```python
class ProviderAdapter:
    def call(self, input) -> AdapterResult:
        ...

    def estimate_cost(self, input) -> CostEstimate:
        ...
```

## 真实 Dogfood 结果

Input：

```json
{
  "city": "San Francisco"
}
```

Normalized output：

```json
{
  "city": "San Francisco",
  "country": "United States",
  "latitude": 37.77493,
  "longitude": -122.41942,
  "time": "2026-05-29T19:30",
  "temperature_2m": 13.7,
  "temperature_unit": "°C",
  "wind_speed_10m": 12.0,
  "wind_speed_unit": "km/h",
  "weather_code": 3
}
```

Usage event：

```json
{
  "execution_mode": "direct",
  "capability_id": "weather.get",
  "provider_id": "open_meteo",
  "tool_id": "get_current_weather",
  "status_code": 200,
  "success": true,
  "estimated_cost": 0.0
}
```

Ledger row：

```json
{
  "project_id": "local",
  "capability_id": "weather.get",
  "provider_id": "open_meteo",
  "execution_mode": "direct",
  "total_calls": 1,
  "successful_calls": 1,
  "failed_calls": 0,
  "success_rate": 1.0,
  "estimated_cost": 0.0
}
```

## 证明了什么

API2Agent 现在有了真实 E2E core loop：

- 一个 Agent-facing SDK call
- 一个 hardcoded router
- 一个 provider adapter
- 一个真实世界 API
- 一个 normalized output
- 一个 usage event
- 一个 ledger row

这是继续增加 providers、智能 routing、hosted control 或 future discovery 前正确的地基。

## 当前限制

- 只有一个 capability
- 只有一个 provider
- static routing
- 仅 direct execution
- identity 只有 `project_id` 和 optional `agent_id`
- cost 是 provider-declared zero cost

## 下一步

为同一个 capability 增加第二个 provider，或增加第二个真实世界 capability，然后 benchmark：

- success rate
- p50/p95 latency
- estimated vs observed cost

