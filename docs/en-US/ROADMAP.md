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

Strategic thesis:

> API2Agent starts as a local Agent capability compiler, then becomes the control, metrics, routing, and reliable execution layer for Agent access to API-backed capabilities.

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

Not implemented yet:

- replay command
- shadow execution mode
- golden trace marker
- enforced capability naming rule
- endpoint-level auth
- base URL override
- manual write tests
- hosted proxy
- credential vault
- durable multi-project backend
- capability registry persistence
- billing

Explicitly out of current API2Agent scope:

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

- implement or explicitly design `api2agent replay`
- add the capability naming rule to validation/docs
- design `shadow` execution mode for benchmark-only provider calls
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

## 9. Phase 6: Hosted Control Plane

Status: planned.

Goal:

Move local proxy concepts into a hosted service.

Scope:

- hosted proxy endpoint
- project identity
- API keys for proxy access
- durable database
- multi-project usage isolation
- hosted usage reporting
- basic credential vault

Exit criteria:

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
