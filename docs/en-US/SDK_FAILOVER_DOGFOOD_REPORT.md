# SDK Failover Dogfood Report

Date: May 30, 2026

## Goal

Verify that the hand-written SDK core loop can fail over from a failed provider attempt to a fallback provider, while recording both attempts under one routing decision.

Capability:

- `weather.get`

Primary provider:

- `open_meteo`

Fallback provider:

- `wttr_in`

## Method

The dogfood used a controlled failing adapter for `open_meteo` that returned:

```json
{
  "ok": false,
  "status_code": 500,
  "error_type": "PROVIDER_ERROR"
}
```

The fallback provider was the real `wttr_in` adapter calling the live API.

SDK call:

```python
from api2agent import sdk

result = sdk.call(
    "weather.get",
    {"city": "San Francisco"},
    strategy="first",
    failover=True,
    max_attempts=2,
    db=".dogfood/sdk-failover-real-fallback.sqlite",
)
```

## Result

The SDK returned success through the fallback provider:

```json
{
  "ok": true,
  "provider_id": "wttr_in",
  "attempts": [
    {
      "provider_id": "open_meteo",
      "ok": false,
      "status_code": 500,
      "error_type": "PROVIDER_ERROR"
    },
    {
      "provider_id": "wttr_in",
      "ok": true,
      "status_code": 200,
      "error_type": null
    }
  ]
}
```

Ledger rows:

| Provider | Execution Mode | Calls | Success | Failure | Average Latency |
| --- | --- | ---: | ---: | ---: | ---: |
| `open_meteo` | `direct` | 1 | 0 | 1 | 12.00 ms |
| `wttr_in` | `direct` | 1 | 1 | 0 | 1894.06 ms |

The routing decision stored:

- `strategy`: `first`
- `selected_provider_id`: `open_meteo`
- `ranked_provider_ids`: `["open_meteo", "wttr_in"]`
- `failover_policy.enabled`: `true`
- `failover_policy.max_attempts`: `2`

## What This Proves

The SDK path now has the same reliability shape as the CLI execution path:

```text
route
  -> primary attempt
  -> usage event
  -> failover decision
  -> fallback attempt
  -> usage event
  -> ledger
```

Failed providers do not disappear from metrics. They become part of the observability and routing feedback loop.

## Limits

- primary failure was controlled, not a live provider outage
- fallback provider was live
- no hosted identity, quota, or credential vault yet
