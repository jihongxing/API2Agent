# Control, Receipt, and Trust Layer Strategy

Date: 2026-05-31

Status: strategic direction, not an active implementation task

Decision: API2Agent should evolve from API-to-Agent tooling into a controlled execution, receipt, routing, and trust layer. This strategy does not change the current next engineering task, which remains `Go Control Plane Persistent Registry Store Schema v0`.

## 1. Why This Matters

API2Agent is currently on the correct path:

```text
API -> Tooling -> Proxy -> Usage -> Metrics -> Routing
```

The strategic risk is stopping too early.

If API2Agent remains only:

```text
API -> Agent tool generator + optional proxy
```

users can generate tools and bypass the system. API2Agent would lose real execution data, routing leverage, and long-term platform power.

The long-term goal is stronger:

```text
API -> Capability -> Controlled Execution -> Receipt -> Routing Decision -> Trust / Settlement
```

## 2. Power Layer Model

### Layer 1: Tooling Layer

Status: implemented directionally.

API2Agent already supports:

- OpenAPI/curl to IR
- capability package generation
- generated runner
- generated MCP server

This is the entry point, not the moat.

### Layer 2: Control Layer

Status: partially implemented.

API2Agent already has:

- proxy execution
- usage events
- metrics
- quota
- Go Data Plane execution

This layer becomes valuable only when real calls consistently pass through API2Agent.

### Layer 3: Credential Orchestration

Status: implemented locally, not yet weaponized strategically.

API2Agent already has:

- credential ownership
- injection
- attribution
- local config and env resolution

Long term, credential ownership becomes part of trust weighting and abuse resistance.

### Layer 4: Capability and Routing Layer

Status: designed and partially dogfooded.

API2Agent has capability abstraction, provider candidates, and routing policies. The next strategic requirement is making routing depend on real execution data, not static configuration alone.

### Layer 5: Receipt, Trust, and Settlement Layer

Status: not implemented.

This is the future protocol-level power layer.

It should eventually support:

- verifiable call receipts
- trust-weighted metrics
- anti-gaming controls
- routing confidence
- settlement-ready execution records

Marketplace remains a far-term result, not the current product.

## 3. Core Thesis

The moat is not tool generation.

The moat is:

```text
Routing Control
+ Policy Layer
+ Receipt / Trust Data
```

API2Agent should make Agents depend on its execution interpretation:

```text
What was called?
Who called it?
Which credential was used?
Which provider executed?
Did it succeed?
How much did it cost?
How long did it take?
Should this provider be chosen next time?
Can the record be trusted?
```

## 4. Usage Event vs Receipt

Current `UsageEvent` should not be deleted or renamed immediately.

Recommended split:

```text
UsageEvent = internal execution observation
Receipt = protocol-grade, verifiable execution evidence
```

`UsageEvent` is still useful for local observability, debugging, metrics, and replay.

`Receipt` should become the future externalizable structure used for routing, trust, and settlement.

## 5. Receipt v0.1 Candidate Fields

Receipt v0.1 should be derived from existing execution records.

Candidate fields:

- `receipt_id`
- `schema_version`
- `request_id`
- `routing_decision_id`
- `attempt_id`
- `parent_attempt_id`
- `project_id`
- `agent_id`
- `capability_id`
- `capability_version`
- `provider_id`
- `provider_version`
- `tool_global_id`
- `credential_reference`
- `input_hash`
- `output_hash`
- `status_code`
- `success`
- `error_type`
- `error_scope`
- `latency_ms`
- `estimated_cost`
- `observed_cost`
- `cost_source`
- `client_region`
- `provider_region`
- `created_at`
- `signing_key_id`
- `signature`

Design rule:

```text
Do not replace UsageEvent now.
Add Receipt later as a signed or hash-bound derivative once execution semantics are stable.
```

## 6. Proxy as Default Path

Proxy must become the default path for generated tools.

Target direction:

```text
generated tool
  -> API2Agent proxy
  -> provider
```

Direct execution should remain available for:

- local development
- air-gapped use
- debugging
- privacy-sensitive self-hosted deployments

But direct execution should be clearly marked as having weaker routing, receipt, and trust properties.

## 7. Routing Must Become Real Early

Routing does not need to be sophisticated at first.

It does need to actually affect execution.

Minimal future rule:

```text
if provider_a.weighted_success_rate < provider_b.weighted_success_rate:
    route to provider_b
```

The strategic milestone is when Agent/provider selection starts depending on API2Agent-collected data.

## 8. Receipt Farming Risk

Future risk:

API providers may try to inflate their routing rank by generating fake or low-quality traffic through API2Agent.

This is `Receipt Farming`.

Mitigation direction:

- identity-weighted metrics
- project trust scores
- stronger weighting for BYOK calls tied to real user credentials
- lower weighting for anonymous or low-trust traffic
- rate limits and anomaly detection
- credential quality signals
- metrics windows with confidence and sample size
- separation of test, shadow, replay, and production traffic
- audit flags for suspicious provider self-traffic

Design implication:

```text
Not every receipt should have equal routing weight.
```

## 9. Privacy and Edge-Mesh Proxy

Hosted proxy alone may block enterprise adoption.

Many Agent builders will not want raw API keys, business inputs, or provider outputs to pass through a third-party hosted proxy.

API2Agent should support two execution tracks:

### Hosted Proxy

Best for:

- individual developers
- simple BYOK flows
- low-sensitivity workloads
- easiest onboarding

API2Agent receives fuller execution data.

### Edge-Mesh Proxy

Best for:

- enterprise users
- private APIs
- regulated data
- internal agent workflows

A local or customer-controlled proxy handles:

- credential injection
- raw request execution
- input/output redaction
- local policy enforcement

Only safe metadata should be reported upstream:

- request hashes
- output hashes
- status code
- error taxonomy
- latency
- cost metadata
- credential reference
- provider identity
- routing decision id
- signed receipt metadata

Design implication:

```text
API2Agent must collect trustworthy execution metadata without always collecting raw payloads.
```

## 10. Roadmap Implications

This strategy should influence future protocol and architecture work, but it should not interrupt the current persistence roadmap.

Near term:

- continue `Go Control Plane Persistent Registry Store Schema v0`
- preserve `UsageEvent`
- preserve `DecisionLog`
- preserve current snapshot contract

Future protocol work:

- Receipt v0.1
- signed/hash-bound execution evidence
- receipt-derived routing metrics
- identity-weighted metrics
- Edge-Mesh Proxy metadata contract
- anti-farming trust policy

Future architecture work:

- receipt signer in Data Plane or Edge Proxy
- receipt ingestion in Control Plane
- trust-weighted metrics pipeline
- routing policy that consumes trusted receipts
- audit model for provider self-traffic

## 11. Non-Goals

Do not implement now:

- payment settlement
- public receipt exchange
- marketplace ranking UI
- full trust score system
- cryptographic receipt network
- mandatory hosted proxy
- enterprise Edge-Mesh product

## 12. Adoption Criteria Before Implementation

Receipt work should begin only when:

- current UsageEvent and DecisionLog semantics are stable
- Control Plane persistence exists or is in progress
- routing consumes real metrics
- credential references are consistently emitted
- proxy or local edge execution is the default generated path

## 13. Strategic Judgment

API2Agent should not stop at being an API-to-Agent compiler.

The long-term opportunity is to become:

```text
the layer that records, verifies, interprets, and routes Agent calls to real-world capabilities
```

This is the difference between a useful tool and infrastructure.
