# API2Agent Manual Write Test Path Report v0

Date: 2026-05-31

Status: complete

## Summary

Generated packages now include a safe, explicit manual path for write-like API operations.

Default generated smoke tests remain read-only. POST, PUT, PATCH, and DELETE tools are not executed unless the developer deliberately opts in through the CLI or environment guard.

This keeps the Tooling Re-entry scope constrained:

- API-first only
- generated package test behavior only
- no workflow engine
- no marketplace or billing
- no credential vault

## What Changed

### Generated Manual Test

Generated packages now include:

```text
manual_write_test.py
```

The generated package still includes the read-only:

```text
smoke_test.py
```

Default behavior is unchanged:

```bash
api2agent test .
```

This runs only the read-only smoke test.

### Explicit Opt-in

Write/delete testing requires:

```bash
api2agent test . --allow-write
```

The CLI then runs `manual_write_test.py` and injects:

```bash
API2AGENT_ALLOW_WRITE_TEST=1
```

Running `manual_write_test.py` directly without the guard exits with code `2`.

### Write-like Selection

The manual test selects the first generated tool whose safety level is:

```text
write
delete
```

Generated request examples now support object and array schemas so required JSON bodies can be exercised without hand-editing generated source.

## Dogfood

Repro command:

```bash
python scripts/api2agent_manual_write_test_path_dogfood.py
```

Artifact:

```text
.dogfood/manual-write-test-path/result.json
```

Dogfood flow:

```text
write-only OpenAPI package
  -> default api2agent test
  -> no provider call
  -> api2agent test --allow-write direct
  -> provider POST
  -> api2agent test --allow-write proxy
  -> provider POST
  -> SQLite usage event
```

Dogfood checks:

- default smoke test succeeds without calling the provider
- default output warns that no read-only endpoint exists
- direct `--allow-write` calls the provider once
- proxy `--allow-write` calls the provider a second time
- both provider calls are `POST /items`
- generated example body is `{"name": "example", "quantity": 1}`
- proxy mode records exactly one usage event
- usage event preserves `tool_id`, `provider_region`, estimated cost, and no-credential attribution
- scope remains API-first and no-workflow-engine

## Result

The dogfood passed.

Key observed values:

```json
{
  "default_smoke_test_did_not_call_provider": true,
  "direct_allow_write_called_provider_once": true,
  "provider_called_twice_after_opt_in": true,
  "proxy_usage_event_recorded": true,
  "proxy_usage_event_write_tool": true,
  "proxy_usage_event_provider_region": true,
  "proxy_usage_event_estimated_cost": true,
  "proxy_usage_event_credential_none": true
}
```

## Why This Matters

This lowers onboarding cost without weakening safety:

- developers can dogfood write-only APIs without editing generated code
- accidental generated smoke-test writes remain blocked
- proxy usage data still flows for explicitly approved write tests
- credential-safe metadata and provider-region attribution remain intact

It also supports the current Tooling Layer goals:

- more real execution data
- lower API/provider onboarding cost
- safer expansion from read-only APIs into real operational APIs

## Remaining Gap

The next Tooling Re-entry gap is large OpenAPI performance and scale control.

Next task:

```text
Large Spec Performance v0
```
