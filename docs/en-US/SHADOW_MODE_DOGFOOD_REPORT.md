# Shadow Mode Dogfood Report

Date: May 30, 2026

## Goal

Verify that API2Agent can run an additional provider in `shadow` mode without changing the main SDK result.

Capability:

- `weather.get`

Main provider:

- `open_meteo`

Shadow provider:

- `wttr_in`

## Method

SDK call:

```python
from api2agent import call

result = call(
    "weather.get",
    {"city": "San Francisco"},
    strategy="first",
    shadow=True,
    db=".dogfood/shadow-weather.sqlite",
)
```

## Result

Main result:

```json
{
  "ok": true,
  "provider_id": "open_meteo"
}
```

Shadow attempt:

```json
{
  "provider_id": "wttr_in",
  "ok": true,
  "status_code": 200,
  "latency_ms": 1786.19
}
```

Ledger rows:

| Provider | Execution Mode | Calls | Success Rate | Average Latency |
| --- | --- | ---: | ---: | ---: |
| `open_meteo` | `direct` | 1 | 100% | 3342.38 ms |
| `wttr_in` | `shadow` | 1 | 100% | 1786.19 ms |

## What This Proves

API2Agent can collect provider comparison data without changing the user-visible result.

This is the first implementation of the benchmark data path:

```text
main provider result
  -> returned to caller
shadow provider result
  -> recorded as metrics
  -> available for future routing
```

## Limits

- implemented in SDK path first
- not yet available in generated package CLI execution
- shadow events currently contribute to aggregate metrics
