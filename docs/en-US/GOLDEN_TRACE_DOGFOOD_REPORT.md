# Golden Trace Dogfood Report

Date: May 30, 2026

## Goal

Verify that a real usage event can be marked as a golden trace, listed, and filtered in ledger output.

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

python -m api2agent.cli golden --list \
  --db .dogfood/shadow-weather.sqlite \
  --capability-id weather.get \
  --provider-id wttr_in \
  --execution-mode shadow \
  --json

python -m api2agent.cli ledger \
  --db .dogfood/shadow-weather.sqlite \
  --golden-only \
  --json
```

## Result

```json
{
  "contract_version": "golden_trace.v0.1",
  "is_golden": true,
  "usage_event": {
    "provider_id": "wttr_in",
    "execution_mode": "shadow",
    "is_golden": true
  }
}
```

List output returns a stable golden trace contract:

```json
{
  "contract_version": "golden_trace.v0.1",
  "count": 1,
  "golden_traces": [
    {
      "provider_id": "wttr_in",
      "execution_mode": "shadow",
      "is_golden": true
    }
  ]
}
```

## What This Proves

API2Agent can mark known-good real executions for future:

- replay baselines
- benchmark baselines
- provider scoring
- regression tests
- filtered ledger inspection

## Limits

- golden traces are markers and filters only
- no scoring logic uses golden traces yet
