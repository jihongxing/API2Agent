# Go Data Plane Stage Review and Consolidation Plan

Date: 2026-05-30

Status: consolidation checkpoint after `efff899`.

## 1. Current Position

API2Agent is currently in the Go Data Plane hardening stage.

The active goal is not marketplace, billing, hosted SaaS, or broad non-API sources. The active goal is:

```text
API2Agent -> local Go Data Plane execution + observability primitive
```

Python remains the reference implementation and local dogfood harness. Go is the production Data Plane direction.

## 2. What Is Already Proven

| Area | Status | Evidence |
|---|---|---|
| Protocol v0.2 | Complete | `docs/en-US/API2AGENT_PROTOCOL_V0_2.md` and `schemas/api2agent/v0.2/protocol.schema.json` |
| Production architecture | Complete | `docs/en-US/PRODUCTION_ARCHITECTURE_RFC.md` |
| Go Data Plane skeleton | Complete | `/v1/execute`, `/healthz`, local snapshots, deterministic routing |
| Protocol conformance | Working | emitted `RequestContext`, `RoutingDecision`, `UsageEvent`, and `DecisionLog` are checked against schema in Go tests |
| Controlled retry/failover | Complete | `docs/en-US/GO_DATAPLANE_FAILOVER_DOGFOOD_REPORT.md` |
| Credential resolution | Complete skeleton | env-backed credential intent, injection, redacted attribution |
| Durable local event ingestion | Complete local slice | fsync-backed JSONL writes and restart sequence recovery |
| Real external retry | Complete dogfood | `httpbin/status/500` followed by `httpbin/ip` fallback |

## 3. What Needs Hardening

These are not new product features. They are consolidation work required before moving toward hosted control plane.

### 3.1 Reusable Protocol Conformance Validator

Current conformance logic is embedded inside `execute_test.go`.

Risk:

- dogfood scripts cannot reuse it
- future services may drift from Protocol v0.2
- schema validation is not yet a shared contract gate

Required hardening:

- extract reusable conformance validation into a Go package or shared script
- use it from Go tests
- validate JSONL dogfood output records against the schema snapshot

### 3.2 Event Write Failure Policy

The JSONL writer is durable, but handler call sites currently treat event writes as best-effort.

Risk:

- execution can succeed while audit/usage data is silently missing
- future billing and routing datasets would become untrustworthy

Required hardening:

- define fail-open vs fail-closed behavior for each event type
- add tests for writer failure behavior
- make event write failures visible in health or response semantics

### 3.3 Runtime Provider Availability Probe

Real external dogfood showed that `api.ipify.org` can be refused from the local Go runtime even when the API is documented and expected to work.

Risk:

- routing decisions assume provider availability without runtime proof
- provider performance data can be wrong if measured outside the actual execution runtime

Required hardening:

- add a minimal provider probe dogfood
- record provider reachability from the Data Plane runtime
- keep this as observability, not marketplace ranking yet

### 3.4 Timeout Budget Semantics

The current timeout is applied per attempt.

Risk:

- total request latency can exceed agent expectations when multiple attempts run

Required hardening:

- define total budget vs per-attempt budget
- persist the chosen policy in routing/request metadata
- test retry behavior under budget exhaustion

## 4. Next Task

Next task:

```text
Go Data Plane Consolidation Hardening v0
```

Scope:

1. Extract reusable Protocol v0.2 conformance validator.
2. Reuse the validator in Go tests and dogfood output validation.
3. Define event write failure policy.
4. Add failure-path tests for event writer / handler integration.
5. Add a small runtime provider availability probe dogfood.

Exit criteria:

- conformance validation is no longer test-local
- dogfood JSONL events can be validated against Protocol v0.2
- event write failures have explicit behavior
- provider reachability is measured from the Go runtime
- roadmap and implementation plan point to the next concrete slice

## 5. Non-Goals

Do not build in this consolidation slice:

- hosted database
- billing
- marketplace UI
- provider onboarding portal
- workflow runtime
- multi-region data plane
- queue-backed ingestion pipeline

Those remain later phases.
