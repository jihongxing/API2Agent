# Go Data Plane Timeout Budget Dogfood Report

Date: 2026-05-30

## Goal

Verify that Go Data Plane treats `timeout_budget_ms` as a request-level total deadline, not as a fresh per-provider timeout.

This matters because failover should improve reliability without multiplying the maximum latency seen by the Agent.

## Semantics

`timeout_budget_ms` now means:

```text
Agent request starts
  -> total deadline is created
  -> each provider attempt receives only the remaining budget
  -> fallback is skipped if the budget is exhausted
```

Each `UsageEvent.request_metadata` records:

- `total_timeout_budget_ms`
- `attempt_timeout_budget_ms`
- `remaining_timeout_budget_ms`
- `timeout_budget_policy: "total_deadline"`

The final `DecisionLog.routing_context` records:

- `total_timeout_budget_ms`
- `remaining_timeout_budget_ms`
- `timeout_budget_exhausted`
- `timeout_budget_policy`

## Dogfood Command

```bash
python scripts/go_dataplane_timeout_budget_dogfood.py \
  --output .dogfood/go-dataplane-timeout-budget/report.json
```

The script builds:

- `api2agent-dataplane`
- `api2agent-conformance`

It then runs two deterministic local provider scenarios and validates emitted JSONL events against Protocol v0.2.

## Scenario 1: Budget Exhaustion Prevents Fallback

Setup:

- primary provider sleeps longer than the total request budget
- fallback provider is healthy
- total budget is `300ms`

Observed result:

- response failed with `TIMEOUT`
- primary provider was called once
- fallback provider was not called
- one `UsageEvent` was written
- `DecisionLog.outcome` was `failure`
- `timeout_budget_exhausted` was `true`
- Protocol v0.2 conformance passed

This proves failover does not receive a new full timeout after the primary consumes the request budget.

## Scenario 2: Fast Failure Allows Fallback

Setup:

- primary provider returns HTTP 500 immediately
- fallback provider is healthy
- total budget is `1000ms`

Observed result:

- response succeeded
- primary provider was called once
- fallback provider was called once
- two `UsageEvent` records were written
- `DecisionLog.outcome` was `success`
- fallback provider was selected
- `timeout_budget_exhausted` was `false`
- Protocol v0.2 conformance passed

This proves failover still works when the first provider fails quickly and budget remains.

## Result

Timeout Budget Semantics v0 passed.

The Go Data Plane now provides predictable request-level latency semantics while preserving retry/failover when time remains.

## Non-Goals

This slice does not add:

- queue-backed event ingestion
- adaptive timeout allocation
- per-provider timeout tuning
- race mode timeout semantics
- hosted control plane policy management
