# Replay Dogfood Report

Date: May 30, 2026

## Goal

Verify that `api2agent replay --execute` can re-run a provider call from captured usage event metadata.

Source database:

- `.dogfood/shadow-weather.sqlite`

Capability:

- `weather.get`

## Method

Replay a successful shadow event:

```bash
python -m api2agent.cli replay 31c5a817-0d2a-4174-94e9-6186acba64ef \
  --db .dogfood/shadow-weather.sqlite \
  --execute \
  --json
```

## Result

Replay preflight:

```json
{
  "replayable": true,
  "exact_replay_metadata_ready": true,
  "executed": true,
  "missing_for_exact_replay": []
}
```

Replay execution:

```json
{
  "ok": true,
  "runtime": "sdk:WttrInWeatherAdapter",
  "provider_id": "wttr_in",
  "status_code": 200
}
```

An additional replay against the original `open_meteo` main event was executable but returned a live timeout. That is acceptable and useful: replay does not pretend provider state is frozen. It re-runs the captured call and surfaces the current provider behavior.

## What This Proves

API2Agent now has a minimal deterministic replay path for SDK adapter calls when:

- request metadata is captured
- provider runtime reference is supported
- no credential reference is required

Replay has moved from audit-only preflight to executable debugging for supported events.

## Limits

- SDK adapters supported first
- HTTP/proxy replay exists only when credentials are not required
- replay execution does not write a new usage event yet
- local generated package replay is still future work
