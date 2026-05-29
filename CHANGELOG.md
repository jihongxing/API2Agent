# Changelog

All notable API2Agent changes will be documented in this file.

## v0.1-alpha baseline - Unreleased

### Positioning

- Defined API2Agent v0.1-alpha as a local Agent API execution and observability layer.
- Chose Reliability + Observability as the alpha product hook.
- Kept marketplace explicitly out of the current implementation scope.

### Added

- OpenAPI/curl to API2Agent IR compiler.
- Local capability package generation.
- Generated runner, MCP server, smoke test, and README.
- Tool filtering by tag, path, operation, and max tool count.
- Local API2Agent proxy with usage tracking and quota.
- SQLite usage store, usage summary, ledger, and decision inspection.
- Capability, provider candidate, metrics snapshot, routing policy, and failover policy models.
- Provider registry validation and inspection.
- Routing execution loop with output normalization.
- Direct and proxy execution modes.
- SDK core loop for `weather.get`.
- Open-Meteo and wttr.in weather adapters.
- SDK routing strategy selection.
- SDK failover with failed and fallback attempts recorded under one routing decision.
- Benchmark helper for repeated weather provider comparison.
- Replay preflight command for usage event audit.
- Alpha capability naming validation warnings for `<domain>.<resource>.<action>`.
- Dogfood reports for compiler, proxy, routing, ledger, failover, benchmark, and SDK failover.
- Bilingual documentation under `docs/en-US` and `docs/cn-ZH`.

### Verified

- Baseline commit created: `7157226`.
- Real API dogfood across Swagger Petstore, GitHub REST, httpbin, JSONPlaceholder, ipify, Open-Meteo, and wttr.in.
- Repeated benchmark calls for `open_meteo` and `wttr_in` with p50/p95 latency.
- SDK failover from controlled `open_meteo` failure to real `wttr_in` fallback.
- Replay preflight dogfooded against a failed Quickstart usage event.
- Registry naming warnings dogfooded against legacy `public_ip_lookup`.
- Full test suite: `87 passed`.

### Planned Next

- Exact replay metadata capture for request params and credential references.
- `shadow` execution mode for benchmark-only provider calls.
- Golden trace marker for known-good executions.
