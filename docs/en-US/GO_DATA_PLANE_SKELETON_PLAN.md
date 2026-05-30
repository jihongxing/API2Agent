# Go Data Plane Skeleton Plan

Status: first skeleton implemented

Date: 2026-05-30

Related documents:

- `docs/en-US/PRODUCTION_ARCHITECTURE_RFC.md`
- `docs/en-US/PYTHON_REFERENCE_MIGRATION_PLAN.md`
- `docs/en-US/API2AGENT_PROTOCOL_V0_2.md`
- `schemas/api2agent/v0.2/protocol.schema.json`

## 1. Purpose

This plan defines the first Go Data Plane skeleton.

The goal is not to rebuild the full Python MVP in Go. The goal is to prove the production hot-path shape:

```text
POST /v1/execute
  -> RequestContext
  -> RoutingDecision
  -> ProviderAdapter
  -> UsageEvent
  -> DecisionLog
```

The skeleton must be protocol-first, small, and testable.

## 2. Scope

In scope:

- Go module for Data Plane
- `/v1/execute` HTTP endpoint
- local static snapshot loading
- deterministic routing stub
- one real no-auth provider adapter
- append-only event writer
- schema-shaped contract objects
- timeout budget propagation
- snapshot metadata propagation

Out of scope:

- Control Plane API
- hosted credential vault
- dashboard
- billing
- marketplace
- multi-provider routing optimization
- non-API capability sources

## 3. Proposed Repository Layout

```text
services/
  data-plane/
    go.mod
    cmd/
      api2agent-dataplane/
        main.go
    internal/
      httpapi/
        execute.go
      protocol/
        models.go
      routing/
        engine.go
      snapshots/
        loader.go
      adapters/
        adapter.go
        ipify.go
      credentials/
        resolver.go
      events/
        writer.go
      config/
        config.go
    testdata/
      snapshots/
        network.public_ip.get.json
```

Rules:

- generated or manually maintained protocol structs must match v0.2 semantics
- no Python runtime imports
- no hidden dependency on local Python package internals
- JSON fields must remain protocol-compatible

## 4. Endpoint Contract

Initial endpoint:

```http
POST /v1/execute
Authorization: Bearer <api2agent_project_key>
Content-Type: application/json
```

Minimum request:

```json
{
  "project_id": "local",
  "capability_id": "network.public_ip.get",
  "capability_version": "0.1-migrated",
  "input": {},
  "execution_mode": "proxy",
  "client_region": "local",
  "timeout_budget_ms": 5000
}
```

Minimum response:

```json
{
  "request_id": "req_...",
  "routing_decision_id": "route_...",
  "usage_event_id": "usage_...",
  "success": true,
  "output": {
    "ip": "127.0.0.1"
  }
}
```

## 5. First Capability

Initial real capability:

```text
network.public_ip.get
```

Initial provider:

```text
ipify
```

Why:

- no auth required
- stable output
- already dogfooded in Python MVP
- simple enough for dual-run comparison

## 6. Snapshot Model

The skeleton uses local static snapshots before Control Plane exists.

Required snapshot fields:

- `snapshot_version`
- `snapshot_fetched_at`
- `snapshot_ttl`
- `snapshot_source`
- capability definition
- provider candidates
- routing policy

Rules:

- RoutingDecision must record `snapshot_version`.
- Snapshot expiration policy may warn in skeleton mode.
- Phase B should not introduce mutable live Control Plane reads.

## 7. Routing Skeleton

Initial routing policy:

```text
first
```

Required routing fields:

- `request_id`
- `routing_mode`
- `routing_seed`
- `snapshot_version`
- `selected_provider_id`
- `selected_provider_region`

Rules:

- default routing mode is `deterministic`
- stochastic routing is out of scope for the skeleton
- routing decisions are pre-execution plans

## 8. Timeout Budget

The skeleton must carry timeout budget explicitly.

Fields:

- `execution_timeout_budget_ms`
- `attempt_timeout_ms`
- `attempt_timeout_policy`

Initial policy:

```text
fixed
```

Rules:

- provider attempt timeout must not exceed remaining execution budget
- timeout errors must map to standardized error records
- timeout budget must appear in safe request metadata or decision context

## 9. Event Writer

The skeleton should use an append-only local event writer.

Initial storage:

```text
.api2agent/events/*.jsonl
```

Event objects:

- RequestContext
- RoutingDecision
- UsageEvent
- DecisionLog

Ordering fields:

- `event_sequence_id`
- `parent_attempt_id`

Rules:

- event writes should not block provider response longer than necessary
- JSONL is acceptable for Phase B
- Postgres belongs to the Control Plane minimum phase

## 10. Credential Boundary

The first provider is no-auth.

Even so, the skeleton must define credential boundaries:

- credential resolver interface
- credential reference on usage events
- no raw secret logging
- missing credential error shape

Hosted vault integration is out of scope for Phase B.

## 11. Dual-Run Compatibility

The Go skeleton must support dual-run comparison with Python.

Comparison objects:

- normalized output
- RequestContext
- RoutingDecision
- UsageEvent
- DecisionLog

Expected difference:

- IDs may differ
- timestamps may differ
- implementation metadata may differ

Required match:

- capability ID
- capability version
- provider ID
- selected provider
- success flag
- normalized output schema
- error category when failure occurs

## 12. Test Plan

Required tests:

- `/v1/execute` golden path
- snapshot load and version propagation
- deterministic provider selection
- timeout budget propagation
- UsageEvent emission
- DecisionLog emission
- no raw credential logging

Optional tests:

- schema validation against JSON schema
- dual-run comparison fixture with Python output

## 13. Acceptance Criteria

Phase B plan is ready for implementation when:

- repository layout is accepted
- first capability/provider is accepted
- endpoint contract is accepted
- event writer behavior is accepted
- snapshot behavior is accepted
- timeout budget behavior is accepted
- no Control Plane dependency is required

The implementation is complete when:

- `go test ./...` passes inside `services/data-plane`
- local `/v1/execute` returns a real `network.public_ip.get` result
- RequestContext, RoutingDecision, UsageEvent, and DecisionLog are emitted
- emitted records include snapshot and timeout metadata
- no Python runtime is required on the hot path
