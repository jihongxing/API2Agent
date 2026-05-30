# Go/Python Dual-Run Dogfood Report

Date: 2026-05-30

## Goal

Verify that the Python reference path and the Go Data Plane skeleton can execute the same capability and produce semantically compatible results.

## Setup

Capability:

```text
network.public_ip.get
```

Provider:

```text
ipify
```

Dogfood mode:

- local fake ipify-compatible provider
- deterministic response: `{ "ip": "203.0.113.42" }`
- Python generated package executes through `execute_capability`
- Go Data Plane executes through `/v1/execute`

Script:

```text
python scripts/dual_run_go_python_public_ip.py --output .dogfood/go-python-dual-run/report.json
```

## Result

```json
{
  "passed": true,
  "comparisons": {
    "same_success": true,
    "same_output": true,
    "same_capability_id": true,
    "same_provider_id": true,
    "go_has_request_context": true,
    "go_has_routing_decision": true,
    "go_has_usage_event": true,
    "go_has_decision_log": true,
    "go_has_snapshot_version": true
  }
}
```

## What This Proves

- Python and Go can execute the same capability ID.
- Both paths normalize to the same output shape.
- Go emits the v0.2 execution graph seed:
  - RequestContext
  - RoutingDecision
  - UsageEvent
  - DecisionLog
- Go routing decisions include snapshot version metadata.

## Notes

The dogfood uses a local fake provider to avoid external network instability. Earlier direct Go calls to real `api.ipify.org` were refused in the local environment even though PowerShell could reach it. The local dual-run isolates protocol compatibility from provider network behavior.
