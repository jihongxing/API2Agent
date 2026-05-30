# Go Data Plane Failover Dogfood Report

Date: 2026-05-30

## Goal

Verify that the Go Data Plane can execute one capability through a primary provider failure and a fallback provider success while preserving the v0.2 execution graph.

## Setup

Capability:

```text
network.public_ip.get
```

Providers:

- `ipify_primary_v1`: local fake provider returning HTTP 500
- `ipify_fallback_v1`: local fake provider returning `{ "ip": "203.0.113.99" }`

Script:

```text
python scripts/go_dataplane_failover_dogfood.py --output .dogfood/go-dataplane-failover/report.json
```

## Result

```json
{
  "passed": true,
  "checks": {
    "response_success": true,
    "fallback_output": true,
    "two_usage_events": true,
    "first_attempt_failed": true,
    "first_attempt_provider_error": true,
    "second_attempt_succeeded": true,
    "decision_log_success": true,
    "decision_log_references_both_attempts": true,
    "selected_fallback_provider": true
  }
}
```

## What This Proves

- Go Data Plane can attempt multiple ranked providers under one `RoutingDecision`.
- Failed provider attempts are written as `UsageEvent` records.
- Successful fallback attempts are written as separate `UsageEvent` records.
- `DecisionLog` records the final outcome and references both attempts.
- The selected provider in the final observation can differ from the pre-execution primary plan when failover succeeds.

## Notes

This dogfood uses local fake providers to isolate failover behavior from external network instability.
