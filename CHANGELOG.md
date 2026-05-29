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
- Safe replay metadata capture for SDK, proxy, and local package execution paths.
- Alpha capability naming validation warnings for `<domain>.<resource>.<action>`.
- SDK shadow execution mode for benchmark-only provider calls.
- Exact replay execution for supported SDK and no-credential HTTP events.
- Optional replay usage recording with isolated `replay` execution mode.
- Explicit metrics policy: include `shadow` by default, exclude `replay` by default.
- Golden trace marker for usage events.
- Golden trace listing and ledger filtering.
- Generated package shadow execution mode for `api2agent call`.
- Local generated package replay execution.
- Credential Orchestration strategy and MVP-2.5 planning docs.
- Credential Schema v0.1 code models and local resolver.
- Credential injection patches for generated package execution.
- Credential-safe usage attribution and local package replay.
- Proxy-side credential intent and credential injection.
- Proxy missing-credential usage events without provider forwarding.
- Dogfood reports for compiler, proxy, routing, ledger, failover, benchmark, and SDK failover.
- Bilingual documentation under `docs/en-US` and `docs/cn-ZH`.

### Verified

- Baseline commit created: `7157226`.
- Real API dogfood across Swagger Petstore, GitHub REST, httpbin, JSONPlaceholder, ipify, Open-Meteo, and wttr.in.
- Repeated benchmark calls for `open_meteo` and `wttr_in` with p50/p95 latency.
- SDK failover from controlled `open_meteo` failure to real `wttr_in` fallback.
- Replay preflight dogfooded against a failed Quickstart usage event.
- Replay metadata capture dogfooded with `exact_replay_metadata_ready: true`.
- Registry naming warnings dogfooded against legacy `public_ip_lookup`.
- Shadow mode dogfooded with `open_meteo` as main provider and `wttr_in` as shadow provider.
- Exact replay dogfooded against a real `wttr_in` shadow event.
- Replay recording dogfooded and verified as excluded from routing metrics.
- Shadow metrics policy dogfooded with include/exclude comparison.
- Golden trace marker dogfooded against a real `wttr_in` shadow event.
- Generated package shadow/replay paths covered by regression tests.
- Generated package shadow/replay dogfooded against real no-auth `ipify` and `httpbin` APIs.
- Credential resolver dogfooded with env-based bearer injection and replay.
- Proxy credential injection dogfooded with env-based bearer intent and missing-secret failure.
- Full test suite: `116 passed`.

### Planned Next

- Decide when capability naming moves from warning to hard enforcement.
