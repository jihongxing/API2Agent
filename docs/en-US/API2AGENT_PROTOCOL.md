# API2Agent Protocol v0.1

Status: draft

## 1. Purpose

API2Agent Protocol defines how APIs become reliable, auditable, and routable Agent capabilities.

It is not a marketplace protocol.

The current protocol target is:

```text
API description
  -> capability
  -> provider candidate
  -> routing decision
  -> execution attempt
  -> usage event
  -> ledger row
  -> feedback into future routing
```

## 2. Design Principles

- model-neutral
- provider-neutral
- API-neutral
- local-first
- proxy-ready
- audit-first
- marketplace-later

The protocol must make API2Agent more than a generator. It should become a standard execution and audit layer for Agent API access.

## 3. Identity Layer

Every controlled or auditable call should eventually be attributable to an identity.

Minimum identity objects:

- `project_id`
- `user_id`
- `api_key_id`
- `agent_id`

Current local implementation only requires:

- `project_id`

Protocol direction:

```json
{
  "project_id": "proj_123",
  "user_id": "user_123",
  "api_key_id": "key_123",
  "agent_id": "agent_123"
}
```

Identity must attach to:

- routing decisions
- usage events
- ledger rows
- quotas
- future billing exports

Without identity, API2Agent is only an anonymous traffic pipe.

## 4. Capability Layer

Capability is the semantic unit Agents route against.

Stable capability fields:

- `id`
- `name`
- `description`
- `input_schema`
- `output_schema`
- `safety`

Example:

```json
{
  "id": "public_ip_lookup",
  "name": "Public IP Lookup",
  "description": "Return the caller's public IP address.",
  "input_schema": {},
  "output_schema": {
    "type": "object",
    "properties": {
      "ip": { "type": "string" }
    },
    "required": ["ip"]
  },
  "safety": "read"
}
```

## 5. Capability Taxonomy

Capability IDs must become more than arbitrary strings.

Minimum v0.1-alpha naming rule:

```text
<domain>.<resource>.<action>
```

Minimum taxonomy shape:

```text
network.public_ip.get
image.text.generate
image.poster.create
commerce.product.search
crm.contact.lookup
payment.charge.create
```

Taxonomy goals:

- prevent duplicate names for the same intent
- make providers comparable
- reduce routing if/else logic
- make future discovery possible

This is required before marketplace-like behavior can be credible.

## 6. Provider Candidate

Provider candidates implement a capability.

Stable provider fields:

- `id`
- `capability_id`
- `provider_id`
- `tool_id`
- `estimated_cost`
- `output_mapping`
- `metadata`

Example:

```json
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
```

## 7. Provider Onboarding Protocol

Provider onboarding is how supply enters API2Agent.

Minimum onboarding fields:

- provider identity
- capability ID
- generated package or hosted endpoint
- auth requirements
- output mapping
- cost metadata
- SLA metadata
- test endpoint or smoke test

Draft shape:

```json
{
  "provider_id": "ipify",
  "capability_id": "public_ip_lookup",
  "runtime": {
    "type": "local_package",
    "package_dir": ".dogfood/ipify"
  },
  "pricing": {
    "cost_source": "estimated",
    "estimated_cost": 0.001
  },
  "quality": {
    "declared_sla": null,
    "smoke_test": "get"
  }
}
```

## 8. Cost Source

Cost must declare its source.

Stable cost source values:

- `estimated`
- `provider_declared`
- `observed`
- `contracted`

Example:

```json
{
  "estimated_cost": 0.001,
  "cost_source": "estimated"
}
```

Without cost source, routing and billing-ready ledgers are not trustworthy.

## 9. Routing Contract

Routing chooses a provider candidate for a capability.

Stable routing decision fields:

- `id`
- `project_id`
- `capability_id`
- `strategy`
- `preset`
- `selected_provider_id`
- `ranked_provider_ids`
- `metrics`
- `failover_policy`
- `created_at`

Routing must remain policy-driven and auditable.

## 10. Failover Policy

Failover is explicit policy.

Stable fields:

- `enabled`
- `max_attempts`
- `retry_on_error_types`
- `retry_on_status_codes`

Default retriable status codes:

- `408`
- `429`
- `500`
- `502`
- `503`
- `504`

SDK-facing default retriable error types:

- `RATE_LIMIT`
- `TIMEOUT`
- `PROVIDER_ERROR`
- `NORMALIZATION_ERROR`
- `UNKNOWN`

SDK-facing default non-retriable error types:

- `AUTH_ERROR`
- `INVALID_REQUEST`
- `NOT_FOUND`

When both `status_code` and `error_type` are present, `retry_on_status_codes` is checked first. This keeps HTTP-level retry policy explicit and auditable.

## 11. Usage Event Contract

Usage events record execution attempts.

Stable fields:

- `id`
- `routing_decision_id`
- `execution_mode`
- `project_id`
- `capability_id`
- `provider_id`
- `tool_id`
- `method`
- `path`
- `status_code`
- `success`
- `latency_ms`
- `estimated_cost`
- `error_type`
- `created_at`

Stable execution modes:

- `direct`
- `proxy`

Planned execution modes:

- `shadow`: execute additional providers for benchmark data without changing the main result
- `race`: execute multiple providers concurrently and return the best eligible result

## 12. Ledger Contract

Ledger rows aggregate usage events.

Stable row fields:

- `project_id`
- `capability_id`
- `provider_id`
- `execution_mode`
- `total_calls`
- `successful_calls`
- `failed_calls`
- `success_rate`
- `average_latency_ms`
- `estimated_cost`

Ledger is measurement, not billing.

## 12.1 Replay Contract

Replay turns recorded execution history into a debug and regression tool.

Current command:

```text
api2agent replay <usage_event_id>
```

Current implementation status:

- replay preflight is implemented
- exact replay is not implemented yet
- the command returns `replayable: false` until request metadata capture exists

Minimum replay data:

- usage event
- routing decision
- capability ID
- provider ID
- tool ID
- input metadata where safely available
- redacted credential references

Replay must warn when exact replay is impossible because credentials, request body, or provider state were not retained.

## 12.2 Golden Trace Contract

Golden traces are known-good executions that can be used as benchmark or regression references.

Draft field:

```json
{
  "is_golden": true
}
```

Golden trace support is optional in early alpha code, but the protocol should allow it.

## 13. Error Taxonomy

Error taxonomy must be machine-readable because routing and failover depend on it.

Current execution/proxy error types:

- `http_status`
- `http_error`
- `proxy_error`
- `quota_exceeded`
- `missing_auth`
- `missing_parameters`
- `output_normalization`
- `no_provider`
- `all_providers_failed`

Current SDK adapter error types:

- `RATE_LIMIT`
- `TIMEOUT`
- `AUTH_ERROR`
- `INVALID_REQUEST`
- `NOT_FOUND`
- `PROVIDER_ERROR`
- `NORMALIZATION_ERROR`
- `UNKNOWN`

Future work should define:

- retriable vs non-retriable
- provider fault vs caller fault
- billing-impacting vs non-billing-impacting

## 14. Routing Feedback Loop

API2Agent should not only record metrics. It should use them.

Feedback loop:

```text
usage event
  -> metrics snapshot
  -> routing policy
  -> next routing decision
```

Minimum metrics:

- success rate
- average latency
- estimated cost per call
- failure count
- error type distribution

Future routing can become context-aware, but v0.1 only requires aggregate provider metrics.

## 15. Current Implementation Coverage

Implemented:

- local compiler
- generated runner
- generated MCP server
- proxy
- usage events
- routing decisions
- failover policy
- direct/proxy execution mode
- ledger
- provider registry contract
- decision/usage contract
- SDK `weather.get` core loop
- SDK benchmark helper
- explicit SDK routing strategy
- SDK failover with attempts recorded under one routing decision

Not yet implemented:

- full identity layer
- credential vault
- hosted control plane
- provider onboarding workflow
- cost source field
- capability taxonomy registry
- formal error taxonomy document
- routing feedback beyond aggregate metrics

## 16. Non-Goals For v0.1

- marketplace UI
- payment processing
- provider revenue share
- public provider onboarding portal
- hosted SaaS APIs
- settlement

These may come later, but API2Agent v0.1 must first become a reliable capability execution and audit protocol.
