# Location-Aware Routing Strategy

## Why This Matters

API2Agent should not only answer:

- Which provider is more reliable?
- Which provider is cheaper?

It must also answer:

- Which provider is faster for this Agent from this location?

APIs are everywhere. Agents running in China, the US, Europe, or other regions will see very different network paths to the same provider. A global average latency can hide the provider that is actually best for one region.

## Strategic Priority Update

API2Agent should increase the product weight of two goals:

1. Own the most real execution data.
2. Keep API onboarding cost as low as possible.

These are the two sides of the flywheel:

```text
lowest onboarding cost
  -> more APIs/providers connected
  -> more real calls
  -> richer decision dataset
  -> better routing
  -> higher success / lower cost / lower latency
  -> stronger developer pull
  -> more APIs/providers connected
```

## Latency Model

Do not model speed as a single number only.

Total latency should be treated as:

```text
total_latency =
  network_rtt
  + provider_processing_latency
  + api2agent_overhead
```

v0.1 can continue storing `latency_ms`, but the next schema iteration should add room for this breakdown.

## Region Model

Minimum region vocabulary:

- `us-east`
- `us-west`
- `eu-west`
- `ap-east`
- `cn`
- `unknown`

Future usage events should include:

```json
{
  "client_region": "cn",
  "api2agent_region": "ap-east",
  "provider_region": "us-east",
  "latency_total_ms": 320,
  "latency_network_ms": 200,
  "latency_provider_ms": 100,
  "latency_overhead_ms": 20
}
```

## Provider Metadata

Provider registry entries should eventually include:

```json
{
  "provider_id": "example_cn",
  "regions": ["cn"],
  "geo_affinity": "regional"
}
```

Stable `geo_affinity` values:

- `global`
- `regional`
- `cn-only`
- `unknown`

## Routing Implication

Latency should become region-aware:

```text
latency = f(client_region, provider_region)
```

Balanced routing should evolve toward a multidimensional score:

```text
score =
  success_weight * success_score
  + cost_weight * cost_score
  + latency_weight * region_aware_latency_score
```

The current `lowest_latency` strategy can remain as a local aggregate strategy. The next version should introduce a region-aware latency strategy.

## Decision Dataset

Usage logs are not enough.

The strategic asset is a decision dataset:

```json
{
  "request_id": "req_123",
  "capability_id": "weather.current.get",
  "client_region": "cn",
  "candidate_providers": ["provider_us", "provider_cn"],
  "selected_provider": "provider_cn",
  "routing_strategy": "balanced",
  "success": true,
  "latency_total_ms": 40,
  "estimated_cost": 0.001
}
```

This dataset is what future routing learning, marketplace ranking, and active optimization depend on.

## Active Probing

Historical latency can go stale.

Future API2Agent should support active probing:

- scheduled health checks
- regional latency probes
- provider availability checks
- stale metric detection

This should not be built before the local schema and routing contract are clear.

## Product Direction

The long-term target is not only "API to Agent."

The stronger target is:

> A global API routing network for Agents.

Near-term implementation should stay focused:

1. Add schema fields for region-aware usage.
2. Extend provider metadata with region information.
3. Add a region-aware routing strategy.
4. Dogfood with same capability, different provider regions, different outcomes.
