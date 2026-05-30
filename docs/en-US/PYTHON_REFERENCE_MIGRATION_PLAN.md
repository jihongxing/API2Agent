# Python Reference Migration Plan

Status: active

Date: 2026-05-30

Related documents:

- `docs/en-US/MVP_EXIT_REVIEW.md`
- `docs/en-US/ARCHITECTURE_DEFINITION_PHASE.md`
- `docs/en-US/PRODUCTION_ARCHITECTURE_RFC.md`
- `docs/en-US/API2AGENT_PROTOCOL_V0_2.md`
- `schemas/api2agent/v0.2/protocol.schema.json`

## 1. Purpose

This plan defines how the Python MVP transitions from the hot path into a reference and compatibility role.

Python remains valuable for:

- compiler behavior
- local dogfood
- compatibility validation
- protocol regression testing

Python should not remain the hosted production data plane.

## 2. Migration Principle

Migration is a progressive narrowing of Python's responsibility:

```text
hot path execution
  -> dual-run reference path
  -> compatibility oracle
  -> local dogfood and compiler only
```

The migration must preserve:

- protocol compatibility
- deterministic replay
- usage and decision auditability
- dogfood comparability

The migration must not preserve:

- hidden runtime assumptions
- duplicated production logic across Python and Go
- long-term divergence in event schemas

## 3. Python Roles After Migration

Python should continue to own:

- OpenAPI/curl compiler
- generated package reference behavior
- protocol conformance tests
- local dogfood harness
- schema validation helpers

Python should stop owning:

- hosted proxy execution
- high-throughput routing
- production credential vault
- production usage ingestion
- long-lived hosted adapter runtime

## 4. Migration Phases

### Phase 1: Freeze the Python Surface

Goal:

- prevent new Python runtime expansion
- lock emitted events to v0.2 schema
- keep Python as the compatibility baseline

Deliverables:

- schema-validated usage events
- schema-validated routing decisions
- schema-validated decision logs
- protocol regression tests

### Phase 2: Introduce Go Data Plane Skeleton

Goal:

- build the first Go `/v1/execute` path
- support one real adapter
- emit the same contract objects as Python

Deliverables:

- RequestContext creation
- RoutingDecision creation
- UsageEvent append
- snapshot propagation
- timeout budget propagation

### Phase 3: Dual-Run Dogfood

Goal:

- execute the same capability through Python and Go
- compare outputs, events, and latency breakdowns

Deliverables:

- identical capability inputs
- comparable normalized outputs
- compatible credential references
- matching ledger aggregation

Acceptance:

- Go and Python emit semantically equivalent contract objects
- any divergence is explained by snapshot version or adapter version

### Phase 4: Move Hosted Traffic to Go

Goal:

- move hosted proxy requests off Python hot path
- keep Python only as fallback reference

Deliverables:

- Go Edge Proxy
- Go Routing Engine
- Go Provider Adapter runtime
- Control Plane snapshot distribution

Migration rule:

- move by capability, not by arbitrary user
- move by region only after the capability path is stable

### Phase 5: Retire Python from Hot Path

Goal:

- remove Python from hosted execution
- retain Python for compiler and reference use

Final Python responsibilities:

- local compiler
- dogfood harness
- compatibility oracle
- documentation examples

## 5. Compatibility Rules

Python and Go must agree on:

- `RequestContext`
- `RoutingDecision`
- `UsageEvent`
- `DecisionLog`
- `LedgerRow`
- `CredentialReference`
- `metrics_window`
- `snapshot_version`

The migration is invalid if Python and Go disagree on schema semantics without an explicit version reason.

## 6. Test Strategy

Required tests:

- schema conformance tests
- replay equivalence tests
- routing decision equivalence tests
- credential redaction tests
- output normalization tests
- failover parity tests

Recommended tests:

- golden trace comparison
- region-aware routing comparison
- metrics window comparison

## 7. Exit Criteria

This migration plan is complete when:

- Python no longer serves hosted production traffic
- Go Data Plane handles the production hot path
- Python remains available as the reference compiler and dogfood harness
- protocol conformance is preserved across both runtimes
- replay and audit output remain explainable
