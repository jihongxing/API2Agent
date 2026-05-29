# E2E Core Loop Report

Date: May 30, 2026

## Goal

Build the first real end-to-end API2Agent loop with one real-world API.

The loop:

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

Capability:

- `weather.get`

SDK:

```python
from api2agent import call

result = call(
    "weather.get",
    {"city": "San Francisco"},
    agent_id="demo_agent",
)
```

Provider:

- `open_meteo`

## Adapter

Implemented:

- `ProviderAdapter` protocol
- `AdapterResult`
- `CostEstimate`
- `OpenMeteoWeatherAdapter`

Adapter contract:

```python
class ProviderAdapter:
    def call(self, input) -> AdapterResult:
        ...

    def estimate_cost(self, input) -> CostEstimate:
        ...
```

## Real Dogfood Result

Input:

```json
{
  "city": "San Francisco"
}
```

Normalized output:

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

Usage event:

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

Ledger row:

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

## What This Proves

API2Agent now has a real E2E core loop:

- one Agent-facing SDK call
- one hardcoded router
- one provider adapter
- one real-world API
- one normalized output
- one usage event
- one ledger row

This is the correct foundation before adding more providers, smarter routing, hosted control, or marketplace-like discovery.

## Current Limitations

- only one capability
- only one provider
- static routing
- direct execution only
- no identity beyond `project_id` and optional `agent_id`
- cost is provider-declared zero cost

## Next Step

Add one more provider for the same capability or one more real-world capability, then benchmark:

- success rate
- p50/p95 latency
- estimated vs observed cost

