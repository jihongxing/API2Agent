# API2Agent Core Concepts

## 1. What This Document Answers

This document explains the strategic model behind API2Agent. Marketplace is treated as a far-term outcome, not the current build target.

It answers:

- Why API2Agent is not just an API-to-tool generator
- What API2Agent IR is
- What a capability package is
- Why proxy and usage tracking matter
- What Capability Layer means
- What Routing Layer means
- Why marketplace does not emerge automatically from data

## 2. The Core Strategic Shift

API2Agent starts as:

> An Agent capability compiler.

But it should evolve into:

> The infrastructure layer for Agents to call, compare, route to, and reliably execute API-backed capabilities.

The short version:

```text
API2Agent IR = internal language
Capability Package = runnable delivery unit
Proxy = control point
Usage Metrics = decision fuel
Capability Layer = comparability
Routing Layer = decision engine
Marketplace = economic network
```

## 3. API2Agent IR

Plain language:

> API2Agent IR is the internal unified language that describes API operations in a provider-neutral way.

Inputs differ:

```text
OpenAPI
curl
Postman
GraphQL
API docs
SDK source
```

Outputs differ:

```text
MCP
OpenAI tools
Anthropic tools
Gemini function calling
TypeScript runtime
Hosted proxy route
```

IR prevents an `N * M` integration explosion.

Current IR describes:

- capability metadata
- auth
- tools
- parameters
- request body
- response shape
- safety level
- tags and operation ids

Future IR or adjacent platform metadata must also connect to:

- capability ids
- provider candidate ids
- pricing hints
- routing hints
- observability metadata

## 4. Capability Package

Plain language:

> A capability package is a runnable API tool package that an Agent runtime can actually use.

It contains:

- `capability.json`
- `tools.json`
- `runner.py`
- `mcp_server.py`
- `smoke_test.py`
- `auth.env.example`
- README and examples

Capability package is still important, but it is not the end-state. It is the packaging format that lets the system prove an API can be called.

## 5. Proxy

Plain language:

> Proxy is the control point that turns API2Agent from a generator into infrastructure.

Without proxy:

```text
Agent -> third-party API
```

API2Agent sees no traffic.

With proxy:

```text
Agent -> API2Agent Proxy -> third-party API
```

API2Agent can measure:

- who called
- which tool/capability was called
- whether it succeeded
- how long it took
- estimated cost
- error type
- quota consumption

This is why the correct path is not "free then paid." It is:

```text
usable -> controllable -> chargeable
```

## 6. Usage Metrics

Usage metrics are the fuel for future routing and marketplace decisions.

Minimum event:

```json
{
  "project_id": "proj_123",
  "capability_id": "image_generation",
  "provider_id": "provider_a",
  "tool_id": "generate_image",
  "success": true,
  "status_code": 200,
  "latency_ms": 1200,
  "estimated_cost": 0.02,
  "error_type": null
}
```

Metrics that matter:

- success rate
- cost per successful call
- average latency
- p95 latency
- failure type distribution
- quota usage

Data alone does not create a marketplace. Data becomes valuable when it feeds capability comparison and routing.

## 7. Capability Layer

Plain language:

> Capability Layer turns many APIs into comparable candidates for the same Agent intent.

Example:

```text
Capability: text_to_speech
  Candidate: elevenlabs_tts
  Candidate: openai_tts
  Candidate: internal_voice_api
```

Without this layer, API2Agent only has isolated endpoints. Isolated endpoints cannot compete.

Capability Layer should define:

- semantic name
- description
- input contract
- output contract
- safety level
- candidate providers
- compatibility rules
- observed metrics

## 8. Routing Layer

Plain language:

> Routing Layer decides which provider candidate should fulfill a capability request.

Routing strategies:

- choose cheapest
- choose fastest
- choose highest success rate
- balanced score
- failover after failure
- respect quotas
- respect safety policies

Routing is the moment API2Agent becomes a platform, because it starts deciding who receives Agent traffic.

## 9. Marketplace

Marketplace does not appear automatically because API2Agent has data.

Marketplace requires:

- comparable capabilities
- multiple provider candidates
- routing decisions
- observed success/cost/latency metrics
- pricing rules
- provider incentives

So the correct sequence is:

```text
Tooling Layer
  -> Control Layer
  -> Economic Layer
  -> Capability Layer
  -> Routing Layer
  -> Marketplace
```

## 10. MCP First, Not MCP Only

MCP remains the first important Agent runtime target because it is open and executable.

But API2Agent must not be defined as an MCP generator.

MCP is an output.

IR, proxy, metrics, capability abstraction, and routing are the strategic core.

## 11. The Most Important Product Judgment

API2Agent's moat should not be "we generate a schema."

The moat should become:

- many API inputs normalized into IR
- runnable capability packages
- observed execution data
- comparable capability providers
- routing policies
- marketplace trust and economics

In one sentence:

> API2Agent is the infrastructure layer that turns APIs into routable, measurable, and eventually marketable Agent capabilities.
