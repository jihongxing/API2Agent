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
- `highest_success_rate`
- `balanced`

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

- No routing execution loop yet.
- No failover execution yet.
- No quality evaluation beyond success/cost/latency.
- No policy constraints for safety, region, compliance, or provider allowlists.
