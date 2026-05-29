# Capability Metrics and Routing Dogfood Report

## 1. Goal

This dogfood validates the roadmap stages after Control Layer:

```text
usage events
  -> provider metrics
  -> capability comparison
  -> routing decision
```

It does not execute the selected provider yet. Routing execution loop is a later roadmap phase.

## 2. Setup

Capability:

```text
image_generation
```

Provider candidates:

| Provider | Intent | Estimated Cost |
|---|---|---:|
| `fast_cheap` | lower latency and lower cost | 0.01 |
| `reliable_expensive` | higher success rate | 0.04 |

Synthetic usage events were inserted into the local SQLite usage store.

## 3. Metrics

| Provider | Total Calls | Success Rate | Avg Latency | Estimated Cost / Call |
|---|---:|---:|---:|---:|
| `fast_cheap` | 5 | 60% | 740 ms | 0.01 |
| `reliable_expensive` | 5 | 100% | 1560 ms | 0.04 |

## 4. Routing Results

| Strategy | Selected Provider | Reason |
|---|---|---|
| `lowest_cost` | `fast_cheap` | lower observed cost |
| `lowest_latency` | `fast_cheap` | lower observed latency |
| `highest_success_rate` | `reliable_expensive` | higher observed success rate |
| `balanced` | `fast_cheap` | default weights favor combined latency/cost enough to beat reliability |

## 5. Observations

### What Worked

- Usage events aggregate into provider-level metrics.
- Two providers can be compared under one capability.
- Routing strategy changes provider selection.
- `api2agent route` can rank providers using registry + metrics.

### What Needs Product Design

- The default `balanced` strategy currently favors low cost and low latency strongly enough that a provider with lower success rate can win.
- This is not necessarily wrong, but it must be explicit.
- Future routing policies need named presets, for example:
  - `reliability_first`
  - `cost_first`
  - `latency_first`
  - `balanced`
- Capability comparability needs more than shared `capability_id`; input/output compatibility and output quality must be defined.

## 6. Decision

Capability Metrics MVP and Routing v0 are valid as selection primitives.

Do not implement routing execution loop until:

1. routing decision event is defined
2. routing policy presets are documented
3. at least one real two-provider capability dogfood is designed
