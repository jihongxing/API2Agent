# Failover Ledger Dogfood Report

Date: May 30, 2026

## Goal

Verify that API2Agent records failed provider attempts in the usage ledger and can fail over to a secondary provider under the same routing decision.

This dogfood validates API2Agent reliability. It does not validate marketplace behavior.

## Scenario

Capability:

- `public_ip_lookup`

Providers:

- `httpbin_500`
  - source: `https://httpbin.org/status/500`
  - expected result: HTTP 500
  - estimated cost: `0.003`
- `ipify`
  - source: `https://api.ipify.org?format=json`
  - output mapping: `ip <- $.ip`
  - estimated cost: `0.001`

Routing policy:

- strategy: `first`
- failover: `true`

Execution path:

```text
route selected httpbin_500
  -> httpbin_500 through proxy
  -> HTTP 500 usage event
  -> failover to ipify through proxy
  -> HTTP 200 usage event
  -> normalized output
  -> one routing_decision_id links both attempts
```

## Result

Final result succeeded through failover.

```json
{
  "ok": true,
  "final_provider_id": "ipify",
  "normalized_body": {
    "ip": "108.174.61.76"
  }
}
```

Attempts:

```json
[
  {
    "provider_id": "httpbin_500",
    "ok": false,
    "status_code": 500,
    "error": {
      "type": "http_status",
      "message": "HTTP 500"
    }
  },
  {
    "provider_id": "ipify",
    "ok": true,
    "status_code": 200,
    "error": null
  }
]
```

Ledger rows:

```json
[
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "httpbin_500",
    "total_calls": 1,
    "successful_calls": 0,
    "failed_calls": 1,
    "success_rate": 0.0,
    "average_latency_ms": 2600.8213001769036,
    "estimated_cost": 0.003
  },
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "ipify",
    "total_calls": 1,
    "successful_calls": 1,
    "failed_calls": 0,
    "success_rate": 1.0,
    "average_latency_ms": 2380.0826999358833,
    "estimated_cost": 0.001
  }
]
```

Usage summary:

```json
{
  "project_id": "local",
  "total_calls": 2,
  "successful_calls": 1,
  "failed_calls": 1,
  "success_rate": 0.5,
  "average_latency_ms": 2490.4520000563934,
  "estimated_cost": 0.004,
  "error_counts": {
    "http_status": 1
  }
}
```

## Implementation Change

Successful failover responses now include an `attempts` array, so the caller can inspect failed attempts even when a fallback provider succeeds.

## Product Learning

The reliability model stands:

- failed provider attempts are visible
- failed provider attempts enter the ledger
- successful fallback attempts enter the same ledger
- both attempts share one `routing_decision_id`
- final capability output can still succeed after provider failure

This is the right foundation for API2Agent reliability and future economic measurement. The next step is to turn this into policy: when should API2Agent fail over, and which failures are eligible for fallback?

