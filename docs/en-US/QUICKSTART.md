# API2Agent Quickstart

This quickstart reproduces the v0.1-alpha loop:

```text
one capability
  -> two providers
  -> benchmark comparison
  -> failover
  -> usage ledger
```

Current alpha capability:

- legacy ID: `weather.get`
- target naming rule: `weather.current.get`

`weather.get` remains in code for compatibility while the alpha naming rule is introduced.

## 1. Install

```bash
python -m pip install -e ".[dev]"
pytest
```

Expected:

```text
123 passed
```

## 2. First SDK Call

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

This records:

- routing decision
- usage event
- ledger row

## 3. Benchmark Two Providers

```python
from api2agent.benchmark import run_weather_benchmark

result = run_weather_benchmark(
    city="San Francisco",
    iterations=3,
    db=".dogfood/quickstart-benchmark.sqlite",
)

print(result)
```

This compares:

- `open_meteo`
- `wttr_in`

Metrics include:

- total calls
- success rate
- p50 latency
- p95 latency
- estimated vs observed cost

After metrics exist, a default SDK call ranks providers by observed local latency:

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

This demo forces the primary provider to fail, then falls back to the real `wttr_in` provider.

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

Expected:

- first attempt: `open_meteo`, failed, `500`
- second attempt: `wttr_in`, success, `200`

## 5. Shadow Demo

Shadow mode runs additional providers for benchmark data without changing the main result:

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

Expected:

- main result provider: `open_meteo`
- shadow provider: `wttr_in`
- ledger includes both `direct` and `shadow` execution modes

Shadow metrics are included in routing aggregates by default. CLI routing paths can opt out with:

```bash
--exclude-shadow-metrics
```

## 6. Inspect Ledger

If the `api2agent` console script is installed:

```bash
api2agent ledger --db .dogfood/quickstart-failover.sqlite --capability-id weather.get --group-by-mode --json
```

Portable form:

```bash
python -m api2agent.cli ledger --db .dogfood/quickstart-failover.sqlite --capability-id weather.get --group-by-mode --json
```

Expected ledger shape:

- one failed `open_meteo` row
- one successful `wttr_in` row
- both in `direct` execution mode

## 7. Replay Preflight

`replay` works as a preflight and audit view by default. Add `--execute` to re-run supported SDK or no-credential HTTP events.

```bash
python -m api2agent.cli replay <usage_event_id> --db .dogfood/quickstart-failover.sqlite --json
```

Current expected result:

- usage event is returned
- routing decision is returned
- missing exact replay fields are listed

Execute replay when `replayable` is `true`:

```bash
python -m api2agent.cli replay <usage_event_id> --db .dogfood/quickstart-failover.sqlite --execute --json
```

Record the replay execution in the ledger without affecting routing metrics:

```bash
python -m api2agent.cli replay <usage_event_id> --db .dogfood/quickstart-failover.sqlite --execute --record --json
```

## 8. Golden Trace Marker

Mark a known-good usage event as a golden trace:

```bash
python -m api2agent.cli golden <usage_event_id> --db .dogfood/quickstart-failover.sqlite --json
```

List golden traces and filter ledger rows to golden baselines:

```bash
python -m api2agent.cli golden --list --db .dogfood/quickstart-failover.sqlite --capability-id weather.get --json
python -m api2agent.cli ledger --db .dogfood/quickstart-failover.sqlite --golden-only --json
```

Golden traces are baselines for replay, benchmarks, scoring, and regression tests.

## 9. Generate A Local Capability Package

```bash
api2agent generate examples/openapi/basic.yaml --force
api2agent inspect api2agent-output
api2agent test api2agent-output
```

Portable form:

```bash
python -m api2agent.cli generate examples/openapi/basic.yaml --force
python -m api2agent.cli inspect api2agent-output
python -m api2agent.cli test api2agent-output
```

Generated packages also support the local reliability loop when they are registered as providers:

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

This proves the compiler path still works alongside the SDK execution loop, including shadow observations and local package replay.

## 10. What This Proves

API2Agent v0.1-alpha proves:

- an Agent can call a capability instead of a raw API
- providers can be compared under one capability
- provider failure can be recorded and recovered with failover
- shadow providers can collect benchmark data without changing the main result
- every attempt can be audited through the ledger
- failed attempts can be inspected through replay preflight
- generated package attempts can be shadowed and replayed locally
- known-good attempts can be marked, listed, and filtered as golden traces

Marketplace, hosted SaaS, and payment are intentionally out of scope.
