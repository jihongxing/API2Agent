# Generated Package Shadow + Replay Dogfood Report

Date: May 30, 2026

## Goal

Verify that local generated provider packages can participate in the Reliability + Observability loop:

- main provider execution
- shadow provider execution
- usage ledger recording
- exact replay from captured metadata
- golden trace listing and ledger filtering

## Method: No-Network Regression Dogfood

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

## Real No-Auth API Verification

The same loop was then verified with two real no-auth APIs generated from curl input:

- `ipify`: `https://api.ipify.org?format=json`
- `httpbin`: `https://httpbin.org/ip`

Generated packages:

```bash
python -m api2agent.cli generate --curl="curl 'https://api.ipify.org?format=json'" \
  --name ipify_public_ip \
  --output .dogfood/generated-real-api-shadow-replay/ipify \
  --force

python -m api2agent.cli generate --curl="curl 'https://httpbin.org/ip'" \
  --name httpbin_public_ip \
  --output .dogfood/generated-real-api-shadow-replay/httpbin \
  --force
```

Provider registry:

- capability: `public_ip_lookup`
- selected provider: `ipify`
- shadow provider: `httpbin`
- output mapping:
  - `ipify`: `$.ip`
  - `httpbin`: `$.origin`

Execution:

```bash
python -m api2agent.cli call .dogfood/generated-real-api-shadow-replay/registry.json \
  --capability-id public_ip_lookup \
  --db .dogfood/generated-real-api-shadow-replay/usage.sqlite \
  --strategy first \
  --shadow \
  --json
```

Result:

- routing decision id: `d7afb386-934b-4c21-b3a4-d1e9121840b5`
- main usage event: `c256e26b-639d-4be4-bfbd-9cae34d52a5c`
- shadow usage event: `7ac911e8-fe2c-4230-aa06-a928a344463b`
- main provider: `ipify`
- shadow provider: `httpbin`
- normalized output: `{ "ip": "108.174.61.76" }`
- ledger rows:
  - `ipify / direct / success`
  - `httpbin / shadow / success`

Replay:

```bash
python -m api2agent.cli replay 7ac911e8-fe2c-4230-aa06-a928a344463b \
  --db .dogfood/generated-real-api-shadow-replay/usage.sqlite \
  --execute \
  --json
```

Replay result:

- `replayable`: `true`
- `exact_replay_metadata_ready`: `true`
- `executed`: `true`
- runtime: `local_package:.dogfood/generated-real-api-shadow-replay/httpbin`
- provider: `httpbin`
- status: `200`

Golden trace filtering:

```bash
python -m api2agent.cli golden --list \
  --db .dogfood/generated-real-api-shadow-replay/usage.sqlite \
  --capability-id public_ip_lookup \
  --provider-id httpbin \
  --execution-mode shadow \
  --json

python -m api2agent.cli ledger \
  --db .dogfood/generated-real-api-shadow-replay/usage.sqlite \
  --golden-only \
  --group-by-mode \
  --json
```

Golden result:

- `contract_version`: `golden_trace.v0.1`
- `count`: `1`
- provider: `httpbin`
- execution mode: `shadow`

This proves the generated package path works against real APIs, not only local fakes.
