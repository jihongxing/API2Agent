# API2Agent Generated Package Latency Benchmark Helper Report v0

Date: 2026-05-31

Status: complete

## Summary

Generated packages now have a reusable latency benchmark helper and CLI command for repeated direct/proxy timing.

This closes the current Tooling Re-entry speed-readiness gap without expanding scope:

- API-first only
- no workflow engine
- no marketplace or billing
- no credential vault
- no new provider runtime

## What Changed

### Python Helper

Added:

```python
from api2agent.benchmark import run_generated_package_latency_benchmark
```

The helper accepts a generated package directory, tool name, params, iteration count, and optional proxy URL. It returns:

- direct-mode run stats
- proxy-mode run stats when `proxy_url` is provided
- success rate
- p50 latency
- p95 latency
- per-run status, error type, latency, and usage event id
- generated capability provider-region metadata

### CLI Command

Added:

```bash
api2agent benchmark-package ./api2agent-output \
  --tool get_items \
  --iterations 3 \
  --proxy-url http://127.0.0.1:8765 \
  --provider-region local \
  --json
```

The command can run direct mode, proxy mode, or both.

## Dogfood

Repro command:

```bash
python scripts/api2agent_generated_package_latency_benchmark_dogfood.py
```

Artifact:

```text
.dogfood/generated-package-latency-benchmark/result.json
```

Dogfood flow:

```text
generated curl package
  -> direct benchmark loop
  -> local API2Agent proxy benchmark loop
  -> SQLite proxy usage events
  -> p50/p95 report
```

Dogfood checks:

- direct mode ran 3 successful calls
- proxy mode ran 3 successful calls
- direct and proxy stats include p50/p95 latency
- proxy results include usage event ids
- proxy usage events record `provider_region == "local"`
- scope remains API-first and no-workflow-engine

## Result

The dogfood passed.

Key observed values:

```json
{
  "direct_successful_runs": 3,
  "proxy_successful_runs": 3,
  "proxy_usage_event_count": 3,
  "provider_region": "local"
}
```

## Why This Matters

The Tooling Layer now has a first-class way to measure generated package latency, instead of hiding this logic inside ad hoc audit scripts.

This directly supports the current API2Agent goals:

- more real execution data: proxy benchmark runs produce usage events
- lower onboarding cost: generated packages can be benchmarked without source edits
- faster responses: direct/proxy p50 and p95 are visible per generated tool

## Remaining Gap

The next Tooling Re-entry gap returns to onboarding cost: endpoint-level auth inference.

Next task:

```text
Endpoint-level Auth Inference v0
```
