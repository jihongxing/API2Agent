# API2Agent Far-Term Economic Strategy

## 0. Scope Boundary

This is a long-term strategy document.

This document is not the active implementation roadmap. `ROADMAP.md` remains the source of truth for what gets built next.

The current product is API2Agent: compiler, capability package, proxy, metrics, routing, and reliable execution.

Marketplace is a far-term possible outcome. It is not the current product, MVP, or active implementation phase.

## 1. Strategic Correction

API2Agent is not only an API-to-tool converter.

The sharper thesis is:

> API2Agent is the entry layer for Agents to discover, choose, call, observe, and eventually pay for API-backed capabilities.

The product should evolve through this sequence:

```text
usable -> controllable -> measurable -> comparable -> routable -> reliable execution
```

Economic and marketplace work only becomes relevant after the API2Agent execution layer is reliable.

Do not jump directly from "free tooling" to "billing." The missing middle is control.

## 2. Correct Phase Logic

### Phase 1: Free Tooling Layer

Goal:

Make APIs callable by Agents quickly.

Core capabilities:

- OpenAPI/curl to tool schema
- API2Agent IR
- generated runner
- generated MCP server
- smoke test
- tool filtering

This phase creates adoption, not direct revenue.

### Phase 2: Control Layer

Goal:

Move the execution path through API2Agent.

Required capabilities:

- hosted proxy
- usage tracking
- success/failure tracking
- latency measurement
- cost estimation
- user/API/capability identity
- basic quotas

The important shift:

```text
Agent -> third-party API
```

becomes:

```text
Agent -> API2Agent Proxy -> third-party API
```

This creates the future right to meter, route, and charge.

### Phase 3: Billing Layer

Goal:

Turn controlled traffic into chargeable usage.

Possible pricing:

- developer subscription
- per-call usage billing
- quota upgrades
- team/enterprise plans
- API provider revenue share

Payment is not needed on day one, but the system must be designed so billing can be added without changing the execution path.

### Phase 4: Capability Layer

Goal:

Make APIs comparable.

An API endpoint is not a market object. A capability is.

Example:

```text
Capability: image_generation
  Candidate A: provider_api_a
  Candidate B: provider_api_b
  Candidate C: internal_workflow_c
```

Each candidate should expose:

- semantic capability definition
- input/output contract
- execution adapter
- observed success rate
- observed latency
- estimated cost
- pricing model
- safety and policy metadata

### Phase 5: Routing Layer

Goal:

Turn metrics into decisions.

Routing decides which candidate should satisfy a capability request.

Early policies:

- lowest cost
- lowest latency
- highest success rate
- balanced score
- failover on error
- quota-aware routing

This is the platform shift. API2Agent stops being a generation tool and starts deciding who receives Agent traffic.

### Phase 6: Capability Marketplace

Goal:

Create a marketplace where Agents can discover and invoke capabilities, and providers can compete to fulfill them.

A marketplace only emerges when three things exist:

- comparability: multiple providers mapped to the same capability
- selection: routing chooses between providers
- economics: calls have prices, quotas, and incentives

Marketplace is the result of capability abstraction plus routing plus economic rules. It is not just a directory of APIs.

## 3. Why API Market Is the Wrong Frame

Traditional API marketplaces are built for humans.

They expose:

- endpoints
- documentation
- pricing pages
- manual subscription flows

Agents need something different:

- semantic capability search
- machine-readable contracts
- observed quality metrics
- automatic provider selection
- safe execution
- metered usage

So API2Agent should target an Agent Capability Marketplace, not a conventional API marketplace.

## 4. Marketplace Object Model

### Capability

A semantic unit of work.

Example:

```json
{
  "name": "generate_marketing_poster",
  "description": "Generate an ecommerce marketing poster from product inputs.",
  "inputs": {},
  "outputs": {},
  "safety": "write"
}
```

### Provider Candidate

One implementation of a capability.

It can be:

- third-party API
- internal API
- hosted workflow
- multi-step tool chain

### Metrics

Observed execution data:

```json
{
  "success_rate": 0.92,
  "avg_latency_ms": 1200,
  "estimated_cost_per_call": 0.02,
  "p95_latency_ms": 2100
}
```

### Pricing

Economic contract:

```json
{
  "model": "per_call",
  "price": 0.02,
  "currency": "USD"
}
```

### Routing Policy

Decision rule:

```json
{
  "strategy": "balanced",
  "weights": {
    "success_rate": 0.5,
    "latency": 0.3,
    "cost": 0.2
  }
}
```

## 5. First Practical MVP Upgrade

Do not build a marketplace website yet.

Build the smallest control-plane path:

```text
Agent
  -> generated tool / MCP server
  -> API2Agent Proxy
  -> third-party API
  -> usage event
  -> metrics store
```

Minimum data to record:

- user id or local project id
- capability id
- tool id
- provider id
- request timestamp
- status code
- success/failure
- latency
- estimated cost
- error type

Minimum control:

- per-project quota
- read-only default safety
- proxy API key
- no payment system yet

## 6. Strategic Rule

The free product should create adoption, but it must not give up the future control point.

The rule is:

> Free capabilities are fine. Unobserved direct execution is not the future platform path.

Local generation can remain open source. Hosted proxy, metrics, routing, registry, marketplace, and billing can become the open-core commercial surface.
