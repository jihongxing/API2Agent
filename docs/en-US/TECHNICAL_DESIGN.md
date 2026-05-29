# API2Agent Technical Design

## 1. Current Implementation Decision

API2Agent currently uses Python for the local compiler and generated MVP runtime.

This is an implementation path, not the product boundary.

```text
Product goal: language-neutral, model-neutral, runtime-neutral
Current MVP: Python compiler and generated Python MCP runtime
```

## 2. Updated Architecture Direction

The architecture now has two major planes.

### Local Tooling Plane

```text
OpenAPI / curl
  -> Parser
  -> API2Agent IR
  -> Tool Filter
  -> Capability Package
  -> runner.py / mcp_server.py / smoke_test.py
```

Purpose:

- fast local adoption
- open-source distribution
- proof that APIs can become Agent-callable tools

### Hosted Control Plane

```text
Agent / generated runtime
  -> API2Agent Proxy
  -> Credential Resolver
  -> third-party API
  -> Usage Event
  -> Metrics Store
  -> Quota / Cost / Routing
```

Purpose:

- control traffic
- resolve and inject provider credentials
- observe success/cost/latency
- enable quota and future billing
- enable capability routing
- preserve future commercial optionality without making marketplace the current scope

## 3. Layered System Design

### 3.1 Compiler Layer

Responsibilities:

- parse inputs
- normalize into API2Agent IR
- filter tools
- generate local and hosted runtime artifacts

Current code:

```text
api2agent/
  cli.py
  filters.py
  parsers/
  ir/
  generators/
  safety/
```

### 3.2 Runtime Layer

Responsibilities:

- execute a generated tool
- validate params
- attach auth
- call direct API or proxy
- return structured result

Current MVP runtime is generated Python code.

Future runtime modes:

- direct local mode
- proxied hosted mode
- self-hosted enterprise mode

### 3.3 Proxy Layer

Responsibilities:

- receive normalized tool calls
- enforce project identity
- resolve and attach provider credentials
- forward to third-party APIs
- record usage events
- return structured success/error response

Minimum proxy API:

```http
POST /v1/proxy/call
Authorization: Bearer <project_proxy_key>
Content-Type: application/json
```

Body:

```json
{
  "routing_decision_id": "route_123",
  "capability_id": "github_repos",
  "tool_id": "list_repos",
  "provider_id": "github",
  "params": {}
}
```

### 3.3.1 Credential Orchestration Layer

Responsibilities:

- model credential ownership
- resolve which credential may be used for a provider call
- inject credentials into headers, query params, or request bodies
- prevent raw secrets from entering usage events, replay metadata, or logs
- attach `credential_reference` to usage events

Minimum local sources:

- environment variables
- project config
- inline override
- `none` for public APIs

Future hosted sources:

- project vault credential
- platform credential
- provider-managed credential

This layer is not billing. It is the permission and attribution layer required before billing or marketplace settlement can be credible.

### 3.4 Metrics Layer

Responsibilities:

- store usage events
- aggregate success rate
- aggregate latency
- estimate cost
- expose usage reports

Minimum event fields:

- routing_decision_id
- project_id
- capability_id
- provider_id
- tool_id
- timestamp
- success
- status_code
- latency_ms
- estimated_cost
- error_type

Routing decision ledger fields:

- id
- project_id
- capability_id
- strategy
- preset
- selected_provider_id
- ranked_provider_ids
- metrics snapshot
- created_at

### 3.5 Capability Layer

Responsibilities:

- define semantic capability objects
- connect provider candidates
- define compatible inputs/outputs
- attach metrics snapshots
- attach pricing and safety metadata

### 3.6 Routing Layer

Responsibilities:

- select provider candidate
- apply routing policy
- fail over on errors
- respect quota and safety constraints
- log routing decisions

Routing should be built after proxy metrics exist. Before metrics, routing is guesswork.

## 4. Data Model Direction

### Capability

```json
{
  "id": "text_to_speech",
  "name": "Text to Speech",
  "description": "Generate spoken audio from text.",
  "input_schema": {},
  "output_schema": {},
  "safety": "write"
}
```

### Provider Candidate

```json
{
  "id": "openai_tts",
  "capability_id": "text_to_speech",
  "source": "api",
  "tool_id": "create_speech",
  "pricing": {
    "model": "per_call",
    "estimated_cost": 0.01
  }
}
```

Provider registry files are validated before route or call execution:

```json
{
  "providers": [
    {
      "id": "ipify_public_ip",
      "capability_id": "public_ip_lookup",
      "provider_id": "ipify",
      "tool_id": "get",
      "estimated_cost": 0.001,
      "output_mapping": {
        "ip": "$.ip"
      },
      "metadata": {
        "package_dir": ".dogfood/ipify"
      }
    }
  ]
}
```

Invalid registry JSON should fail before routing, so bad provider metadata cannot silently distort metrics or ledger output.

### Usage Event

```json
{
  "project_id": "proj_123",
  "capability_id": "text_to_speech",
  "provider_id": "openai_tts",
  "tool_id": "create_speech",
  "success": true,
  "status_code": 200,
  "latency_ms": 950,
  "estimated_cost": 0.01,
  "error_type": null,
  "credential_reference": "cred_123"
}
```

### Credential

```json
{
  "credential_id": "cred_123",
  "owner_type": "project",
  "owner_id": "proj_123",
  "provider_id": "github",
  "auth_type": "api_key",
  "injection_mode": "header",
  "injection_name": "Authorization",
  "source": "env",
  "secret_ref": "GITHUB_TOKEN"
}
```

### Routing Policy

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

### Usage Correlation

```json
{
  "routing_decision_id": "route_123",
  "usage_event_id": "evt_456",
  "selected_provider_id": "github",
  "success": true,
  "latency_ms": 950,
  "estimated_cost": 0.01
}
```

This correlation is the minimum local ledger needed before API2Agent can support reliable cost reporting, quotas, routing audits, or a future hosted economic layer.

### Failover Policy

Failover is explicit policy, not hidden provider preference.

Minimum policy fields:

- enabled
- max_attempts
- retry_on_error_types
- retry_on_status_codes

Default retriable status codes:

- 408
- 429
- 500
- 502
- 503
- 504

### Local Usage Ledger

The local ledger groups direct and proxied usage by:

- project_id
- capability_id
- provider_id

Each row reports:

- total_calls
- successful_calls
- failed_calls
- success_rate
- average_latency_ms
- estimated_cost

This is not billing. It is the measurement layer required before billing can be designed responsibly.

### Direct Mode vs Proxy Mode Audit

API2Agent supports two execution audit modes.

Direct local mode:

- generated runner calls the provider API directly
- `execute_capability` records the local usage event
- useful for local dogfood and offline development
- does not enforce proxy quota or proxy auth

Proxy mode:

- generated runner calls API2Agent Proxy
- proxy forwards the provider API request
- proxy records the usage event
- supports quota, auth, and centralized control

Both modes write usage events with `routing_decision_id`, so `api2agent decision` and `api2agent ledger` work in both paths.

Both modes also write `execution_mode`:

- `direct`
- `proxy`
- `shadow`
- `replay`

Proxy mode remains the preferred path for controllable execution and future economic measurement.

Planned execution modes:

- `race`: execute multiple providers concurrently and return the best eligible result

`shadow` lets API2Agent collect provider comparison data without making routing risky for the user.

`replay` records debug executions in the ledger without affecting default routing metrics.

Metrics policy:

- include `shadow` by default because shadow is benchmark signal
- exclude `replay` by default because replay is debug signal

## 5. Why Python Still Makes Sense Now

Python remains reasonable for the current compiler because:

- first users are Agent builders
- OpenAPI/YAML/HTTP/testing ecosystem is mature
- MCP Python SDK is usable for MVP
- iteration speed matters more than high throughput

But the hosted control plane may later use a mixed stack:

```text
Python compiler workers
TypeScript/Node API service or dashboard
Postgres metrics store
Queue workers
Sandboxed execution workers
```

The decision should be made when proxy and metrics requirements become concrete.

## 6. Immediate Technical Priorities

### Priority 1: Keep Local Compiler Stable

Maintain:

- API2Agent IR
- generated package
- tool filtering
- smoke tests
- MCP integration tests

### Priority 2: Design Proxy Mode

Add a generation option later:

```bash
api2agent generate openapi.yaml --proxy https://api.api2agent.com
```

Generated runner should be able to call proxy instead of third-party API directly.

### Priority 3: Proxy-Side Credential Injection

Credential Schema v0.1 and the local resolver are implemented for generated package execution. The next design step is moving credential injection toward the proxy path.

Proxy-side credential injection should define:

- how generated packages send credential intent without raw secrets
- how proxy resolves credentials
- how proxy injects provider credentials
- how proxy records `credential_reference`
- how replay handles proxy-injected credentials

### Priority 4: Define Usage Event Schema

Before building billing, define the event contract.

### Priority 5: Define Capability Schema v0.1

Before provider comparison and routing can become reliable, define what makes two APIs comparable under one capability.

### Priority 6: Build Routing v0

Start with simple routing:

- random
- lowest estimated cost
- highest observed success rate

### Priority 7: v0.1-alpha Product Hook

The alpha product hook is Reliability + Observability.

Technical work should prioritize:

- deterministic replay design
- capability naming rule: `<domain>.<resource>.<action>`
- `shadow` execution mode
- golden trace marker
- two-provider failover + benchmark demo

## 7. Open-Core Boundary

Open source:

- compiler
- local package generation
- local runtime templates
- local tests

Commercial:

- hosted proxy
- metrics store
- quota enforcement
- credential vault
- credential orchestration
- routing
- registry
- billing

Far-term commercial option, not current product scope:

- marketplace

This matches the product strategy: free capabilities, but do not give up the platform control point.

## 8. Technical Principle

The technical north star is:

> Every Agent API call should be executable, observable, comparable, and eventually routable.
