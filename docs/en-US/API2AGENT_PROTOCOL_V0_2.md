# API2Agent Protocol v0.2

Status: frozen contract draft

Contract version: `api2agent.protocol.v0.2`

Schema snapshot: `schemas/api2agent/v0.2/protocol.schema.json`

## 1. Purpose

API2Agent Protocol v0.2 freezes the production-facing contract for turning external capabilities into Agent-callable execution units.

The protocol is source-neutral, but the current MVP remains API-first.

Protocol v0.2 exists so future production implementations can be written in Go, Rust, TypeScript, or another runtime without inheriting Python MVP assumptions.

## 2. Scope

v0.2 defines:

- identity attribution
- capability definitions
- capability source metadata
- provider candidates
- credential references
- cost profiles
- latency profiles
- network topology metadata
- reliability profiles
- routing decisions
- usage events
- decision logs
- ledger rows

v0.2 does not define:

- marketplace UI
- payment settlement
- provider revenue share
- hosted SaaS APIs
- workflow engine semantics
- every possible adapter implementation

## 3. Versioning Rules

Every exported protocol object MUST include:

- `schema_version`
- stable object ID when the object is persisted
- creation timestamp when the object represents an event or decision

The v0.2 schema version is:

```text
api2agent.protocol.v0.2
```

Future versions MAY add optional fields.

Future versions MUST NOT remove or rename v0.2 stable fields without a new contract version.

Persistent definitions MUST include explicit versions where behavior or schema can change:

- `capability_version`
- `provider_version`
- `mapping_version`

Usage, replay, ledger, and decision dataset records MUST preserve the versions used at execution time.

## 4. Request Context

Request context is the top-level object for one Agent capability invocation.

Stable fields:

- `id`
- `schema_version`
- `identity`
- `capability_id`
- `capability_version`
- `input_fingerprint`
- `execution_mode`
- `client_region`
- `created_at`

Rules:

- Routing decisions MUST reference `request_id`.
- Usage events MUST reference `request_id`.
- Decision logs MUST reference `request_id`.
- A single request MAY produce multiple routing decisions and multiple usage events.
- Raw input SHOULD NOT be stored by default. Use `input_fingerprint` for safe correlation.

## 5. Identity Reference

Identity answers who owns or initiated a call.

Stable fields:

- `project_id`
- `user_id`
- `api_key_id`
- `agent_id`

Rules:

- `project_id` is REQUIRED for controlled or auditable execution.
- `user_id`, `api_key_id`, and `agent_id` MAY be null in local execution.
- Usage events, routing decisions, decision logs, ledger rows, quota checks, and future billing exports MUST carry identity attribution.

## 6. Execution Class

Execution class describes the type of external capability source.

Stable values:

- `api`
- `workflow`
- `tool`
- `model`
- `human`
- `async_job`

Rules:

- v0.2 reserves these values at the protocol layer.
- v0.2 does not require implementation of every execution class.
- Current Python MVP generated packages SHOULD map to `api`.

Execution properties:

- `sync`
- `streaming`
- `deterministic`
- `idempotent`

These properties describe execution behavior for routing, retry, replay, and future async handling.

## 7. Capability Definition

A capability is the semantic unit an Agent requests and the router optimizes.

Stable fields:

- `id`
- `version`
- `name`
- `description`
- `execution_class`
- `execution_properties`
- `input_schema`
- `output_schema`
- `safety`
- `taxonomy`

Naming rule:

```text
<domain>.<resource>.<action>
```

Examples:

- `weather.current.get`
- `network.public_ip.get`
- `commerce.product.search`
- `payment.charge.create`

Rules:

- `version` MUST change when input schema, output schema, safety classification, or behavior changes incompatibly.
- Usage events MUST preserve the capability version used at execution time.

## 8. Capability Source Contract

Capability source metadata describes where execution comes from.

Stable fields:

- `source_id`
- `source_type`
- `execution_class`
- `execution_properties`
- `executor_ref`
- `input_schema`
- `output_schema`
- `auth`
- `region_metadata`

Stable `source_type` values:

- `openapi`
- `curl`
- `http_endpoint`
- `workflow_endpoint`
- `local_function`
- `model_endpoint`
- `human_queue`
- `manual`

Rules:

- v0.2 is API-first in implementation, but source-neutral in contract.
- Non-API sources MUST be adapted into an input -> execution -> output shape before routing.
- API2Agent MUST NOT become a workflow engine; workflows should be invoked through an adapter or endpoint.

## 9. Provider Candidate

A provider candidate implements a capability.

Stable fields:

- `id`
- `capability_id`
- `capability_version`
- `provider_id`
- `provider_version`
- `tool_id`
- `source_id`
- `execution_class`
- `estimated_cost`
- `cost_profile`
- `regions`
- `geo_affinity`
- `output_mapping`
- `mapping_version`
- `metadata`

Stable `geo_affinity` values:

- `global`
- `regional`
- `cn-only`
- `unknown`

Provider region selection MUST be deterministic when possible.

Rules:

- `provider_version` MUST change when provider behavior, endpoint semantics, or adapter behavior changes incompatibly.
- `mapping_version` MUST change when output normalization or mapping behavior changes.
- Usage events MUST preserve provider and mapping versions used at execution time.

## 10. Credential Reference

Credential references describe which calling right was used without exposing secrets.

Stable fields:

- `credential_reference`
- `credential_id`
- `owner_type`
- `owner_id`
- `provider_id`
- `auth_type`
- `injection_mode`
- `source`
- `resolution_strategy`
- `scope`
- `status`

Rules:

- Raw secret values MUST NOT appear in protocol records.
- Usage events MUST store only references or redacted metadata.
- Replay MAY require credential re-resolution.

Stable `resolution_strategy` values:

- `static`
- `dynamic`
- `per_request`

## 11. Metrics Window

Metrics window defines the observation window behind aggregate metrics.

Stable fields:

- `type`
- `size`
- `sample_size`
- `observed_at`
- `period_start`
- `period_end`

Stable `type` values:

- `rolling`
- `fixed`
- `lifetime`

Rules:

- Aggregate latency, cost, and reliability metrics SHOULD include a metrics window.
- Routing MUST NOT treat metrics from different windows as equally comparable without policy.
- `sample_size` SHOULD be present when metrics are observed from calls.

## 12. Cost Profile

Cost profile makes routing and future economic measurement auditable.

Stable fields:

- `estimated_cost`
- `observed_cost`
- `currency`
- `unit`
- `cost_source`
- `metrics_window`

Stable `cost_source` values:

- `estimated`
- `provider_declared`
- `observed`
- `contracted`

Rules:

- `estimated_cost` MAY be zero.
- `observed_cost` MAY be null.
- Billing MUST NOT be inferred from ledger rows alone.

## 13. Latency Profile

Latency profile separates total latency from its components.

Stable fields:

- `latency_ms`
- `latency_p50_ms`
- `latency_p95_ms`
- `latency_p99_ms`
- `latency_cold_start_ms`
- `latency_network_ms`
- `latency_provider_ms`
- `latency_overhead_ms`
- `latency_region`
- `metrics_window`

Rules:

- `latency_ms` is the top-level observed latency for a single execution.
- Component fields MAY be null when not measured.
- Aggregate metrics SHOULD use p50 and p95 before p99 is trusted.

## 14. Network Topology

Network topology makes region-aware routing auditable.

Stable fields:

- `client_region`
- `edge_region`
- `api2agent_region`
- `provider_region`
- `selected_provider_region`
- `route_path`

Rules:

- `client_region` describes the caller or Agent execution region.
- `provider_region` describes the provider region that handled the attempt when known.
- `selected_provider_region` describes the router's intended provider region.
- `route_path` records the logical path, not necessarily every physical network hop.

## 15. Reliability Profile

Reliability profile lets routing compare stability, not only success rate.

Stable fields:

- `reliability_score`
- `success_rate`
- `timeout_rate`
- `error_rate`
- `retry_rate`
- `failover_rate`
- `sla_confidence`
- `metrics_window`

Rules:

- Scores MUST be normalized between 0 and 1 when present.
- `sla_confidence` measures confidence in the metric, not the declared SLA itself.
- Reliability fields MAY be null for cold-start providers.

## 16. Routing Decision

Routing decisions are pre-execution plans. They record why a provider should be selected based on estimates and policy.

Stable fields:

- `id`
- `schema_version`
- `request_id`
- `identity`
- `capability_id`
- `strategy`
- `preset`
- `topology`
- `candidate_provider_ids`
- `ranked_provider_ids`
- `selected_provider_id`
- `selected_provider_region`
- `metrics`
- `cost_estimate`
- `latency_estimate`
- `reliability_estimate`
- `failover_policy`
- `created_at`

Stable routing strategies:

- `first`
- `random`
- `lowest_cost`
- `lowest_latency`
- `region_aware_latency`
- `highest_success_rate`
- `balanced`

Rules:

- A routing decision MUST be recorded before controlled execution.
- A routing decision MUST reference one request context.
- The selected provider MUST appear in `candidate_provider_ids` unless the decision is a synthetic failure record.
- `region_aware_latency` MUST consider `client_region` when available.
- Routing decisions contain estimates, not final observed outcomes.

## 17. Usage Event

Usage events record execution attempts.

Stable fields:

- `id`
- `schema_version`
- `request_id`
- `routing_decision_id`
- `execution_mode`
- `identity`
- `capability_id`
- `capability_version`
- `provider_id`
- `provider_version`
- `mapping_version`
- `tool_id`
- `method`
- `path`
- `status_code`
- `success`
- `latency`
- `topology`
- `cost`
- `error`
- `request_metadata`
- `credential_reference`
- `provider_runtime_reference`
- `is_golden`
- `created_at`

Stable execution modes:

- `direct`
- `proxy`
- `shadow`
- `replay`
- `race`

Rules:

- `race` is reserved in v0.2 and does not need to be implemented by the current MVP.
- `replay` events are included in audit ledgers but excluded from default routing metrics.
- `shadow` events are included in routing metrics by default unless policy says otherwise.

## 18. Decision Log

Decision logs are post-execution observations. They connect request context, routing plan, usage events, and outcome.

Stable fields:

- `id`
- `schema_version`
- `request_id`
- `routing_decision_id`
- `identity`
- `capability_id`
- `input_fingerprint`
- `routing_strategy`
- `routing_context`
- `selected_provider_id`
- `selected_provider_region`
- `cost_estimate`
- `latency_estimate`
- `reliability_estimate`
- `outcome`
- `usage_event_ids`
- `created_at`

Rules:

- Decision logs are the seed of the future decision dataset.
- Decision logs MUST reference a routing decision unless no routing decision could be created.
- Decision logs SHOULD NOT duplicate candidate rankings from routing decisions unless denormalization is explicitly required.
- Raw user input SHOULD NOT be stored by default.
- `input_fingerprint` SHOULD be stable enough for debugging and safe enough for privacy.

## 19. Ledger Row

Ledger rows aggregate usage events for audit and measurement.

Stable fields:

- `schema_version`
- `identity`
- `capability_id`
- `provider_id`
- `execution_mode`
- `region`
- `total_calls`
- `successful_calls`
- `failed_calls`
- `success_rate`
- `average_latency_ms`
- `estimated_cost`
- `observed_cost`
- `error_counts`
- `period_start`
- `period_end`

Rules:

- Ledger is measurement, not payment settlement.
- Billing systems MAY consume ledger data later, but MUST add explicit billing contracts.

## 20. Error Taxonomy

Stable error categories:

- `RATE_LIMIT`
- `TIMEOUT`
- `AUTH_ERROR`
- `INVALID_REQUEST`
- `NOT_FOUND`
- `PROVIDER_ERROR`
- `NORMALIZATION_ERROR`
- `QUOTA_EXCEEDED`
- `MISSING_AUTH`
- `NO_PROVIDER`
- `ALL_PROVIDERS_FAILED`
- `UNKNOWN`

Stable `error_scope` values:

- `caller`
- `provider`
- `platform`

Rules:

- Error records SHOULD distinguish caller fault, provider fault, and platform fault.
- Failover policies SHOULD use standardized error categories.

## 21. v0.1 Compatibility

v0.1 objects map into v0.2 as follows:

- `project_id` maps to `identity.project_id`.
- Missing identity fields map to null.
- `latency_ms` maps to `latency.latency_ms`.
- Region fields map into `topology`.
- `estimated_cost` maps to `cost.estimated_cost`.
- Existing generated package providers map to `execution_class=api`.
- Missing `request_id` maps to a synthetic request context during migration.
- Missing version fields map to `0.1-migrated`.
- Missing latency percentile fields map to null.
- Missing reliability fields map to null.
- Existing `credential_reference` remains a redacted credential reference.

v0.2 consumers MUST tolerate null optional fields during migration, but new v0.2 writers SHOULD emit request context and version fields.

## 22. Freeze Criteria

This contract is frozen when:

- this document is committed
- the schema snapshot is committed
- roadmap and technical design link to this document
- v0.1 compatibility is documented
- no Python runtime feature expansion is included in the freeze commit
