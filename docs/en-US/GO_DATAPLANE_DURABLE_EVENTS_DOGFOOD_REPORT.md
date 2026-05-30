# Go Data Plane Durable Events Dogfood Report

Date: 2026-05-30

## Goal

Verify that Go Data Plane JSONL event ingestion persists events durably and resumes event sequence IDs after process restart.

## Setup

Dogfood flow:

```text
start Go Data Plane
  -> execute network.public_ip.get
  -> stop process
  -> restart Go Data Plane with the same event directory
  -> execute network.public_ip.get again
  -> inspect events.jsonl
```

Script:

```text
python scripts/go_dataplane_durable_events_dogfood.py --output .dogfood/go-dataplane-durable-events/report.json
```

## Result

```json
{
  "passed": true,
  "checks": {
    "first_response_success": true,
    "second_response_success": true,
    "event_log_exists": true,
    "eight_events_for_two_calls": true,
    "sequence_continues_after_restart": true,
    "no_duplicate_sequences": true,
    "two_request_contexts": true,
    "two_usage_events": true,
    "two_decision_logs": true,
    "protocol_conformance": true
  }
}
```

## What This Proves

- JSONL event writes are flushed and synced before returning from the writer.
- Restarted writers recover the next sequence ID from the existing event log.
- Event sequence IDs remain monotonic across process restarts.
- The execution graph remains append-only across restarts.
- Every emitted event record validates against the Protocol v0.2 schema snapshot.

## Notes

This is local durable ingestion, not the final hosted ingestion pipeline. A future hosted path still needs queue/log-backed ingestion and backpressure behavior.
