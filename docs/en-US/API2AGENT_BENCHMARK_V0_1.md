# API2Agent Benchmark v0.1

Date: May 30, 2026

## Goal

Benchmark the first SDK E2E loop across two real providers for one capability.

Capability:

- `weather.get`

Providers:

- `open_meteo`
- `wttr_in`

Input:

```json
{
  "city": "San Francisco"
}
```

## Method

Both providers were called through:

```python
from api2agent import call

call("weather.get", {"city": "San Francisco"}, provider_id="open_meteo")
call("weather.get", {"city": "San Francisco"}, provider_id="wttr_in")
```

Both calls wrote:

- routing decision
- usage event
- ledger row

The repeated benchmark was run with:

```python
from api2agent.benchmark import run_weather_benchmark

run_weather_benchmark(
    city="San Francisco",
    iterations=3,
    db=".dogfood/weather-benchmark-repeat.sqlite",
)
```

After the benchmark populated metrics, a default SDK call without `provider_id` was executed against the same database to verify provider selection from observed metrics.

## Results

| Provider | Calls | Success Rate | p50 Latency | p95 Latency | Estimated Cost | Observed Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `open_meteo` | 3 | 100% | 3368.97 ms | 5958.40 ms | 0.0 | 0.0 |
| `wttr_in` | 3 | 100% | 2161.30 ms | 3307.59 ms | 0.0 | 0.0 |

The follow-up default SDK call selected:

```json
{
  "provider_id": "wttr_in",
  "ranked_provider_ids": ["wttr_in", "open_meteo"],
  "ok": true
}
```

Local ledger summary after benchmark plus default call:

| Provider | Execution Mode | Calls | Success Rate | Average Latency |
| --- | --- | ---: | ---: | ---: |
| `open_meteo` | `direct` | 3 | 100% | 4246.34 ms |
| `wttr_in` | `direct` | 4 | 100% | 2303.71 ms |

## What This Proves

API2Agent can now compare two providers under one capability using real execution data.

The SDK can also use that data in the next call. With both providers present in the same local usage store, default routing ranked providers by lowest observed latency and selected `wttr_in`.

This is the first visible form of the future routing data flywheel:

```text
call
  -> usage event
  -> ledger row
  -> provider metrics
  -> next routing decision
```

## Limitations

- only three benchmark calls per provider
- no observed paid cost
- routing uses simple observed average latency, not p50/p95 or a weighted policy
- no identity or hosted control plane yet

## Next Step

Continue hardening the SDK core loop:

- expose benchmark and failover examples in developer docs
- define SDK-facing error and retry policy defaults in protocol docs
- keep benchmark data local and transparent
