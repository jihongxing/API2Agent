# Golden Trace Dogfood Report

Date: May 30, 2026

## Goal

Verify that a real usage event can be marked as a golden trace.

Source database:

- `.dogfood/shadow-weather.sqlite`

Usage event:

- `31c5a817-0d2a-4174-94e9-6186acba64ef`

Provider:

- `wttr_in`

Execution mode:

- `shadow`

## Method

```bash
python -m api2agent.cli golden 31c5a817-0d2a-4174-94e9-6186acba64ef \
  --db .dogfood/shadow-weather.sqlite \
  --json
```

## Result

```json
{
  "is_golden": true,
  "usage_event": {
    "provider_id": "wttr_in",
    "execution_mode": "shadow",
    "is_golden": true
  }
}
```

## What This Proves

API2Agent can mark known-good real executions for future:

- replay baselines
- benchmark baselines
- provider scoring
- regression tests

## Limits

- golden traces are markers only
- no golden-trace filtering command yet
- no scoring logic uses golden traces yet
