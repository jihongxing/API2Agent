# API2Agent Roadmap

## 1. Roadmap Role

This document is the canonical implementation plan.

Future work should follow this roadmap unless the roadmap is explicitly updated first.

`docs/en-US/API2AGENT_PROTOCOL.md` defines the protocol direction that this roadmap implements.

Current product direction:

```text
usable -> controllable -> measurable -> comparable -> routable -> reliable execution
```

Current execution focus:

```text
Agent request -> SDK call -> Adapter -> Real API -> Normalized output -> Usage -> Ledger
```

Current build target:

```text
API2Agent
```

Current phase:

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Live Dogfood + Closeout Complete
```

Strategic thesis:

> API2Agent starts as a local Agent capability compiler, then becomes the control, metrics, routing, and reliable execution layer for Agent access to API-backed capabilities.

Tooling re-entry thesis:

> API2Agent completed a constrained return to the Tooling Layer with Control/Data Plane constraints. The Tooling Layer optimizes for more real execution data, lower API/provider onboarding cost, and faster Agent API responses while remaining API-first and not becoming a workflow engine. See `docs/en-US/API2AGENT_TOOLING_REENTRY_REVIEW_AND_EXPANSION_PLAN.md`.

Receipt and trust thesis:

> API2Agent should eventually turn internal usage observations into verifiable receipts that can power routing, trust, anti-gaming controls, and future settlement. This is a strategic direction, not the current implementation task. See `docs/en-US/CONTROL_RECEIPT_AND_TRUST_LAYER_STRATEGY.md`.

Capability source boundary:

> v0.1-alpha is API-first. Long term, API2Agent may support any source that can be adapted into `input -> execution -> output`, but non-API sources enter only as future adapters after API execution is reliable. See `docs/en-US/CAPABILITY_SOURCES.md`.

v0.1-alpha product hook:

```text
Reliability + Observability
```

The alpha must prove that API2Agent makes Agent API calls more reliable, measurable, and debuggable than calling providers directly.

Marketplace is a far-term optional outcome. It is not the current product, not the current MVP, and not an active implementation phase.

## 2. Current Status

Implemented:

- local OpenAPI/curl compiler
- API2Agent IR
- capability package generation
- generated runner
- generated MCP server
- smoke test
- tool filtering / selection
- local API2Agent Proxy
- SQLite usage event store
- usage summary command
- project-level quota
- generated runner proxy mode
- Capability Schema v0.1 code model
- Provider Candidate model
- Metrics Snapshot model
- Routing Policy model
- Routing v0 provider selection command
- local routing execution loop
- output normalization metadata and execution
- SDK E2E core loop for `weather.get`
- repeated two-provider weather benchmark with p50/p95 latency
- SDK default provider selection from observed local metrics
- explicit SDK routing strategy selection
- SDK failover with failed and fallback attempts recorded in usage events
- v0.1-alpha plan with Reliability + Observability as the product hook
- CHANGELOG
- alpha Quickstart with SDK call, benchmark, failover, ledger, and compiler path
- clean baseline commit: `7157226`
- replay preflight command for usage event audit
- safe replay metadata capture for SDK, proxy, and local package execution paths
- alpha capability naming validation warnings
- SDK shadow execution mode
- exact replay execution for supported SDK and no-credential HTTP events
- optional replay usage recording with `execution_mode=replay`
- explicit routing metrics policy for `shadow` and `replay`
- golden trace marker for usage events
- golden trace filtering command
- local generated package replay execution
- generated package shadow execution mode
- Credential Orchestration strategy document
- Credential Schema v0.1 code models
- local Credential Resolver
- credential injection patches for generated package execution
- credential-safe usage attribution and replay
- capability source boundary document
- MVP exit review
- Architecture Definition Phase document
- API2Agent Protocol v0.2 plan
- API2Agent Protocol v0.2 frozen contract
- API2Agent Protocol v0.2 schema snapshot
- API2Agent Protocol v0.2 hardening constraints for request context, versions, metrics windows, and plan/observation split
- Production Architecture RFC with Go Data Plane and Go Control Plane backend direction
- Python reference migration plan
- Go Data Plane Skeleton plan
- Go Data Plane Skeleton implementation under `services/data-plane`
- Go/Python dual-run dogfood for `network.public_ip.get`
- Go Data Plane Skeleton hardening with health, auth, timeout, snapshot TTL, and failure-event tests
- Go Data Plane protocol conformance checks against the v0.2 schema snapshot
- Go Data Plane retry/failover execution and controlled failover dogfood
- Go Data Plane env credential resolution skeleton and controlled credential dogfood
- Go Data Plane durable event ingestion and real external provider retry dogfood
- Go Data Plane stage review and consolidation hardening plan

Not implemented yet:

- non-API capability source adapters
- hard enforcement of capability naming rule
- endpoint-level auth
- base URL override
- manual write tests
- hosted proxy
- credential vault
- durable multi-project backend
- capability registry persistence
- billing

Explicitly out of current API2Agent scope:

- workflow engine execution
- local function runtime
- arbitrary script sandbox
- database runtime
- human task routing
- agent-as-provider execution
- marketplace UI
- marketplace search
- provider revenue share
- public provider onboarding

## 3. Phase 1: Usable Tooling MVP

Status: implemented, needs continued regression protection.

Goal:

Make a real REST API callable by an Agent through a local generated package.

Scope:

- OpenAPI JSON/YAML input
- curl input
- API2Agent IR
- generated `capability.json`
- generated `tools.json`
- generated `runner.py`
- generated `smoke_test.py`
- generated `mcp_server.py`
- `api2agent generate`
- `api2agent inspect`
- `api2agent test`
- `api2agent run`

Exit criteria:

- real API specs can generate packages
- read-only smoke tests run safely
- generated MCP server can be called by an MCP client
- tests cover parser, generator, runner, MCP, and CLI behavior

Do not expand:

- no marketplace UI
- no hosted SaaS
- no payment
- no broad new input formats before control-plane dogfood

## 4. Phase 2: Controllable Execution MVP

Status: first local version implemented; public-read and authenticated proxy dogfood completed.

Goal:

Move from direct execution to observed and controlled execution.

Scope:

- local `api2agent proxy`
- `POST /v1/proxy/call`
- generated runner proxy mode through `API2AGENT_PROXY_URL`
- usage event schema
- SQLite usage store
- `api2agent usage`
- project-level quota
- latency/success/failure/status tracking
- estimated per-call cost field

Exit criteria:

- one generated package can call through the proxy
- proxy records usage events for success and failure
- quota blocks calls before forwarding
- usage report shows total calls, success rate, latency, cost, and errors
- dogfood report covers at least 3 real APIs through proxy mode

Current dogfood result:

- JSONPlaceholder, GitHub rate_limit, and httpbin succeeded through proxy mode.
- httpbin bearer auth succeeded through proxy mode.
- quota blocking worked on the fourth call.
- see `docs/en-US/CONTROL_LAYER_DOGFOOD_REPORT.md`.

Do not expand:

- no billing integration yet
- no provider revenue share
- no hosted deployment before local proxy behavior is proven

## 5. Phase 3: Capability Metrics MVP

Status: first code model implemented; local two-provider metrics dogfood completed.

Goal:

Turn raw usage events into comparable provider metrics under a semantic capability.

Scope:

- Capability Definition
- Provider Candidate
- Metrics Snapshot
- usage aggregation by capability/provider
- minimal provider registry JSON
- metrics fields:
  - total calls
  - success rate
  - average latency
  - estimated cost per call

Exit criteria:

- two provider candidates can map to one capability
- usage events aggregate into metrics for each provider
- docs define what makes two providers comparable
- one local demo compares two mock or real providers

Current dogfood result:

- `image_generation` was compared across `fast_cheap` and `reliable_expensive`.
- metrics successfully changed routing outcomes across strategies.
- see `docs/en-US/CAPABILITY_ROUTING_DOGFOOD_REPORT.md`.

Do not expand:

- no public registry yet
- no provider onboarding
- no manual marketplace curation

## 6. Phase 4: Routing v0

Status: provider selection implemented and dogfooded; execution loop not implemented.

Goal:

Select a provider candidate for a capability using policy and observed metrics.

Scope:

- `api2agent route`
- strategy:
  - first
  - random
  - lowest_cost
  - lowest_latency
  - highest_success_rate
  - balanced
- ranked provider output
- routing policy model

Exit criteria:

- route command selects a provider from a registry
- route command uses usage metrics when available
- tests cover strategy behavior
- one dogfood scenario proves routing selection changes when metrics change

Current dogfood result:

- `lowest_cost` and `lowest_latency` selected `fast_cheap`.
- `highest_success_rate` selected `reliable_expensive`.
- `balanced` selected `fast_cheap`, exposing the need for explicit policy presets.
- routing decision event and policy presets are now defined.

Current real-provider result:

- real `public_ip_lookup` dogfood completed with ipify and httpbin.
- both providers succeeded, but returned different output shapes.
- see `docs/en-US/REAL_TWO_PROVIDER_DOGFOOD_REPORT.md`.

Do not implement until this phase is accepted:

- automatic routing execution loop
- failover execution
- hosted routing service

## 7. Phase 5: Routing Execution Loop

Status: minimal local implementation completed and dogfooded; decision/usage correlation is the next hardening step.

Goal:

Move from selecting a provider to executing a capability request through the selected provider.

Scope:

- capability request input format
- registry lookup
- provider selection
- provider tool execution through proxy
- routing decision event
- routing decision ledger
- usage event correlation through `routing_decision_id`
- output normalization through `output_mapping`
- Failover Policy v0 after failed provider call

Exit criteria:

- one capability request can execute through the selected provider
- routing decision is recorded
- selected provider result is normalized to the capability output contract
- failed primary provider can optionally fall back to secondary provider
- failover can be limited by max attempts, error type, and HTTP status
- usage event and routing event can be correlated

Minimal local implementation:

```text
capability registry JSON
  -> select provider
  -> load provider generated package
  -> execute provider tool through proxy
  -> normalize output
  -> return routing decision + normalized result
```

Do not expand:

- no marketplace search
- no billing
- no third-party provider onboarding
 - no hosted routing service

Entry requirements:

- routing decision event defined
- routing policy presets documented
- real two-provider dogfood completed
- output normalization requirements documented

Current gate result:

- entry requirements exposed a required intermediate step: Capability Schema v0.2 for output normalization.
- v0.2 output normalization metadata is now defined.
- next implementation gate is applying normalized outputs inside routing execution, not changing provider selection.

Current dogfood result:

- `public_ip_lookup` executed through selected local generated provider packages.
- ipify and httpbin both normalized to `{ "ip": "..." }`.
- see `docs/en-US/ROUTING_EXECUTION_DOGFOOD_REPORT.md`.
- routing decision ledger and local usage ledger were dogfooded with real ipify and httpbin calls through proxy.
- see `docs/en-US/ROUTING_LEDGER_DOGFOOD_REPORT.md`.
- failover ledger behavior was dogfooded with a real HTTP 500 provider followed by a successful ipify fallback.
- see `docs/en-US/FAILOVER_LEDGER_DOGFOOD_REPORT.md`.
- Failover Policy v0 was dogfooded with real HTTP 500 and HTTP 400 providers.
- see `docs/en-US/FAILOVER_POLICY_DOGFOOD_REPORT.md`.
- routing decision inspection command was implemented and verified against a real failover dogfood database.
- stable decision/usage contract fields were documented and covered by regression fixtures.
- decision output now includes `contract_version`.
- provider registry JSON is schema-validated before route/call execution.
- provider registry contract fields are documented and covered by contract fixtures.
- registry inspection command was implemented.
- route/call JSON output now includes `registry_contract_version`.
- registry inspection now reports local package warnings.
- call execution now fails before execution when requested providers have invalid local package metadata.
- registry inspection was dogfooded against generated ipify and httpbin provider packages with zero warnings.
- `api2agent call` was dogfooded with the same registry and returned `registry_contract_version`.
- direct local execution now records usage events without proxy.
- direct local mode was dogfooded with `api2agent decision` and `api2agent ledger`.
- usage events now include `execution_mode`.
- direct and proxy execution modes were both verified through `api2agent decision`.
- direct-vs-proxy audit regression fixture was added.
- `api2agent ledger --group-by-mode` now separates direct and proxy rows.
- usage ledger contract fields were documented and covered by fixtures.
- ledger now supports project, capability, provider, and month filters.
- SDK E2E core loop for `weather.get` with Open-Meteo was implemented and dogfooded.
- second weather provider `wttr_in` was implemented.
- `API2Agent Benchmark v0.1` compared `open_meteo` and `wttr_in`.
- repeated benchmark calls now compute total calls, success rate, p50 latency, p95 latency, and estimated vs observed cost.
- default SDK routing now uses observed local metrics and selected `wttr_in` after benchmark data showed lower average latency.
- SDK callers can now pass an explicit routing strategy such as `first`, `lowest_latency`, `lowest_cost`, `highest_success_rate`, or `balanced`.
- SDK failover now records failed and successful attempts under the same routing decision.
- SDK failover was dogfooded with a controlled `open_meteo` 500 failure and a real `wttr_in` fallback.
- see `docs/en-US/SDK_FAILOVER_DOGFOOD_REPORT.md`.

Immediate next step:

- decide when capability naming moves from warning to hard enforcement
- keep policy local and explicit: no hidden marketplace-style provider preference

## 8. Phase 5.5: v0.1-alpha Product Hook Hardening

Status: planned.

Goal:

Turn the working local infra primitive into a sharp alpha product centered on Reliability + Observability.

Scope:

- clean repo baseline
- CHANGELOG
- alpha Quickstart
- capability naming rule: `<domain>.<resource>.<action>`
- replay design and local command
- execution mode matrix:
  - `direct`
  - `proxy`
  - `shadow`
  - future `race`
- golden trace contract field
- one complete alpha demo:
  - one capability
  - two providers
  - primary failure
  - fallback success
  - benchmark comparison
  - ledger inspection

Exit criteria:

- a new developer can reproduce the alpha demo from docs
- failed and fallback attempts are visible in the ledger
- provider comparison includes success rate and p50/p95 latency
- replay is implemented locally or explicitly documented as the next alpha task
- marketplace remains out of scope

Current hardening result:

- `CHANGELOG.md` created.
- bilingual Quickstart created.
- Quickstart compiler path verified with `generate`, `inspect`, and `test`.
- Quickstart failover path verified with controlled `open_meteo` failure and real `wttr_in` fallback.
- clean baseline commit created: `7157226`.
- `api2agent replay` preflight verified against a failed Quickstart usage event.
- replay metadata capture verified with `exact_replay_metadata_ready: true`.
- alpha capability naming warnings verified against legacy `public_ip_lookup`.
- SDK shadow mode verified with real `open_meteo` main result and real `wttr_in` shadow result.
- see `docs/en-US/SHADOW_MODE_DOGFOOD_REPORT.md`.
- exact replay execution verified against a real `wttr_in` shadow event.
- see `docs/en-US/REPLAY_DOGFOOD_REPORT.md`.
- replay recording verified as a ledger row excluded from routing metrics.
- shadow metrics policy verified: included by default, removable with explicit option.
- golden trace marker verified against a real `wttr_in` shadow event.
- see `docs/en-US/GOLDEN_TRACE_DOGFOOD_REPORT.md`.
- golden trace listing and `ledger --golden-only` filtering are implemented.
- generated package shadow execution mode is implemented for `api2agent call`.
- local generated package replay execution is implemented for `local_package:<package_dir>` events.
- generated package shadow + replay dogfood completed with local and real no-auth API packages; see `docs/en-US/GENERATED_PACKAGE_SHADOW_REPLAY_DOGFOOD_REPORT.md`.

## 8.6 Phase 5.6: Credential Orchestration MVP

Status: first local implementation complete.

Goal:

Make API2Agent credential-aware without building payments or hosted vaults yet.

Scope:

- Credential Schema v0.1
- credential owner model:
  - user
  - project
  - platform
  - provider
- credential sources:
  - env
  - config
  - inline
  - none
- local credential resolver
- credential injection patch
- usage event `credential_reference`
- secret redaction in request metadata and replay metadata

Exit criteria:

- one authenticated API can be called through resolved credentials
- raw secrets do not enter usage events
- replay warns when a required credential cannot be resolved
- ledger can preserve credential attribution without exposing secrets

Do not expand:

- no hosted vault yet
- no payment processing
- no provider settlement
- no marketplace credential onboarding

Completed architecture definition task:

```text
Protocol v0.2 contract freeze
Production Architecture RFC
```

Immediate next task:

```text
Complete durable event ingestion first, then run real external provider retry dogfood
```

Current implementation result:

- `api2agent/credentials/models.py` defines Credential Schema v0.1 objects.
- `api2agent/credentials/resolver.py` resolves env/config/inline/none credentials.
- generated runners can consume credential injection patches through local execution env.
- `execute_capability` resolves credentials and writes `credential_reference`.
- local package replay can re-resolve credentials from redacted metadata.
- generated runners in proxy mode now send credential intent instead of provider secrets.
- the local proxy resolves credential intent, injects provider auth, and records redacted usage attribution.
- local proxy can load project-level credential config files.
- config credentials can be used when proxy payloads do not include credential intent.
- credential resolver precedence is now explicit: inline, config, request/env intent, none.
- config credential owner matching now prefers exact project owner, then local project owner, then config order.
- credential scope matching now supports provider, capability, tool, and wildcard scope entries.
- out-of-scope credentials fail with `credential_scope_denied` and do not fall back to lower-precedence credentials.
- credential lifecycle metadata now includes status, expiry, and rotation hints.
- disabled and expired credentials fail with machine-readable errors before secret resolution.
- usage CLI can now print credential audit events through `api2agent usage --credential-audit`.
- credential audit output uses an allowlist and groups credential-related failures.
- authenticated proxy credential dogfood passed against the real `https://httpbin.org/bearer` API.
- the local BYOK loop now covers config credential resolution, auth injection, usage ledger, and audit CLI.
- strategic priority increased for owning real execution data and minimizing API/provider onboarding cost.
- location-aware execution is now a Phase 6+ routing requirement; see `docs/en-US/LOCATION_AWARE_ROUTING.md`.
- usage events and SQLite storage now support optional region and latency breakdown fields.
- provider candidates now support `regions` and `geo_affinity`.
- `DecisionDatasetRecord` defines the first local decision dataset contract.
- `region_aware_latency` routing strategy now ranks providers by client-region affinity and latency metrics.
- `api2agent route` and `api2agent call` now accept `--client-region`.
- routing decisions now persist `client_region` for audit and decision-dataset use.
- `run_region_aware_routing_benchmark` now returns a routing decision and decision-dataset record.
- route/call now load aggregate plus matching client-region metrics for `region_aware_latency`.
- routing decisions now persist deterministic `selected_provider_region`.
- generated package usage events now record derived `provider_region`.
- credential resolver dogfood completed; see `docs/en-US/CREDENTIAL_RESOLVER_DOGFOOD_REPORT.md`.
- proxy credential injection dogfood completed; see `docs/en-US/PROXY_CREDENTIAL_INJECTION_DOGFOOD_REPORT.md`.
- proxy credential config dogfood completed; see `docs/en-US/PROXY_CREDENTIAL_CONFIG_DOGFOOD_REPORT.md`.
- credential policy dogfood completed; see `docs/en-US/CREDENTIAL_POLICY_DOGFOOD_REPORT.md`.
- credential scope dogfood completed; see `docs/en-US/CREDENTIAL_SCOPE_DOGFOOD_REPORT.md`.
- credential lifecycle dogfood completed; see `docs/en-US/CREDENTIAL_LIFECYCLE_DOGFOOD_REPORT.md`.
- credential audit CLI dogfood completed; see `docs/en-US/CREDENTIAL_AUDIT_CLI_DOGFOOD_REPORT.md`.
- authenticated proxy credential dogfood completed; see `docs/en-US/AUTHENTICATED_PROXY_CREDENTIAL_DOGFOOD_REPORT.md`.
- location-aware schema dogfood completed; see `docs/en-US/LOCATION_AWARE_SCHEMA_DOGFOOD_REPORT.md`.
- Go Data Plane durable event ingestion completed; see `docs/en-US/GO_DATAPLANE_DURABLE_EVENTS_DOGFOOD_REPORT.md`.
- Go Data Plane real external provider retry dogfood completed; see `docs/en-US/GO_DATAPLANE_REAL_EXTERNAL_PROVIDER_RETRY_DOGFOOD_REPORT.md`.
- Go Data Plane stage review completed; see `docs/en-US/GO_DATAPLANE_STAGE_REVIEW.md`.

Implementation checklist:

1. Credential data models - complete
   - add `api2agent/credentials/models.py`
   - define `CredentialDefinition`, `CredentialSource`, `CredentialResolutionRequest`, `ResolvedCredential`, and `CredentialInjectionPatch`
   - validate `owner_type`, `auth_type`, `injection_mode`, and `source`
2. Local Credential Resolver - complete
   - add `api2agent/credentials/resolver.py`
   - resolve in this order: inline override, project config, environment variable, none
   - return a redacted credential reference and injection patch
3. Execution integration - complete
   - connect resolver to generated package / routing execution path
   - inject resolved credentials into provider requests
   - keep direct local mode working
4. Usage attribution - complete
   - write `credential_reference` into usage events
   - ensure raw secrets never enter usage event metadata, decision output, ledger output, or logs
5. Replay and masking behavior - complete
   - replay warns when required credentials cannot be resolved
   - replay can execute when credentials are resolvable
   - replay metadata remains redacted
6. Proxy-side credential injection - complete
   - generated runners send credential intent to the proxy
   - proxy resolves env-based credential intent and injects provider auth before forwarding
   - missing proxy credentials create failed usage events without calling the provider
   - proxy usage metadata stores redacted credential metadata only
7. Credential config loading for local proxy - complete
   - add JSON/YAML credential config loader
   - add `api2agent proxy --credential-config`
   - allow proxy resolver to use config credentials without credential intent in the payload
   - keep config credential secrets out of usage metadata
8. Credential precedence and ownership policy hardening - complete
   - expose deterministic credential precedence
   - prefer config credentials owned by the current `project_id`
   - fallback to local owner before raw config order
   - preserve owner metadata in redacted resolver output
9. Credential scope matching for capability and tool access - complete
   - support `provider:<id>`, `capability:<id>`, `tool:<id>`, `*`, and `*:*`
   - keep empty scope as unrestricted for the matching provider
   - return `credential_scope_denied` for out-of-scope credentials
   - prevent lower-precedence fallback after an out-of-scope higher-precedence credential
10. Credential rotation metadata and audit events - complete
   - add `status`, `expires_at`, and `rotation_hint` to credential definitions
   - return `credential_disabled` for disabled credentials
   - return `credential_expired` for expired credentials
   - preserve lifecycle fields in redacted resolver metadata
11. Credential audit reporting in usage CLI - complete
   - add `api2agent usage --credential-audit`
   - add JSON and text audit output
   - include `credential_reference`, selected metadata, and credential failure counts
   - omit non-allowlisted metadata such as `secret_value`
12. Authenticated proxy credential dogfood with a real API - complete
   - use credential config to authenticate a real provider request
   - verify provider receives Bearer auth
   - verify usage metadata and audit CLI remain secret-safe
   - record dogfood results in bilingual docs

Acceptance test set:

- resolver reads env credentials
- resolver reads config credentials
- inline credential override wins
- `auth_type=none` does not require credentials
- authenticated provider receives the injected header/query/body patch
- usage event contains `credential_reference`
- raw secret is absent from SQLite usage metadata
- replay reports missing credential clearly
- replay executes when the credential can be resolved
- proxy injects resolved credentials into forwarded requests
- proxy records missing credentials in the ledger without forwarding
- proxy loads config credentials and injects them without raw secret metadata
- resolver chooses inline over config over request credentials
- resolver chooses project-owned config credentials before local fallback
- resolver allows matching capability/tool scopes
- resolver rejects out-of-scope credentials without exposing raw secrets
- resolver rejects disabled and expired credentials with redacted metadata
- resolver records lifecycle audit metadata for accepted credentials
- usage CLI prints credential audit JSON without raw secrets
- usage CLI prints credential audit text without raw secrets
- authenticated real API dogfood returns provider `authenticated=true`
- credential audit CLI reports the real API event without raw token leakage

Next strategic design requirements:

- execute Go Data Plane Consolidation Hardening v0:
  - reusable Protocol v0.2 conformance validator
  - event write failure policy
  - runtime provider availability probe

## 8.7 Phase 5.7: Architecture Definition Phase

Status: active.

Goal:

Freeze the protocol and production architecture before adding more implementation.

Scope:

- Protocol v0.2 contract freeze
- Production Architecture RFC
- Control Plane vs Data Plane boundary
- data model finalization
- long-term runtime and language decision
- Python MVP migration path

Do not expand:

- no new Python runtime features
- no marketplace UI
- no billing
- no non-API capability source runtimes
- no hosted SaaS productization

Exit criteria:

- `docs/en-US/API2AGENT_PROTOCOL_V0_2_PLAN.md` is complete
- `docs/en-US/API2AGENT_PROTOCOL_V0_2.md` is complete
- `schemas/api2agent/v0.2/protocol.schema.json` is complete
- `docs/en-US/ARCHITECTURE_DEFINITION_PHASE.md` is complete
- `docs/en-US/PRODUCTION_ARCHITECTURE_RFC.md` is complete
- `docs/en-US/PYTHON_REFERENCE_MIGRATION_PLAN.md` is complete
- `docs/en-US/GO_DATA_PLANE_SKELETON_PLAN.md` is complete
- production architecture responsibilities are explicit
- Data Plane technology direction is chosen
- Control Plane technology direction is chosen

Current implementation gate:

```text
Go Data Plane Skeleton hardening - complete
Go Data Plane protocol conformance + retry/failover dogfood - complete
Go Data Plane env credential resolution skeleton - complete
Go Data Plane durable event ingestion - complete
Go Data Plane real external provider retry dogfood - complete
Go Data Plane Consolidation Hardening v0 - complete
Timeout Budget Semantics v0 - complete
Snapshot Freshness Gate v0 - complete
Project Quota Gate v0 - complete
Go Data Plane Credential Config v0 - complete
Go Data Plane Credential Audit Metadata v0 - complete
Execution Event Ordering / Attempt Correlation v0 - complete
Go Data Plane Milestone Closeout + Phase 6 Readiness Review - complete
Go Control Plane Minimum v0 - complete
Control Plane Registry Validation v0 - complete
Control Plane Snapshot Compatibility Gate v0 - complete
Control Plane Registry Store v0 - complete
Control Plane Snapshot Versioning Policy v0 - complete
Control Plane Snapshot Export Artifact v0 - complete
Control Plane Snapshot Distribution Stub v0 - complete
Control Plane Snapshot Refresh / Reload Policy v0 - complete
Control Plane Snapshot Reload Failure Semantics v0 - complete
Control Plane Snapshot Reload Audit Events v0 - complete
Control Plane Snapshot Version Compatibility Guard v0 - complete
Control Plane Snapshot Strict Metadata Requirement v0 - complete
Control Plane Snapshot Metadata Manifest Consistency Guard v0 - complete
Control Plane Snapshot Artifact Content Digest Guard v0 - complete
Control Plane Snapshot Artifact Path Safety Guard v0 - complete
Control Plane Snapshot Distribution Atomic Publish Guard v0 - complete
Go Control Plane Snapshot Distribution Closeout + Phase Review - complete
Go Control Plane Service API Skeleton v0 - complete
Go Control Plane Service Snapshot Publish Endpoint v0 - complete
Go Control Plane Service API Closeout + Hosted Persistence Readiness Review - complete
Go Control Plane Persistent Registry Store Design v0 - complete
Control, Receipt, and Trust Layer Strategy - documented
Go Control Plane Persistent Registry Store Schema v0 - complete
Go Control Plane Persistence Phase Review - complete
Go Control Plane PostgresStore Load Parity v0 - complete
Go Control Plane Persistent Store Runtime Wiring v0 - complete
Go Control Plane Live Postgres Store Dogfood v0 - complete
Go Control Plane Persistent Export/Publish Audit Writes v0 - complete
Go Control Plane Persistent Store Failure Semantics Hardening v0 - complete
Go Control Plane Persistent Registry Mutation Boundary Review v0 - complete
API2Agent Tooling Re-entry Review + Tooling Expansion Plan v0 - complete
API2Agent Tooling Baseline Audit v0 - complete
API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0 - complete
Generated Package Region Metadata v0 - complete
Proxy-mode Credential Dogfood Expansion v0 - complete
Generated Package Latency Benchmark Helper v0 - complete
Endpoint-level Auth Inference v0 - complete
Base URL Override v0 - complete
Manual Write Test Path v0 - complete
Large Spec Performance v0 - complete
Better curl naming residual review v0 - complete
API2Agent Tooling Re-entry Closeout + Phase Review v0 - complete
API2Agent Stage Consolidation Before Import/Replace v0 - complete
Go Control Plane Persistent Registry Import/Replace Transaction Design v0 - complete
Go Control Plane Persistent Registry Import/Replace CLI Implementation v0 - complete
Go Control Plane Persistent Registry Import/Replace Live Postgres Dogfood v0 - complete
Go Control Plane Import/Replace Closeout + Mutation API Readiness Review v0 - complete
Go Control Plane Private Admin Import/Replace Endpoint Design v0 - complete
Go Control Plane Private Admin Import/Replace Endpoint Implementation v0 - complete
Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0 - complete
Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0 - complete
Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0 - complete
Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0 - complete
Go Control Plane Admin Mutation Idempotency Store Design v0 - complete
Go Control Plane Admin Mutation Idempotency Store Implementation v0 - complete
Go Control Plane Admin Mutation Idempotency Store Live Postgres Dogfood v0 - complete
Go Control Plane Admin Mutation Idempotency Store Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Identity Boundary Design v0 - complete
Go Control Plane Hosted Admin Identity Boundary Implementation v0 - complete
Go Control Plane Hosted Admin Identity Boundary Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Authenticator Integration Design v0 - complete
Go Control Plane Hosted Admin Authenticator Integration Implementation v0 - complete
Go Control Plane Hosted Admin Authenticator Integration Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Implementation v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Gateway Contract Harness Design v0 - complete
Go Control Plane Hosted Admin Gateway Contract Harness Implementation v0 - complete
Go Control Plane Hosted Admin Gateway Contract Harness Closeout + Phase Review v0 - complete
```

## 8.8 Phase 5.8: Tooling Re-entry Phase

Status: complete.

Closeout decision:

Tooling Re-entry can pause. The API-first hardening backlog is closed, and the project can return to the previously paused Control Plane write-side design unless product requirements are updated first. See `docs/en-US/API2AGENT_TOOLING_REENTRY_CLOSEOUT_REVIEW.md`.

Goal:

Return to the API2Agent Tooling Layer after the Control/Data Plane foundation work, without regressing into a one-shot generator.

Product goals:

- more real execution data
- lower API/provider onboarding cost
- faster Agent API responses

Scope:

- OpenAPI reliability
- curl reliability
- generated package observability defaults
- real API dogfood harness
- speed and region readiness

Hard constraints:

- API-first only
- no workflow engine
- no non-API runtime expansion
- no marketplace
- no billing
- no vault
- preserve proxy, usage, credential, replay, shadow, golden trace, and Protocol v0.2 compatibility

Completed re-entry result:

- Tooling re-entry is approved as a planned return to the top of the funnel.
- The Tooling Layer is now explicitly responsible for feeding the execution/data flywheel.
- Control Plane mutation API work remains paused.
- See `docs/en-US/API2AGENT_TOOLING_REENTRY_REVIEW_AND_EXPANSION_PLAN.md`.
- Tooling baseline audit is complete:
  - 4/4 curl inputs generated successfully.
  - 4/4 curl inputs achieved first successful direct execution.
  - 3/3 no-auth proxy paths achieved first successful proxy execution.
  - GitHub REST OpenAPI generated successfully but produced 1186 tools unfiltered.
  - filtering the GitHub REST spec to `/repos/{owner}/{repo}` produced 3 tools.
  - see `docs/en-US/API2AGENT_TOOLING_BASELINE_AUDIT_REPORT.md`.
- OpenAPI filtering + curl tool naming hardening is complete:
  - root-path curl tools now include capability intent, e.g. `get_ipify_public_ip` instead of `get`.
  - non-root curl naming remains path-based for backward compatibility.
  - OpenAPI generation warns when a package still contains more than 50 tools.
  - bounded generation through existing filters remains unchanged.
  - see `docs/en-US/API2AGENT_OPENAPI_FILTERING_CURL_NAMING_HARDENING_REPORT.md`.
- Generated Package Region Metadata v0 is complete:
  - `api2agent generate --provider-region` writes `provider_region` and `provider_regions` into generated `capability.json`.
  - generated README files document provider-region intent and runtime override.
  - generated runners include `provider_region` in proxy payloads.
  - `API2AGENT_PROVIDER_REGION` can override generated metadata at runtime.
  - see `docs/en-US/API2AGENT_GENERATED_PACKAGE_REGION_METADATA_REPORT.md`.
- Proxy-mode Credential Dogfood Expansion v0 is complete:
  - generated authenticated packages can execute through local proxy mode using local credential config.
  - generated packages send credential intent without provider secrets.
  - proxy usage events record `credential_reference` and redacted credential metadata without raw secret leakage.
  - the dogfood remains local and does not introduce a credential vault.
  - see `docs/en-US/API2AGENT_PROXY_CREDENTIAL_DOGFOOD_EXPANSION_REPORT.md`.
- Generated Package Latency Benchmark Helper v0 is complete:
  - `run_generated_package_latency_benchmark` measures generated package direct/proxy loops.
  - `api2agent benchmark-package` exposes p50/p95 latency output for generated tools.
  - proxy benchmark runs preserve usage event ids and provider-region metadata.
  - see `docs/en-US/API2AGENT_GENERATED_PACKAGE_LATENCY_BENCHMARK_REPORT.md`.
- Endpoint-level Auth Inference v0 is complete:
  - OpenAPI document-level auth remains the capability default.
  - operation-level `security: []` now marks public tools as no-auth.
  - operation-level bearer/API key security can override the capability default.
  - generated runners and proxy credential intent are tool-aware.
  - local credential resolution can select endpoint-matching config credentials for mixed-auth providers.
  - see `docs/en-US/API2AGENT_ENDPOINT_AUTH_INFERENCE_REPORT.md`.
- Base URL Override v0 is complete:
  - generated runners support `API2AGENT_BASE_URL` for package-wide runtime override.
  - generated runners support `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>` for tool-specific override.
  - invalid overrides fail fast before provider forwarding.
  - base path prefixes such as `/v1` are preserved when joining base URL and tool path.
  - direct and proxy execution share the same URL resolution semantics.
  - see `docs/en-US/API2AGENT_BASE_URL_OVERRIDE_REPORT.md`.
- Manual Write Test Path v0 is complete:
  - generated packages include `manual_write_test.py` for explicit write/delete checks.
  - default `api2agent test` remains read-only and never executes write/delete tools.
  - `api2agent test --allow-write` injects `API2AGENT_ALLOW_WRITE_TEST=1` before running the manual test.
  - direct and proxy opt-in write tests preserve usage, credential, provider-region, and estimated-cost metadata.
  - see `docs/en-US/API2AGENT_MANUAL_WRITE_TEST_PATH_REPORT.md`.
- Large Spec Performance v0 is complete:
  - OpenAPI filters are applied during parsing for tag/path/operation/max-tools selection.
  - `api2agent inspect` prints tool count, safety summary, top tags, top path prefixes, and large-package hints.
  - `api2agent test --tool ... --params ...` can run a selected generated read tool.
  - local 1200-operation dogfood verified unfiltered warnings, bounded generation, inspect truncation, and targeted tool testing.
  - see `docs/en-US/API2AGENT_LARGE_SPEC_PERFORMANCE_REPORT.md`.
- Better curl naming residual review v0 is complete:
  - generic leading curl host labels such as `api` and `www` no longer produce vague default capability names.
  - `api.github.com` now generates `github_api` and `GITHUB_API_TOKEN`.
  - explicit `--name` still wins.
  - non-root path tools remain path-based for backward compatibility.
  - see `docs/en-US/API2AGENT_CURL_NAMING_RESIDUAL_REVIEW.md`.
- API2Agent Tooling Re-entry Closeout + Phase Review v0 is complete:
  - Tooling Re-entry acceptance criteria are reviewed and passed.
  - remaining risks are documented.
  - API-first and no-workflow-engine constraints remain explicit.
  - next task returns to Control Plane import/replace transaction design.
  - see `docs/en-US/API2AGENT_TOOLING_REENTRY_CLOSEOUT_REVIEW.md`.
- API2Agent Stage Consolidation Before Import/Replace v0 is complete:
  - Tooling, Go Data Plane, and Go Control Plane persistent read/audit primitives are consolidated.
  - import/replace entry gates are documented before design begins.
  - invariants for FileStore default, Postgres opt-in, snapshot handoff, credential metadata-only registry rows, and no workflow/marketplace/billing/vault scope are reaffirmed.
  - see `docs/en-US/API2AGENT_STAGE_CONSOLIDATION_BEFORE_IMPORT_REPLACE.md`.

Completed private admin endpoint design result:

- `POST /v1/admin/registry/import-replace` is the accepted private admin endpoint.
- the request body uses a wrapper object with `registry`, optional `source`, and reserved `dry_run=false`.
- `X-Request-ID` and `Idempotency-Key` are required for HTTP mutation requests.
- the endpoint is Postgres mutation only; file-store mode returns `REGISTRY_MUTATION_UNAVAILABLE`.
- response shape, request-size limit, error mapping, audit mapping, and required implementation tests are documented.
- snapshot export, publish, and Data Plane reload remain separate.
- see `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`.

Completed import/replace snapshot propagation result:

- The E2E dogfood started Control Plane and Data Plane locally.
- HTTP import/replace changed the persistent registry provider from `ipify_public_ip_v1` to `httpbin_public_ip_v1`.
- Control Plane exported and published the replaced snapshot.
- Data Plane manually reloaded the published distribution.
- Data Plane execution returned replacement-provider output `{ "ip": "203.0.113.88" }`.
- Data Plane usage/decision records attributed `httpbin` / `httpbin_public_ip_v1` and `snapshot_propagation_httpbin_v2`.
- Persistent audit counts were asserted: `registry_revisions=4`, `snapshot_artifact_publications=2`, `admin_audit_events=5`, `providers=1`.
- See `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`.

Completed propagation closeout result:

- The import/replace snapshot propagation milestone can close.
- The write-side path is now proven from private admin HTTP mutation to Data Plane execution with the replaced provider.
- Data Plane still consumes immutable/versioned snapshots rather than mutable Control Plane tables.
- Remaining risks are idempotency persistence, hosted admin identity, manual propagation, blunt full replacement, local filesystem distribution, and conservative registry size limit.
- The next task is a design task for persistent admin mutation idempotency records.
- See `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`.

Next engineering task:

```text
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood Closeout + Phase Review v0
```

## 9. Phase 6: Hosted Control Plane

Status: hosted permission store read model live Postgres dogfood complete. Local Go Control Plane minimum, snapshot distribution, private import/replace, idempotency, hosted admin trusted gateway, local gateway contract harness, gateway permission-source proof, tenant partition validation, private project mutation endpoint, live dogfood closeout, durable permission-store boundary design, hosted permission-store contract harness and closeout, hosted permission-store schema, schema closeout, read model implementation, read model closeout, and read model live Postgres dogfood are complete.

Goal:

Move local proxy concepts into a hosted service.

Immediate local scope:

- local Go Control Plane model layer
- routing snapshot export consumed by the Go Data Plane
- local snapshot artifact and distribution lifecycle
- local Control Plane service API boundary
- project identity and admin authorization

Completed local entry slices:

```text
Go Control Plane Minimum v0
Go Control Plane Snapshot Distribution Closeout + Phase Review
Go Control Plane Service API Skeleton v0
Go Control Plane Service Snapshot Publish Endpoint v0
Go Control Plane Service API Closeout + Hosted Persistence Readiness Review
Go Control Plane Persistent Registry Store Design v0
Go Control Plane Persistent Registry Store Schema v0
Go Control Plane Persistence Phase Review
Go Control Plane PostgresStore Load Parity v0
Go Control Plane Persistent Store Runtime Wiring v0
Go Control Plane Live Postgres Store Dogfood v0
Go Control Plane Persistent Export/Publish Audit Writes v0
Go Control Plane Persistent Store Failure Semantics Hardening v0
Go Control Plane Persistent Registry Mutation Boundary Review v0
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
Go Control Plane Persistent Registry Import/Replace CLI Implementation v0
Go Control Plane Persistent Registry Import/Replace Live Postgres Dogfood v0
Go Control Plane Import/Replace Closeout + Mutation API Readiness Review v0
Go Control Plane Private Admin Import/Replace Endpoint Design v0
Go Control Plane Private Admin Import/Replace Endpoint Implementation v0
Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0
Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0
Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0
Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0
Go Control Plane Admin Mutation Idempotency Store Design v0
Go Control Plane Admin Mutation Idempotency Store Implementation v0
Go Control Plane Admin Mutation Idempotency Store Live Postgres Dogfood v0
Go Control Plane Admin Mutation Idempotency Store Closeout + Phase Review v0
Go Control Plane Hosted Admin Identity Boundary Design v0
Go Control Plane Hosted Admin Identity Boundary Implementation v0
Go Control Plane Hosted Admin Identity Boundary Closeout + Phase Review v0
Go Control Plane Hosted Admin Authenticator Integration Design v0
Go Control Plane Hosted Admin Authenticator Integration Implementation v0
Go Control Plane Hosted Admin Authenticator Integration Closeout + Phase Review v0
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Closeout + Phase Review v0
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Implementation v0
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0
Go Control Plane Hosted Admin Gateway Contract Harness Design v0
Go Control Plane Hosted Admin Gateway Contract Harness Implementation v0
Go Control Plane Hosted Admin Gateway Contract Harness Closeout + Phase Review v0
Go Control Plane Hosted Admin Gateway Permission Source Design v0
Go Control Plane Hosted Admin Gateway Permission Source Implementation v0
Go Control Plane Hosted Admin Gateway Permission Source Closeout + Phase Review v0
Go Control Plane Tenant-Partitioned Registry Mutation Design v0
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness v0
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness Closeout + Phase Review v0
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Design v0
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Implementation v0
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Live Dogfood + Closeout v0
Go Control Plane Hosted Permission Store Design v0
Go Control Plane Hosted Permission Store Contract Harness v0
Go Control Plane Hosted Permission Store Contract Harness Closeout + Phase Review v0
Go Control Plane Hosted Permission Store Schema v0
Go Control Plane Hosted Permission Store Schema Closeout + Phase Review v0
Go Control Plane Hosted Permission Store Read Model v0
Go Control Plane Hosted Permission Store Read Model Closeout + Phase Review v0
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood v0
```

Next hosted-readiness slice:

```text
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood Closeout + Phase Review v0
```

This hosted-readiness closeout slice is now the immediate next project task because the real Postgres seeded proof has landed and needs phase review before runtime wiring is considered.

Scope:

1. Review whether the live Postgres dogfood satisfies the read-model acceptance criteria.
2. Confirm real schema constraints, seeded rows, pgx lookup, fail-closed cases, zero decision persistence, and secret-safe artifact output are sufficient for v0.
3. Identify remaining risks before gateway runtime wiring or decision persistence.
4. Keep public auth provider implementation, production gateway deployment, gateway runtime wiring, decision persistence, and public management surfaces out of scope.
5. Do not implement automatic publish/reload, vault, billing, marketplace, workflow, or provider onboarding.

Exit criteria:

- live Postgres dogfood can close, or blockers are documented.
- policy version/fingerprint/decision id evidence remains accepted as secret-safe.
- runtime wiring and persistence boundaries remain explicit and deferred.
- gateway runtime wiring remains deferred.
- no granular CRUD API, OAuth/OIDC, vault, billing, marketplace, workflow, provider onboarding, production gateway deployment, or automatic propagation work is included.

References:

- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_LIVE_POSTGRES_DOGFOOD_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_PRIVATE_ENDPOINT_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_PRIVATE_ENDPOINT_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_PRIVATE_ENDPOINT_LIVE_DOGFOOD_CLOSEOUT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_LIVE_POSTGRES_DOGFOOD_REPORT.md`
- `docs/en-US/API2AGENT_HOSTED_CONTROL_PLANE_PAUSE_AND_AGENT_COMPILER_REENTRY.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_WORLD_HARDENING_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_DESIGN.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_FINAL_REENTRY_CLOSEOUT_CONSOLIDATION_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`

Completed tenant-partitioned registry mutation contract harness closeout result:

- the local partition validation helper is accepted as sufficient for v0.
- same-project, cross-project, global/platform, provider ownership, invalid registry, and project-scoped idempotency cases satisfy the design acceptance criteria.
- no HTTP endpoint, public CRUD, production gateway deployment, automatic propagation, or Data Plane mutable-table reads were added.
- remaining risks are endpoint wiring, audit persistence, first-class provider ownership, project row policy, durable permissions, and manual propagation.
- the next task is private hosted project mutation endpoint design.
- See `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`.

Completed tenant-partitioned registry mutation contract harness result:

- local partition validation helper `ValidateProjectPartitionMutation` is implemented.
- same-project project/API key/credential metadata changes pass.
- cross-project, global routing, snapshot config, capability, provider ownership, and platform-owned provider changes fail with stable partition errors.
- project-owned provider metadata changes are allowed only when ownership metadata matches the principal project.
- project-scoped idempotency fingerprint evidence is covered in tests.
- no HTTP endpoint, public CRUD, production gateway deployment, automatic propagation, or Data Plane mutable-table reads were added.
- See `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`.

Completed tenant-partitioned registry mutation design result:

- project partition ownership rules are explicit.
- global/platform read-only objects remain protected from project-scoped mutation.
- provider ownership is identified as a schema/metadata gap before project-owned provider mutation.
- partition diff validation is designed as a pre-commit gate before full-registry replacement.
- idempotency, audit evidence, snapshot boundaries, and failure semantics are defined.
- the next task is a local contract harness for the partition rules, not public CRUD.
- See `docs/en-US/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_DESIGN.md`.

Completed hosted admin gateway permission source closeout result:

- the permission-source implementation slice can close.
- static dogfood policy is accepted as a v0 trust-boundary proof, not production auth.
- gateway-local denial creates no Control Plane audit/idempotency rows.
- the Control Plane trusted-gateway authenticator remains a second gate and rejects insufficient trusted permissions.
- the next highest-risk hosted lane is tenant-partitioned registry mutation design.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_CLOSEOUT_PHASE_REVIEW.md`.

Completed hosted admin gateway permission source implementation result:

- gateway-side permission decisions are implemented in the local contract harness.
- static policy resolves public principals into trusted project-scoped roles and permissions.
- missing/invalid public auth, permission source unavailable, route/method mismatch, and public authz denial fail locally before forwarding.
- the Control Plane trusted-gateway authenticator remains a second gate and rejects forced insufficient trusted permissions with `AUTHZ_DENIED`.
- live dogfood passed with trusted audit/idempotency evidence and no raw public token or gateway secret leakage.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_IMPLEMENTATION_REPORT.md`.

Completed hosted admin gateway permission source design result:

- gateway-side permission source contract is defined.
- static dogfood policy maps public principals to trusted roles and permissions.
- endpoint permission mapping and fail-closed semantics are specified.
- audit/idempotency evidence and local harness dogfood expectations are defined.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_DESIGN.md`.

Completed Agent capability compiler final re-entry closeout result:

- the compiler re-entry scope is accepted as 100% complete.
- future compiler work is moved to evidence-triggered backlog.
- the next project lane returns to hosted Control Plane permission-source design.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_FINAL_REENTRY_CLOSEOUT_CONSOLIDATION_REVIEW.md`.

Completed Agent capability compiler OpenAPI cached real-spec corpus expansion closeout result:

- one required cached public-spec case is accepted as sufficient for v0.
- adding more cached specs is deferred until after final compiler consolidation.
- Agent Capability Compiler completion estimate is 99%.
- the next task is final compiler re-entry consolidation.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler OpenAPI cached real-spec corpus expansion implementation result:

- a committed Apache-2.0 Petstore excerpt is included in the default calibration manifest.
- cached source metadata, checksum validation, path containment, and additive result fields are implemented.
- local calibration now reports 5 pass, 2 warn, 0 fail, and 1 skipped.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler OpenAPI cached real-spec corpus expansion design result:

- source criteria, licensing/cache metadata, redaction policy, artifact layout, manifest changes, metrics, thresholds, tests, and dogfood expectations are defined.
- normal calibration remains offline and deterministic.
- the next compiler hardening task is cached real-spec corpus expansion implementation.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_DESIGN.md`.

Completed Agent capability compiler OpenAPI generic example reduction closeout result:

- deterministic name-aware fallbacks are accepted as complete.
- default generated calibration cases now report zero generic examples and empty generic first-call params.
- Agent Capability Compiler completion estimate is 98%.
- the next confidence gap is cached real-spec corpus expansion design.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler OpenAPI generic example reduction implementation result:

- name-aware parameter/property examples, secret-safe placeholders, numeric/name fallbacks, calibration generic example metrics, regression coverage, and dogfood reducing default calibration generic first-call params to zero are implemented.
- the full Python suite passed with 217 tests.
- the follow-up closeout is now complete.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler OpenAPI generic example reduction design result:

- deterministic name-aware fallback rules, priority preservation for source/schema hints, object field context threading, calibration generic example metrics, tests, dogfood, and non-goals are defined.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_DESIGN.md`.

Completed Agent capability compiler OpenAPI summary noise reduction closeout result:

- v0 summary budgets are accepted as sufficient for the current corpus.
- remaining risks are opinionated text-output budgets, large README tool sections, advisory repeated diagnostic groups, generic first-call params, and fixture-heavy corpus coverage.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler OpenAPI summary noise reduction implementation result:

- compact inspect aggregate rendering, representative response previews, line clipping, grouped diagnostics text, README package overview/key caveats, calibration summary-density metrics, regression coverage, and dogfood are implemented.
- the full Python suite passed with 213 tests.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler OpenAPI summary noise reduction design result:

- noise taxonomy, bounded summary budgets, risk-first rendering order, repeated finding folding, README/inspect/diagnostics text effects, calibration summary-density metrics, tests, dogfood, and non-goals are defined.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_DESIGN.md`.

Completed Agent capability compiler diagnostics score calibration closeout result:

- the calibrated score profile is accepted as complete.
- remaining risks are action-cap calibration on broader real specs, heuristic score semantics, summary noise, generic examples, and fixture-heavy corpus coverage.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler diagnostics score calibration implementation result:

- diagnostics scoring now uses an explicit impact profile, score breakdown, metadata cap, repeated action-finding cap, and readiness zero-penalty handling.
- real-spec calibration improved from 1 pass / 5 warn to 4 pass / 2 warn, while write-heavy and large-surface cases remain visible warnings.
- the full Python suite passed with 212 tests.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler diagnostics score calibration design result:

- scoring weakness, compatibility strategy, impact classes, initial mapping, score formula, metadata cap, score breakdown, calibration expectations, tests, dogfood, and non-goals are defined.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_DESIGN.md`.

Completed Agent capability compiler OpenAPI real-spec calibration harness closeout result:

- the local calibration harness is accepted as complete.
- the first evidence-driven next gap is diagnostics score calibration for metadata-rich packages.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler OpenAPI real-spec calibration harness implementation result:

- local offline calibration script, purpose-labeled corpus cases, machine-readable result artifact, status classification, fixture/synthetic-large coverage, and dogfood are implemented.
- the full Python suite passed with 210 tests.
- the next compiler hardening task is real-spec calibration harness closeout.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler OpenAPI real-spec calibration design result:

- calibration-after-keyword-coverage rationale, corpus slots, metric contract, status thresholds, harness behavior, artifact strategy, tests, dogfood, and non-goals are defined.
- the next compiler hardening task is a local real-spec calibration harness implementation.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_DESIGN.md`.

Completed Agent capability compiler OpenAPI JSON Schema keyword coverage closeout result:

- bounded keyword coverage is accepted as complete.
- remaining risks are bounded keyword semantics, heuristic examples, summary density, advisory diagnostics, and OpenAPI 3.1 dialect nuance.
- the next compiler hardening task is OpenAPI real-spec calibration design.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler OpenAPI JSON Schema keyword coverage implementation result:

- compact keyword summaries, deterministic keyword-hint examples, inspect schema hint counts, diagnostics, fixture coverage, and local dogfood are implemented.
- raw schema compatibility remains intact, and Tier 2 advanced keywords are diagnosed rather than treated as validator semantics.
- the full Python suite passed with 205 tests.
- the next OpenAPI hardening task is JSON Schema keyword coverage closeout.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler OpenAPI JSON Schema keyword coverage design result:

- current keyword coverage baseline and gaps are documented.
- Tier 1 display/example keywords, Tier 2 diagnostics-only keywords, compatibility strategy, generated artifact effects, tests, dogfood, and non-goals are defined.
- the next OpenAPI hardening task is JSON Schema keyword coverage implementation.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_DESIGN.md`.

Completed Agent capability compiler OpenAPI response shape documentation closeout result:

- response shape documentation is accepted as complete.
- remaining risks are documentation-only content negotiation, unvalidated source examples, advisory diagnostics, no runtime output validation, and partial JSON Schema keyword coverage.
- the next OpenAPI hardening task is JSON Schema keyword coverage design.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler OpenAPI response shape documentation implementation result:

- additive response metadata, deterministic content selection, README/inspect response summaries, diagnostics, fixture coverage, and local dogfood are implemented.
- generated runner behavior remains unchanged, and old capability JSON without response metadata remains valid.
- local response-shape dogfood passed, and the full Python suite passed with 201 tests.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler OpenAPI response shape documentation design result:

- current response documentation baseline and gaps are documented.
- additive response metadata, extraction rules, status categories, README/inspect summaries, diagnostics, tests, dogfood, and non-goals are defined.
- the next OpenAPI hardening task is response shape documentation implementation.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_DESIGN.md`.

Completed Agent capability compiler OpenAPI discriminator handling implementation result:

- discriminator-aware schema summaries, mapping-driven examples, schema hints, diagnostics, and tool schema preservation are implemented.
- discriminator fixture and parser/generator/diagnostics/CLI regression tests are added.
- local discriminator dogfood passed, and the full Python suite passed with 197 tests.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler OpenAPI discriminator handling closeout result:

- discriminator handling is accepted as complete.
- remaining risks are pragmatic branch matching, bounded mapping resolution, sparse response documentation, advisory diagnostics, and no runtime branch validation.
- the next OpenAPI hardening task is response shape documentation design.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler OpenAPI discriminator handling design result:

- current discriminator baseline and gaps are documented.
- compatibility strategy, extraction rules, summary formatting, deterministic example rules, generated artifact effects, diagnostics, tests, dogfood, and non-goals are defined.
- the next OpenAPI hardening task is discriminator handling implementation.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_DESIGN.md`.

Completed Agent capability compiler OpenAPI schema shaping closeout result:

- schema shaping is accepted as complete.
- generated Agent-facing inputs are clearer for nullable, map, array, polymorphic, and optional object shapes.
- remaining risks are discriminator metadata not yet used, response shaping depth, intentional partial JSON Schema coverage, advisory diagnostics, and bounded rather than semantic simplification.
- the next OpenAPI hardening task is discriminator handling design.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler OpenAPI schema shaping implementation result:

- direction-aware schema helpers are implemented without required IR changes.
- generated README, inspect, OpenAI tools schema, examples, and diagnostics now use shaped schema summaries and request-body filtering.
- nullable, readOnly/writeOnly, additionalProperties, array, polymorphism, and required/optional cases are covered by fixtures and regression tests.
- local schema-shaping dogfood passed, and the full Python suite passed with 193 tests.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler OpenAPI schema shaping design result:

- current schema handling baseline and gaps are documented.
- direction-aware request/response shaping rules are defined.
- nullable, readOnly/writeOnly, additionalProperties, array, polymorphism, and required/optional field policies are defined.
- generated README, tools schema, examples, inspect, diagnostics, tests, and dogfood expectations are defined.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_DESIGN.md`.

Completed Agent capability compiler OpenAPI real-world hardening design result:

- examples/defaults propagation is selected as the first OpenAPI hardening implementation slice.
- current parser baseline and gaps are documented.
- additive IR fields and deterministic example selection order are specified.
- generated README/test params, diagnostics evidence, tests, and dogfood expectations are defined.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_WORLD_HARDENING_DESIGN.md`.

Completed Agent capability compiler quality diagnostics closeout result:

- quality diagnostics is accepted as complete.
- deterministic diagnostics now provides a feedback layer for generated package quality.
- remaining risks are real-spec calibration, advisory-only diagnostics, shallow schema quality, and broader OpenAPI complexity.
- next compiler expansion task is OpenAPI real-world hardening design.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_CLOSEOUT_PHASE_REVIEW.md`.

Completed Agent capability compiler quality diagnostics implementation result:

- generated packages now write additive `diagnostics.json`.
- diagnostics can be recomputed from old packages with `api2agent diagnose`.
- generation, README, and inspect surfaces expose compact diagnostics summaries.
- deterministic findings cover usability, safety, auth, schema, execution, and observability risks.
- tests and local dogfood passed.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`.

Completed Agent capability compiler expansion design result:

- quality diagnostics is selected as the first compiler expansion implementation slice.
- the design covers generate, diagnose, and inspect workflows.
- `diagnostics.json`, finding ids, severity/status semantics, scoring, tests, and dogfood are defined.
- implementation remains API-first and does not introduce workflow, marketplace, vault, billing, hosted public CRUD, or production gateway work.
- See `docs/en-US/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`.

Completed hosted Control Plane pause + Agent compiler re-entry result:

- deeper hosted Control Plane work is paused at a credible boundary.
- hosted permission-source design moves to the hosted-readiness backlog.
- the immediate next project task returns to API-first Agent capability compiler expansion.
- recommended expansion tracks are capability quality diagnostics, OpenAPI real-world hardening, curl instant onboarding, and observable execution defaults.
- See `docs/en-US/API2AGENT_HOSTED_CONTROL_PLANE_PAUSE_AND_AGENT_COMPILER_REENTRY.md`.

Completed hosted admin gateway contract harness closeout result:

- the local gateway contract proof is accepted as complete.
- public header stripping and trusted claim injection are dogfooded through a real gateway hop.
- audit/idempotency evidence uses harness-injected identity and remains secret/token-safe.
- remaining risks are static public auth, static permission policy, production gateway deployment, tenant-partitioned mutation, and manual propagation.
- next hosted-readiness task is permission-source design, but immediate project focus has shifted back to the compiler.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`.

Completed hosted admin gateway contract harness implementation result:

- local dogfood-only gateway harness is implemented.
- public bearer auth is consumed locally and trusted `X-API2Agent-*` headers are stripped and re-injected.
- dogfood requests reach private Control Plane admin endpoints through the harness.
- audit/idempotency evidence uses harness-injected identity and gateway key id.
- raw public bearer tokens and the raw gateway secret are absent from evidence/report artifacts.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`.

Completed hosted admin gateway contract harness design result:

- local gateway harness responsibilities are explicit.
- static public auth and identity policy are explicit.
- public header stripping matrix is explicit.
- trusted claim injection and request/idempotency propagation are explicit.
- negative spoofing and dogfood evidence requirements are named.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_DESIGN.md`.

Completed hosted trusted-gateway production boundary closeout result:

- Control Plane-side production boundary mechanics can close.
- active secret rotation and gateway key-id evidence are implemented and dogfooded.
- remaining gateway contract, public auth, permission-source, deployment, and tenant-partitioning risks are documented.
- next highest-signal task is gateway contract harness design.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`.

Completed hosted trusted-gateway production boundary implementation result:

- rotation-compatible active gateway secrets are implemented.
- legacy single-secret configuration remains compatible.
- optional gateway key-id evidence is carried into audit and import/replace metadata.
- live dogfood verifies old/new overlap, removed old-secret rejection, new-secret mutation, key-id evidence, and secret-safe metadata.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`.

Completed hosted trusted-gateway production boundary design result:

- gateway-to-Control-Plane trust boundary is explicit.
- trusted header strip/rewrite rules are explicit.
- gateway secret rotation approach is explicit.
- permission issuance assumptions are explicit.
- audit/idempotency evidence contract is explicit.
- deployment and observability expectations are explicit.
- implementation tests and dogfood requirements are named.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_DESIGN.md`.

Completed hosted trusted-gateway service dogfood closeout result:

- the Control Plane-side hosted trusted-gateway admin path can pause.
- service dogfood acceptance criteria passed against real HTTP and live Postgres.
- import/replace audit metadata now includes hosted principal evidence.
- remaining production gateway, secret rotation, permission-source, header-stripping, and tenant-partitioning risks are documented.
- next highest-signal task is production gateway boundary design.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_CLOSEOUT_PHASE_REVIEW.md`.

Completed hosted trusted-gateway service dogfood result:

- the Control Plane service starts in hosted/trusted-gateway mode without `--admin-token`.
- real HTTP validation returned `200` with trusted gateway headers.
- missing gateway authorization returned `401 AUTH_ERROR`.
- missing endpoint permission returned `403 AUTHZ_DENIED`.
- Postgres audit rows preserve trusted actor, subject, project, organization, auth method, token id, and `local_private=false`.
- Postgres idempotency rows use trusted gateway project and actor scope.
- import/replace audit metadata was fixed to include hosted principal evidence.
- See `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`.

Completed propagation closeout result:

- the import/replace snapshot propagation milestone can close.
- private admin HTTP mutation through Data Plane execution with the replaced provider is proven.
- Data Plane continues to consume immutable/versioned snapshots instead of mutable Control Plane tables.
- next highest-signal gap is durable idempotency semantics for admin mutations.
- See `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`.

Completed propagation dogfood result:

- podman-backed Postgres, Control Plane service, Data Plane service, and local httpbin-like replacement provider were started by the dogfood script.
- Data Plane initially loaded `snapshot_propagation_ipify_v1`.
- HTTP import/replace changed the persistent registry provider to `httpbin_public_ip_v1`.
- Control Plane exported and published `snapshot_propagation_httpbin_v2`.
- Data Plane manual reload moved from `snapshot_propagation_ipify_v1` to `snapshot_propagation_httpbin_v2`.
- Data Plane execution returned `{ "ip": "203.0.113.88" }`.
- usage and decision records attributed the replacement provider.
- See `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`.

Completed endpoint closeout result:

- private admin endpoint design, implementation, and live dogfood are complete.
- the write-side milestone can close.
- remaining risks are hosted auth maturity, idempotency cache absence, blunt full-registry replacement, manual snapshot propagation, and conservative request-size limit.
- next highest-signal proof is import/replace snapshot propagation into Data Plane execution.
- See `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_CLOSEOUT_PHASE_REVIEW.md`.

Completed live endpoint dogfood result:

- Live Postgres dogfood used podman.
- The service accepted `POST /v1/admin/registry/import-replace` with Postgres store wiring.
- Changed registry returned `201` and `noop=false`.
- Repeated same-registry import returned `200` and `noop=true`.
- Service validation and artifact export saw the replaced registry.
- Exported snapshot provider was `httpbin_public_ip_v1`.
- Persistent audit counts were `registry_revisions=3`, `admin_audit_events=4`, and `providers=1`.
- See `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_LIVE_POSTGRES_DOGFOOD_REPORT.md`.

Completed private admin endpoint implementation result:

- `POST /v1/admin/registry/import-replace` is registered.
- The handler requires admin auth, `X-Request-ID`, and `Idempotency-Key`.
- The handler accepts the documented wrapper request body and rejects `dry_run=true`.
- Postgres runtime wiring injects a narrow `RegistryImportReplacer`.
- FileStore/unconfigured mutation returns `409 REGISTRY_MUTATION_UNAVAILABLE`.
- changed registry returns `201`; same-fingerprint no-op returns `200`.
- mutation errors map to the stable service error envelope.
- `go test ./...` passes in `services/control-plane`.
- See `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_IMPLEMENTATION_REPORT.md`.

Completed private admin endpoint design result:

- The accepted endpoint is `POST /v1/admin/registry/import-replace`.
- The design requires a wrapper request body, `Authorization`, `X-Request-ID`, and `Idempotency-Key`.
- v0 rejects `dry_run=true`, oversized request bodies, invalid registries, and unconfigured/file-store mutation mode with stable error records.
- success/failure audit evidence remains owned by the registry import/replace primitive; the endpoint only passes identity metadata.
- Snapshot export/publish/reload remains a separate sequence.
- See `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`.

Completed import/replace closeout and mutation API readiness result:

- Local/admin CLI primitive satisfies the current write-side import/replace goal.
- The slice is ready to close.
- The project is ready to design a private admin import/replace endpoint.
- The project is not ready to implement the endpoint without a design step.
- Public CRUD, provider onboarding, vault, billing, settlement, and automatic snapshot reload remain out of scope.
- See `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_CLOSEOUT_MUTATION_API_READINESS_REVIEW.md`.

Completed live Postgres import/replace dogfood result:

- Podman provisioned a live Postgres-compatible database.
- Schema apply, seed, changed-registry import/replace, same-registry no-op, and snapshot export passed.
- First import returned `noop=false`; second import returned `noop=true`.
- Exported snapshot reflected `snapshot_import_replace_live_v1` and provider `httpbin_public_ip_v1`.
- Persistent audit counts were `registry_revisions=2`, `admin_audit_events=2`, and `providers=1`.
- See `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_LIVE_POSTGRES_DOGFOOD_REPORT.md`.

Completed import/replace CLI implementation result:

- `api2agent-controlplane import-replace-postgres` is implemented as a local/admin command.
- `ReplacePersistentRegistry` uses serializable transaction options and a transaction-scoped advisory lock.
- same-fingerprint import returns no-op and writes success audit only.
- changed registry replacement writes `registry_revisions` and success `admin_audit_events` in the same transaction.
- required success audit failure rolls back the mutation.
- no public write API was introduced.
- See `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_CLI_IMPLEMENTATION_REPORT.md`.

Completed import/replace transaction design result:

- The first write-side operation is limited to controlled full-registry import/replace.
- `seed-postgres` remains a dogfood helper, not the production mutation path.
- The accepted transaction uses serializable isolation plus `pg_try_advisory_xact_lock(22021, 1)`.
- Mutable registry tables are replaced as one validated graph; append-only evidence tables are not directly edited.
- Snapshot export/publish/reload remains a separate sequence after import/replace.
- See `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_TRANSACTION_DESIGN.md`.

Completed schema/load-parity result:

- Schema shape is testable locally without changing runtime defaults.
- File registry and persistent row mapping are proven against the existing fixture.
- Canonical registry ordering is covered by regression tests.
- `FileStore` remains the default runtime store.
- No hosted deployment, live database service, vault, billing, or marketplace work is included.
- See `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_STORE_SCHEMA_REPORT.md`.

Completed phase review result:

- Runtime persistence readiness is reviewed.
- API2Agent-first scope is reaffirmed.
- The next runtime persistence slice is narrowed to `PostgresStore.Load(ctx)` parity.
- See `docs/en-US/GO_CONTROL_PLANE_PERSISTENCE_PHASE_REVIEW.md`.

Completed PostgresStore load parity result:

- `PostgresStore.Load(ctx)` reads through a read-only `REPEATABLE READ` transaction.
- Persistent rows rebuild the same in-memory `Registry` shape used by `FileStore`.
- File and Postgres-loaded registries produce equivalent snapshot contract output in tests.
- Runtime store selection and live Postgres dogfood remain the next slice.
- See `docs/en-US/GO_CONTROL_PLANE_POSTGRES_STORE_LOAD_PARITY_REPORT.md`.

Completed runtime wiring result:

- `--registry-store file|postgres` and `--postgres-dsn` are wired into local commands.
- `seed-postgres` can import the file registry model into the persistent schema.
- `file` remains the default store.
- Live dogfood was completed with podman because this environment does not provide Docker or host `psql`.
- See `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_STORE_RUNTIME_WIRING_REPORT.md`.

Completed live Postgres dogfood result:

- Podman provisioned a temporary Postgres-compatible database.
- Schema apply, `seed-postgres`, snapshot export parity, CLI artifact export, service validation, and service artifact export passed.
- File-store and postgres-store snapshots matched exactly.
- See `docs/en-US/GO_CONTROL_PLANE_LIVE_POSTGRES_STORE_DOGFOOD_REPORT.md`.

Completed persistent export/publish audit result:

- Postgres runtime wiring now attaches a `PersistentAuditSink`.
- Service registry validation, artifact export, distribution publish, and current pointer reads write `admin_audit_events` when a persistent audit sink is configured.
- Successful artifact export writes `registry_revisions`.
- Successful distribution publish writes `snapshot_artifact_publications`.
- Live Postgres dogfood verified `admin_audit_events=4`, `registry_revisions=2`, and `snapshot_artifact_publications=1`.
- See `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_EXPORT_PUBLISH_AUDIT_REPORT.md`.

Completed persistent store failure semantics result:

- Postgres-backed registry load failures now return `PERSISTENT_STORE_READ_FAILED` with HTTP 503, platform scope, and retryable semantics.
- File-store load failures remain `REGISTRY_INVALID` with HTTP 400, caller scope, and non-retryable semantics.
- Successful admin operations fail closed with `AUDIT_WRITE_FAILED` when required persistent audit writes fail.
- Failure-path admin audit writes remain best-effort so original errors are preserved.
- See `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_STORE_FAILURE_SEMANTICS_REPORT.md`.

Completed persistent registry mutation boundary review result:

- Granular registry CRUD APIs are deferred.
- The next safe write-side path is a controlled full-registry import/replace transaction.
- Mutable registry state is limited to `projects`, `api_keys`, `capabilities`, `providers`, `credential_metadata`, `routing_policies`, and `snapshot_configs`.
- `registry_revisions`, `snapshot_artifact_publications`, and `admin_audit_events` remain append-only evidence surfaces.
- Transaction, audit, idempotency, failure, and rollback requirements are documented before implementation.
- See `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_MUTATION_BOUNDARY_REVIEW.md`.

Later hosted scope:

- hosted proxy endpoint
- durable database
- multi-project usage isolation
- hosted usage reporting
- basic credential vault

Hosted exit criteria:

- external user can route generated calls through hosted proxy
- hosted usage metrics are reliable
- credentials are not stored in generated files
- quota works per project

## 10. Phase 7: Economic Layer

Status: planned.

Goal:

Make usage measurable and future-billable without implementing payments, settlement, or marketplace economics too early.

Scope:

- pricing metadata
- free quota model
- estimated cost reporting
- routing-decision-linked usage ledger
- local usage ledger grouped by project/capability/provider
- plan/quota configuration
- billing-ready usage ledger

Exit criteria:

- every proxied call has cost metadata
- local ledger can report calls, success rate, latency, and estimated cost by capability/provider
- monthly usage can be calculated per project
- upgrade path from free quota to paid quota is technically clear

Do not expand:

- no revenue share settlement yet
- no full payment system before hosted usage is real

## 11. Phase 8: Capability Registry

Status: planned.

Goal:

Persist reusable capabilities and provider candidates.

Scope:

- capability registry
- provider candidate registry
- versioning
- quality metrics
- compatibility metadata
- install/search command

Exit criteria:

- users can reuse a registered capability
- multiple providers can be attached to one capability
- routing can read from registry instead of one-off JSON files

## 12. Far-Term Optional Direction: Agent Capability Marketplace

Status: far-term only, not an active implementation phase.

Goal:

Create a marketplace where Agents and Agent builders can discover capabilities, compare providers, and route calls using quality/cost/latency signals.

Scope:

- provider onboarding
- marketplace search
- pricing models
- billing
- revenue share
- trust and safety review
- public quality metrics

Exit criteria:

- providers compete for capability traffic
- users can choose capabilities based on observed metrics
- API2Agent can monetize usage, subscription, or revenue share

This direction must not start until API2Agent has a reliable compiler, proxy, metrics, routing, hosted control plane, registry, and billing-ready usage ledger.

## 13. Execution Rule

No phase should start major implementation until:

- the previous phase has passing tests
- the docs for the new phase are updated
- the acceptance criteria are explicit
- at least one dogfood scenario is defined

This rule exists to prevent the project from drifting into interesting but unplanned infrastructure.
