# Go Data Plane Snapshot Freshness Dogfood Report

Date: 2026-05-30

## Goal

Verify that Go Data Plane fails closed when the routing snapshot is expired.

This implements the Snapshot Drift mitigation from the Production Architecture RFC:

```text
record snapshot_version
record fetch time and TTL
fail closed when snapshots expire beyond policy
```

## Semantics

`/v1/execute` now checks snapshot freshness after writing `RequestContext` and before routing.

If the snapshot is expired or invalid:

- no `RoutingDecision` is emitted
- no provider adapter is called
- no `UsageEvent` is emitted
- a failed `DecisionLog` is emitted
- response returns `503`
- error type is `SNAPSHOT_EXPIRED` or `SNAPSHOT_INVALID`

`/healthz` reports expired snapshots as `degraded`.

## Dogfood Command

```bash
python scripts/go_dataplane_snapshot_freshness_dogfood.py \
  --output .dogfood/go-dataplane-snapshot-freshness/report.json
```

The script builds:

- `api2agent-dataplane`
- `api2agent-conformance`

It validates emitted JSONL events against Protocol v0.2.

## Scenario 1: Active Snapshot Executes

Setup:

- snapshot TTL is still valid
- local provider returns a fixed public-IP response

Observed result:

- `/healthz` returned `status: ok`
- `/v1/execute` succeeded
- provider was called once
- event graph was:

```text
request_context -> routing_decision -> usage_event -> decision_log
```

- Protocol v0.2 conformance passed

## Scenario 2: Expired Snapshot Fails Closed

Setup:

- snapshot `snapshot_fetched_at` is `2026-01-01T00:00:00Z`
- snapshot TTL is `1h`

Observed result:

- `/healthz` returned `status: degraded`
- `/healthz` returned `snapshot_expired: true`
- `/v1/execute` returned `SNAPSHOT_EXPIRED`
- provider was not called
- event graph was:

```text
request_context -> decision_log
```

- failed `DecisionLog.routing_context` included `error_type: SNAPSHOT_EXPIRED`
- Protocol v0.2 conformance passed

## Result

Snapshot Freshness Gate v0 passed.

The Go Data Plane now refuses to execute provider calls using an expired routing snapshot, preserving routing auditability and avoiding stale policy execution.

## Non-Goals

This slice does not add:

- hosted snapshot distribution
- push/pull snapshot refresh
- multi-snapshot fallback
- queue-backed ingestion
- Control Plane registry APIs
