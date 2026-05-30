# Go Data Plane Consolidation Hardening v0 Report

Date: 2026-05-30

## Goal

Close the hardening gaps identified in `docs/en-US/GO_DATAPLANE_STAGE_REVIEW.md` before moving toward hosted control plane work.

## Completed

### Reusable Protocol Conformance Validator

Protocol conformance is now available outside `execute_test.go`.

Added:

- `services/data-plane/internal/conformance`
- `services/data-plane/cmd/api2agent-conformance`

The validator checks JSONL event envelopes and validates records against:

```text
schemas/api2agent/v0.2/protocol.schema.json
```

### Dogfood Event Conformance

The durable event and real external retry dogfood scripts now build and run `api2agent-conformance`.

Both reports include:

```json
{
  "protocol_conformance": true
}
```

### Event Write Failure Policy

Go Data Plane now uses fail-closed event writes for execution graph records.

If a required event cannot be written, `/v1/execute` returns:

```json
{
  "success": false,
  "error": {
    "error_type": "EVENT_WRITE_FAILED",
    "error_scope": "platform"
  }
}
```

This prevents successful execution responses with silently missing audit / usage records.

### Runtime Provider Availability Probe

Added:

```text
python scripts/go_dataplane_provider_probe_dogfood.py --output .dogfood/go-dataplane-provider-probe/report.json
```

The probe measures provider reachability from the Go Data Plane runtime, not from docs or a separate client assumption.

Report:

```text
docs/en-US/GO_DATAPLANE_PROVIDER_PROBE_DOGFOOD_REPORT.md
```

## Non-Goals

This hardening slice does not add:

- hosted database
- queue-backed ingestion
- billing
- marketplace ranking
- provider onboarding portal
- workflow runtime

## Recommended Next

The next implementation slice should be:

```text
Timeout Budget Semantics v0
```

Reason:

- real external dogfood already shows long wall-clock execution time
- current timeout budget is applied per attempt
- agents need predictable total request latency
