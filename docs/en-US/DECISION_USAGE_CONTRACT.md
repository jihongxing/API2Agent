# Decision and Usage Contract

## Scope

This document defines the stable local API fields for routing decision inspection and usage audit.

It covers API2Agent local outputs only:

- `api2agent decision --json`
- routing decision records
- correlated usage events

It does not define hosted SaaS APIs, billing APIs, payment APIs, or marketplace APIs.

## Stable Decision Fields

The following `decision` fields are stable:

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

## Stable Failover Policy Fields

The following `failover_policy` fields are stable when present:

- `enabled`
- `max_attempts`
- `retry_on_error_types`
- `retry_on_status_codes`

## Stable Usage Event Fields

The following `usage_events[]` fields are stable:

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
- `request_metadata`
- `credential_reference`
- `provider_runtime_reference`
- `is_golden`
- `created_at`

Stable `execution_mode` values:

- `direct`
- `proxy`
- `shadow`
- `replay`

## Stable Top-Level Inspection Fields

The following `api2agent decision --json` top-level fields are stable:

- `contract_version`
- `decision`
- `usage_events`
- `usage_event_count`

Current contract version:

- `decision_usage.v0.1`

## Compatibility Rule

API2Agent may add new fields later, but must not remove or rename the stable fields above without a documented contract version change.

## Why This Matters

The API2Agent economic layer depends on auditability before billing:

```text
routing decision
  -> provider attempts
  -> usage events
  -> ledger rows
  -> future billing-ready measurement
```

Stable fields make that chain testable.

## Ledger Mode Grouping

`api2agent ledger --group-by-mode` groups rows by `execution_mode` in addition to project, capability, and provider.

This allows local reports to distinguish:

- direct local execution
- proxy-controlled execution
- shadow benchmark execution
- replay debug execution

Metrics policy:

- `direct` events are included in provider routing metrics
- `proxy` events are included in provider routing metrics
- `shadow` events are included in provider routing metrics by default
- `replay` events are excluded from provider routing metrics by default

Replay rows are included in the ledger, but excluded from provider routing metrics.

## Stable Ledger Row Fields

`api2agent ledger --json` returns an array of ledger rows.

Supported filters:

- `--project-id`
- `--capability-id`
- `--provider-id`
- `--month`

The following row fields are stable:

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

When `--group-by-mode` is not used, `execution_mode` is `null`.
