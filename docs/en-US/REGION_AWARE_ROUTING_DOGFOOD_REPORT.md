# Region-Aware Routing Dogfood Report

Date: 2026-05-30

## Purpose

Validate that API2Agent can choose a provider for the same capability using client-region affinity instead of only global latency, cost, or success rate.

## Scenario

Capability:

- `weather.current.get`

Providers:

- `weather_us`
  - `regions`: `["us-east"]`
  - `geo_affinity`: `regional`
- `weather_cn`
  - `regions`: `["cn"]`
  - `geo_affinity`: `regional`

Routing policy:

- strategy: `region_aware_latency`
- client region: `cn`

Expected outcome:

- select `weather_cn`
- persist `client_region=cn` in the routing decision

## Results

- `region_aware_latency` ranked the provider with matching `regions` first.
- matching client-region latency metrics are preferred when available.
- aggregate latency metrics are used as fallback when region-specific metrics are unavailable.
- `api2agent route --client-region cn --strategy region_aware_latency --json` returned `weather_cn`.
- the stored routing decision preserved `client_region=cn`.
- `api2agent call --client-region` now carries the same policy into execution decisions.

## Tests

```text
pytest tests/test_capability_routing.py tests/test_control_layer.py
36 passed

pytest
140 passed
```

## Product Learning

This validates the first practical step toward location-aware execution. API2Agent can now turn region metadata and regional latency observations into an auditable provider decision while keeping the strategy simple enough for v0.1-alpha.

The reusable benchmark helper is `run_region_aware_routing_benchmark` in `api2agent/benchmark.py`.

The next dogfood should use a same-capability registry with real provider calls from different regions or simulated regional latency snapshots, then compare selected provider, ranked providers, latency, cost, and success outcome as a decision dataset record.
