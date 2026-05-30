# Go Data Plane Real External Provider Retry Dogfood Report

Date: 2026-05-30

## Goal

Verify that Go Data Plane can retry against real external provider endpoints: a failing `httpbin` status endpoint first, then a successful `httpbin` IP fallback.

## Setup

Capability:

```text
network.public_ip.get
```

Providers:

- `httpbin_real_500_v1`
  - source: `https://httpbin.org/status/500`
  - expected result: HTTP 500
- `httpbin_ip_real_v1`
  - source: `https://httpbin.org/ip`
  - output mapping: `ip <- $.origin`

Script:

```text
python scripts/go_dataplane_real_external_provider_retry_dogfood.py --output .dogfood/go-dataplane-real-external-retry/report.json
```

## Result

```json
{
  "passed": true,
  "checks": {
    "response_success": true,
    "normalized_output_has_ip": true,
    "two_usage_events": true,
    "first_attempt_failed": true,
    "first_attempt_provider_error": true,
    "second_attempt_succeeded": true,
    "decision_log_success": true,
    "decision_log_references_both_attempts": true,
    "selected_fallback_provider": true,
    "event_order_is_graph": true
  }
}
```

Attempt summary:

```json
[
  {
    "candidate_id": "httpbin_real_500_v1",
    "provider_id": "httpbin",
    "status_code": 500,
    "success": false,
    "error_type": "PROVIDER_ERROR"
  },
  {
    "candidate_id": "httpbin_ip_real_v1",
    "provider_id": "httpbin",
    "status_code": 200,
    "success": true,
    "error_type": null
  }
]
```

## What This Proves

- Go Data Plane can fail over across real external provider endpoints.
- The first provider attempt is recorded as a failed `UsageEvent`.
- The fallback provider attempt is recorded as a second `UsageEvent`.
- The final `DecisionLog` references both attempts.
- The final output remains normalized as `{"ip": ...}`.

## Notes

This is the first real external retry/failover dogfood for the Go Data Plane. It is still a local execution path, not a hosted control plane or billing path.

An earlier attempt to use `api.ipify.org` as the fallback was refused by the remote host from the local Go process. That failure is a useful reminder that external API availability must be measured from the actual execution runtime, not assumed from documentation.
