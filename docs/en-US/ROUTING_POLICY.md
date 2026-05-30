# Routing Policy v0

## 1. Purpose

Routing Policy v0 defines how API2Agent selects a provider candidate for a capability.

This phase only selects and ranks providers. It does not execute the selected provider.

## 2. Routing Decision Event

Every routing selection should be representable as a routing decision event:

```json
{
  "id": "decision_123",
  "capability_id": "image_generation",
  "strategy": "balanced",
  "preset": "reliability_first",
  "client_region": "cn",
  "selected_provider_id": "provider_a",
  "ranked_provider_ids": ["provider_a", "provider_b"],
  "metrics": [],
  "created_at": "2026-05-30T00:00:00Z"
}
```

This event is separate from a usage event.

Later, routing execution should correlate:

```text
routing decision event -> usage event
```

## 3. Strategies

Routing v0 supports:

- `first`
- `random`
- `lowest_cost`
- `lowest_latency`
- `region_aware_latency`
- `highest_success_rate`
- `balanced`

`region_aware_latency` v0 uses `client_region`, provider `regions`, and `geo_affinity`.

Ranking order:

1. providers whose `regions` contain `client_region`
2. providers with `geo_affinity=global`
3. providers with `geo_affinity=unknown`
4. other providers

Within the same region rank, the strategy uses matching client-region latency metrics when available, then aggregate latency metrics, then no-metric fallback.

CLI:

```bash
api2agent route capability-registry.json \
  --capability-id weather.current.get \
  --strategy region_aware_latency \
  --client-region cn \
  --db api2agent-usage.sqlite
```

## 4. Policy Presets

Presets are named weight configurations on top of `balanced`.

| Preset | Success Rate | Latency | Cost | Intent |
|---|---:|---:|---:|---|
| `balanced` | 0.5 | 0.3 | 0.2 | general default |
| `reliability_first` | 0.8 | 0.1 | 0.1 | prefer completion |
| `cost_first` | 0.1 | 0.2 | 0.7 | prefer low cost |
| `latency_first` | 0.1 | 0.7 | 0.2 | prefer speed |

CLI:

```bash
api2agent route capability-registry.json \
  --capability-id image_generation \
  --preset reliability_first \
  --db api2agent-usage.sqlite
```

## 5. Current Limitations

- No quality evaluation beyond success/cost/latency.
- `region_aware_latency` is a v0 heuristic, not active probing.
- No policy constraints for safety, compliance, or provider allowlists.
