# Changelog

All notable API2Agent changes will be documented in this file.

## v0.1-alpha baseline - Unreleased

### Positioning

- Defined API2Agent v0.1-alpha as a local Agent API execution and observability layer.
- Chose Reliability + Observability as the alpha product hook.
- Kept marketplace explicitly out of the current implementation scope.
- Increased strategic priority for real execution data and lowest API/provider onboarding cost.
- Added location-aware execution as a future routing requirement.

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
- Project-level credential config loading for the local proxy.
- Deterministic credential precedence and project-owner matching policy.
- Credential scope matching for provider, capability, tool, and wildcard access.
- Credential lifecycle metadata for status, expiry, and rotation audit hints.
- Credential audit reporting in `api2agent usage --credential-audit`.
- Location-aware usage schema, provider region metadata, and decision dataset contract.
- Region-aware routing strategy `region_aware_latency`.
- `--client-region` support for `api2agent route` and `api2agent call`.
- Routing decision persistence for `client_region`.
- Region-aware routing benchmark helper and decision dataset artifact.
- Region-specific usage metrics loading for `region_aware_latency`.
- Deterministic selected provider-region semantics in routing decisions and usage events.
- Capability source boundary documentation for API-first MVP and future non-API adapters.
- MVP exit review and Architecture Definition Phase documentation.
- API2Agent Protocol v0.2 planning document.
- API2Agent Protocol v0.2 frozen contract and machine-readable schema snapshot.
- API2Agent Protocol v0.2 hardening for request context, versioned definitions, metrics windows, routing plan vs observation split, execution properties, credential resolution strategy, and error scope.
- Production Architecture RFC with Go Data Plane, Go Control Plane backend, Python reference boundaries, storage ownership, deployment phases, and v0.3 architecture inputs.
- Python reference migration plan documenting the hot-path to reference-path transition.
- Go Data Plane Skeleton plan covering `/v1/execute`, local snapshots, deterministic routing, ipify adapter, event writer, timeout budgets, and dual-run compatibility.
- Go Data Plane Skeleton implementation with `/v1/execute`, static snapshot loading, deterministic routing, ipify adapter, JSONL event writer, and golden path Go tests.
- Go/Python dual-run dogfood for `network.public_ip.get` with matching normalized output and Go execution graph events.
- Go Data Plane Skeleton hardening with `/healthz`, snapshot TTL helpers, bearer auth regression tests, timeout error mapping, missing-adapter failure events, and event sequence checks.
- Go Data Plane protocol conformance checks for emitted RequestContext, RoutingDecision, UsageEvent, and DecisionLog records against the v0.2 schema snapshot.
- Go Data Plane retry/failover execution with per-attempt UsageEvents and final DecisionLog attempt aggregation.
- Go Data Plane failover dogfood script and bilingual report for controlled HTTP 500 primary failure followed by fallback success.
- Go Data Plane env credential resolution skeleton with request-level credential intent, header/query injection patches, redacted usage attribution, and missing-secret failure behavior.
- Go Data Plane credential dogfood script and bilingual report for env-backed bearer injection without raw secret leakage.
- Go Data Plane durable JSONL event ingestion with startup sequence recovery and fsync-backed writes.
- Go Data Plane durable event dogfood script and bilingual report for restart-safe event sequence continuity.
- Go Data Plane httpbin IP adapter for real external public-IP fallback normalization.
- Go Data Plane real external provider retry dogfood script and bilingual report.
- Go Data Plane stage review and consolidation hardening plan.
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
- Proxy credential config dogfooded with config-based query injection.
- Credential policy dogfooded across inline/config/request precedence and owner fallback.
- Credential scope dogfooded across allow, deny, and no-fallback cases.
- Credential lifecycle dogfooded across disabled, expired, and active credentials.
- Credential audit CLI dogfooded with JSON/text output and allowlisted metadata.
- Authenticated proxy credential dogfooded against real httpbin bearer auth.
- Location-aware routing strategy documented.
- Location-aware schema dogfooded across usage storage, proxy events, provider metadata, and decision dataset records.
- Region-aware routing strategy dogfooded with same-capability, different-region providers.
- Go Data Plane hardening tests for health metadata, project-key auth, timeout usage errors, and failed decision logging.
- Go Data Plane protocol conformance tests passed for v0.2 execution graph records.
- Go Data Plane failover dogfood passed with two usage attempts and fallback provider selection.
- Go Data Plane credential dogfood passed with env-backed bearer injection and redacted credential metadata.
- Go Data Plane durable event dogfood passed with two process runs, eight event records, and monotonic event sequence IDs.
- Go Data Plane real external provider retry dogfood passed with `httpbin/status/500` followed by `httpbin/ip` fallback.
- Go Data Plane stage review completed and next hardening slice narrowed.
- Full test suite: `143 passed`.

### Planned Next

- Go Data Plane schema conformance should be promoted from test helper to reusable validator.
- Start Go Data Plane Consolidation Hardening v0.
