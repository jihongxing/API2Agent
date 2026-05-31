# API2Agent PRD

## 1. Product Vision

API2Agent is the neutral infrastructure for turning APIs into Agent-callable capabilities.

MVP is API-first. The long-term boundary is broader: any source that can be represented as `input -> execution -> output` may eventually become an Agent-callable capability through an adapter. See `docs/en-US/CAPABILITY_SOURCES.md`.

The project starts as an Agent capability compiler:

```text
OpenAPI / curl
  -> API2Agent IR
  -> capability package
  -> MCP server / tool runtime
```

The current product mandate is API2Agent itself:

- compile API descriptions into Agent capabilities
- execute generated capabilities reliably
- route calls through an observable control point
- collect success, cost, and latency data
- collect region-aware latency and routing data over time
- make capabilities comparable and routable
- maximize real execution data
- minimize API/provider onboarding cost
- keep API onboarding first while preserving future source-neutral capability execution

Current Tooling Re-entry goals:

- collect more real execution data
- reduce API/provider onboarding cost
- improve response-speed visibility for Agent API calls

Current Tooling Re-entry constraints:

- API-first implementation
- no workflow engine
- no non-API runtime expansion
- no marketplace, billing, or vault work
- preserve proxy, usage, credential, replay, shadow, golden trace, and Protocol v0.2 compatibility

The long-term product can become larger:

```text
Agent request
  -> Capability Layer
  -> Routing Layer
  -> Credential Orchestration
  -> API2Agent Proxy
  -> API-like capability execution unit
  -> metrics, quota, pricing
```

Marketplace is a far-term outcome, not the current product target.

## 2. Strategic Positioning

Old positioning:

> Turn any API into a verified Agent capability.

Current positioning:

> Build API2Agent: the capability compiler, proxy, metrics, and routing layer that lets Agents reliably use APIs.

v0.1-alpha positioning:

> A local Agent API execution and observability layer for reliable multi-provider API calls.

The alpha product hook is Reliability + Observability:

- fail over when a provider fails
- compare providers by success, cost, and latency
- compare providers by region-aware latency when location data exists
- keep a ledger of every attempt
- make failures replayable and debuggable

Strategic weight update:

- API2Agent should own the most real execution data.
- API2Agent should have the lowest possible API onboarding cost.
- API2Agent should make response speed visible and optimizable.
- These two goals are the flywheel that makes routing quality defensible.

API2Agent is not just "Stainless for Agents." Stainless helps humans call APIs through SDKs. API2Agent should help Agents choose and execute capabilities through a neutral infrastructure layer.

## 3. Core Thesis

The current winning product is not a marketplace.

The current winning product is API2Agent: a reliable Agent capability infrastructure layer.

The difference:

- API is implementation.
- Capability is intent.
- Metrics make candidates comparable.
- Routing turns metrics into decisions.
- Credentials define who has the right to call and whose resource is consumed.
- Economics can later turn usage into commercial products.

API2Agent must therefore evolve from generation to controlled execution.

## 4. Product Layers

### Layer 1: Tooling Layer

Converts API descriptions into runnable Agent tools.

Includes:

- OpenAPI/curl parser
- API2Agent IR
- tool filtering
- generated runner
- generated MCP server
- smoke test
- capability package

### Layer 2: Control Layer

Moves execution through API2Agent.

Includes:

- hosted proxy
- project identity
- API credential handling
- usage tracking
- quotas
- structured logs
- latency/success/failure measurement

### Layer 3: Economic Layer

Before economics, API2Agent needs a credential orchestration layer.

Includes:

- credential ownership
- credential resolution
- credential injection
- credential masking
- `credential_reference` in usage events
- BYOK, platform-key, provider-key, and no-credential modes

This is not payment. It is the permission and attribution layer required before payment can be trustworthy.

### Layer 3.5: Economic Layer

Makes usage chargeable later.

Includes:

- cost estimation
- pricing metadata
- free quotas
- usage records
- billing integration later
- provider revenue share later

Payment is not required now. Metering is required before payment.

### Layer 4: Capability Layer

Groups multiple implementations under the same semantic capability.

Example:

```text
Capability: text_to_speech
  Candidate: elevenlabs_tts
  Candidate: openai_tts
  Candidate: internal_voice_service
```

This layer makes APIs comparable.

### Layer 5: Routing Layer

Chooses the best candidate for a capability request.

Strategies:

- lowest cost
- lowest latency
- highest success rate
- balanced score
- failover
- quota-aware routing
- policy-aware routing
- future location-aware routing

Routing is the decision engine for API2Agent.

Location-aware routing is a future routing requirement, not a v0.1 requirement. It should model speed as:

```text
total_latency =
  network_rtt
  + provider_processing_latency
  + api2agent_overhead
```

See `docs/en-US/LOCATION_AWARE_ROUTING.md`.

### Layer 6: Far-Term Marketplace Layer

Allows capability providers to compete for Agent traffic. This is not part of the current build focus.

Marketplace emerges only when API2Agent has:

- multiple providers per capability
- observed metrics
- routing decisions
- pricing and quota rules
- trust and safety policies

## 5. Target Users

### Primary ICP: Agent Builders

They need:

- fast API-to-tool conversion
- reliable execution
- hosted proxy option
- usage visibility
- simple quotas
- a way to choose the best capability provider without hand wiring every API

### Secondary ICP: API Providers

They need:

- official Agent-ready capabilities
- usage and success metrics
- distribution to Agents
- revenue share later
- a model-neutral channel

### Future ICP: Agent Platforms

They need:

- capability discovery
- routing infrastructure
- policy controls
- capability registry access
- quality and cost signals

## 6. MVP Scope

The current MVP remains the Free Tooling Layer.

MVP goal:

> Convert OpenAPI/curl into a local capability package and prove at least one generated tool can be called.

Supported:

- REST JSON APIs
- OpenAPI JSON/YAML
- curl commands
- API key / Bearer token
- local runner
- MCP stdio server
- smoke test
- tool filtering

Not in current MVP:

- hosted proxy
- database
- billing
- marketplace UI
- routing
- OAuth
- multi-provider capability matching

But the architecture must not block the Control Layer.

## 7. Near-Term Product Upgrade

The next major product phase after local generation is not more input formats.

It is:

```text
generated tool -> API2Agent Proxy -> third-party API -> usage event
```

Minimum proxy MVP:

- generated packages can call an API2Agent proxy instead of direct API URLs
- proxy forwards requests to third-party APIs
- proxy records usage events
- usage events include success, status code, latency, tool id, capability id, provider id, estimated cost
- quota is enforced at project level

## 8. North Star Metrics

Early tooling metric:

> Time to First Successful Local Tool Call <= 3 minutes.

Long-term platform metric:

> Percentage of Agent API calls successfully routed through API2Agent with known cost, latency, and outcome.

Far-term marketplace metric:

> Capability fulfillment volume routed across competing providers.

Supporting metrics:

- first-call success rate
- generated tool count after filtering
- proxy call success rate
- p50/p95 latency
- estimated cost per successful call
- quota hit rate
- routing win rate by strategy
- provider success rate by capability

## 9. Core Data Objects

### API2Agent IR

Neutral description of API operations.

### Capability Package

Runnable local or hosted tool package.

### Capability

Semantic task that an Agent wants fulfilled.

### Provider Candidate

One implementation of a capability.

### Usage Event

A recorded execution attempt.

### Credential

The right to call a provider API, with ownership, injection, and safe usage attribution metadata.

### Metrics Snapshot

Aggregated success/cost/latency data for routing and far-term marketplace comparison.

### Routing Policy

Machine-readable decision strategy for choosing a provider candidate.

## 10. Business Model

Open-core split:

Open source:

- local compiler
- CLI
- local package generation
- local MCP/runtime templates
- basic tests

Commercial surface:

- hosted proxy
- hosted metrics
- quotas
- credential orchestration
- credential vault
- routing
- private registry
- marketplace distribution later
- billing and revenue share
- enterprise policy controls

Correct sequence:

```text
free tooling -> controlled usage -> metered usage -> paid usage -> far-term marketplace
```

## 11. Risks

### Risk: Remaining a One-Time Generator

If users call third-party APIs directly forever, API2Agent has no usage data, no routing power, and no economic layer.

Mitigation:

- design proxy mode early
- make hosted execution useful before billing
- make metrics visible to users

### Risk: Missing Credential Ownership

If API2Agent cannot say which credential was used and who owns it, usage data cannot become reliable quota, routing, billing, or marketplace data.

Mitigation:

- define Credential Schema v0.1
- build a local credential resolver
- inject credentials through proxy when possible
- keep raw secrets out of usage events and replay metadata

### Risk: Building Marketplace Too Early

A marketplace without routing and metrics is only a directory.

Mitigation:

- build proxy and metrics first
- then capability grouping
- then routing
- then marketplace

### Risk: Weak Capability Abstraction

If every endpoint is treated as unique, APIs cannot compete.

Mitigation:

- define Capability Schema v0.1
- map multiple providers into one capability
- collect comparable metrics

### Risk: Provider or Model Lock-In

Mitigation:

- API2Agent IR remains canonical
- MCP first, not MCP only
- provider-specific formats stay adapters

## 12. Success Criteria

MVP success:

- real APIs can generate usable local capability packages
- safe smoke tests run successfully
- generated MCP server can be called by an Agent runtime

Control Layer success:

- generated package can call through API2Agent Proxy
- proxy records usage events
- quota and latency/success metrics work

Capability Layer success:

- two or more providers can map to the same capability
- metrics are comparable

Routing Layer success:

- routing can choose between providers based on policy
- failover improves successful completion rate

Far-term marketplace success:

- providers compete for capability traffic
- Agents or Agent builders choose capabilities using observed quality, cost, and latency
