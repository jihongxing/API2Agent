# Go Data Plane Provider Probe Dogfood Report

Date: 2026-05-30

## Goal

Measure provider reachability from the Go Data Plane runtime itself.

This does not rank providers or create marketplace behavior. It only proves that availability must be observed from the actual execution runtime.

## Script

```text
python scripts/go_dataplane_provider_probe_dogfood.py --output .dogfood/go-dataplane-provider-probe/report.json
```

## Result

```json
{
  "passed": true,
  "probe_count": 2,
  "reachable_count": 1,
  "checks": {
    "at_least_one_provider_reachable": true,
    "all_results_from_go_runtime": true,
    "all_results_have_events": true
  }
}
```

Provider observations:

```json
[
  {
    "candidate_id": "httpbin_ip_probe_v1",
    "provider_id": "httpbin",
    "reachable": true,
    "status_code": 200
  },
  {
    "candidate_id": "ipify_probe_v1",
    "provider_id": "ipify",
    "reachable": false,
    "status_code": 0,
    "error_type": "PROVIDER_ERROR"
  }
]
```

## What This Proves

- Provider availability differs by execution runtime.
- Go Data Plane can record successful and failed provider reachability attempts.
- Provider probe belongs in observability first, not marketplace ranking.
