# Location-Aware Schema Dogfood Report

Date: 2026-05-30

## Purpose

Validate that API2Agent can persist region-aware usage data and represent provider region metadata without changing current routing behavior.

## Implemented Contract

Usage events now support:

- `client_region`
- `api2agent_region`
- `provider_region`
- `latency_total_ms`
- `latency_network_ms`
- `latency_provider_ms`
- `latency_overhead_ms`

Provider candidates now support:

- `regions`
- `geo_affinity`

Decision dataset contract:

- `DecisionDatasetRecord`

## Results

- usage store persisted and loaded region fields
- proxy calls recorded region fields from proxy payloads
- provider candidates accepted `regions` and `geo_affinity`
- decision dataset records can represent candidates, selected provider, region, latency, cost, and outcome
- existing routing behavior remained unchanged

## Tests

```text
pytest tests/test_control_layer.py tests/test_capability_routing.py
33 passed
```

## Product Learning

This is the correct first step before region-aware routing. API2Agent can now collect the fields required for location-aware execution without prematurely changing provider selection.
