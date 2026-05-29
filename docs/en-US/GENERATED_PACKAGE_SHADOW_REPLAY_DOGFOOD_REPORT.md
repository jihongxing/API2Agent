# Generated Package Shadow + Replay Dogfood Report

Date: May 30, 2026

## Goal

Verify that local generated provider packages can participate in the Reliability + Observability loop:

- main provider execution
- shadow provider execution
- usage ledger recording
- exact replay from captured metadata
- golden trace listing and ledger filtering

## Method

A no-network dogfood registry was created under `.dogfood/generated-shadow-replay` with two local package runners:

- `primary`
- `shadow`

Command:

```bash
python -m api2agent.cli call .dogfood/generated-shadow-replay/registry.json \
  --capability-id public_ip_lookup \
  --params '{"ip":"203.0.113.10"}' \
  --db .dogfood/generated-shadow-replay/usage.sqlite \
  --strategy first \
  --shadow \
  --json
```

Replay command:

```bash
python -m api2agent.cli replay 70e439d8-e6b8-4831-adb3-a880e3a5366b \
  --db .dogfood/generated-shadow-replay/usage.sqlite \
  --execute \
  --json
```

Golden filtering:

```bash
python -m api2agent.cli golden --list \
  --db .dogfood/generated-shadow-replay/usage.sqlite \
  --capability-id public_ip_lookup \
  --provider-id shadow \
  --execution-mode shadow \
  --json

python -m api2agent.cli ledger \
  --db .dogfood/generated-shadow-replay/usage.sqlite \
  --golden-only \
  --group-by-mode \
  --json
```

## Result

Routing decision:

- selected provider: `primary`
- ranked providers: `primary`, `shadow`
- shadow attempts: `shadow`

Usage events:

- `primary` recorded as `direct`
- `shadow` recorded as `shadow`
- both events share one routing decision

Replay result:

```json
{
  "replayable": true,
  "exact_replay_metadata_ready": true,
  "executed": true,
  "replay_result": {
    "ok": true,
    "runtime": "local_package:.dogfood/generated-shadow-replay/shadow",
    "provider_id": "shadow",
    "status_code": 200,
    "body": {
      "ip": "203.0.113.10"
    }
  }
}
```

Golden list result:

- `contract_version`: `golden_trace.v0.1`
- `count`: `1`
- provider: `shadow`
- execution mode: `shadow`

## What This Proves

Generated packages are no longer only callable tools. They can now enter the same local execution and observability loop as SDK adapters:

```text
api2agent call
  -> provider package
  -> shadow provider package
  -> usage events
  -> replay
  -> golden trace filter
```

This closes the alpha gap between the compiler path and the SDK reliability path.
