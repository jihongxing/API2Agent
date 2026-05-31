# API2Agent Base URL Override Report v0

Date: 2026-05-31

Status: complete

## Summary

Generated packages can now override provider base URLs at runtime without editing generated source.

This closes a practical onboarding gap for local, staging, regional, and self-hosted API environments while keeping the current Tooling Re-entry scope constrained:

- API-first only
- generated package runner behavior only
- no workflow engine
- no marketplace or billing
- no credential vault

## What Changed

### Runtime Overrides

Generated `runner.py` now supports:

```bash
API2AGENT_BASE_URL=http://127.0.0.1:9001
```

for package-wide base URL override.

It also supports tool-specific override:

```bash
API2AGENT_TOOL_BASE_URL_GET_ITEMS=http://127.0.0.1:9002
```

Precedence:

```text
tool-specific env
  -> API2AGENT_BASE_URL
  -> tool.base_url
  -> capability.base_url
```

### Fail-fast Validation

Overrides must start with `http://` or `https://`.

Invalid overrides return:

```text
invalid_base_url_override
```

before any direct or proxy provider call is attempted.

### Base Path Preservation

The generated runner now preserves base path prefixes when joining base URLs and paths.

Example:

```text
base_url = http://127.0.0.1:9001/staging
path     = /items
result   = http://127.0.0.1:9001/staging/items
```

This avoids losing OpenAPI server prefixes such as `/v1`.

### Generated README

Generated package READMEs now document:

- package-wide base URL override
- tool-specific base URL override
- provider-region override remains unchanged

## Dogfood

Repro command:

```bash
python scripts/api2agent_base_url_override_dogfood.py
```

Artifact:

```text
.dogfood/base-url-override/result.json
```

Dogfood flow:

```text
generated OpenAPI package
  -> default direct provider
  -> global base URL override direct provider
  -> tool-specific base URL override direct provider
  -> invalid override fail-fast
  -> proxy call with global override
  -> SQLite usage event with override URL
```

Dogfood checks:

- default direct execution uses the generated OpenAPI server URL
- `API2AGENT_BASE_URL` changes the direct provider target without source edits
- `API2AGENT_TOOL_BASE_URL_GET_ITEMS` wins over the global override
- invalid override fails before provider forwarding
- proxy execution forwards to the override URL
- proxy usage event records the override URL
- provider region and no-credential metadata remain intact
- scope remains API-first and no-workflow-engine

## Result

The dogfood passed.

Key observed values:

```json
{
  "direct_default_success": true,
  "direct_global_override_success": true,
  "direct_tool_override_success": true,
  "invalid_override_fails_fast": true,
  "proxy_override_success": true,
  "usage_event_url_uses_override": true,
  "provider_region_preserved": true,
  "credential_reference_none": true
}
```

## Why This Matters

Base URL override lowers real API onboarding cost:

- generated packages can point at local mocks, staging, regional hosts, or self-hosted endpoints
- developers do not need to patch generated source after generation
- proxy-mode usage data remains accurate because the event records the executed URL

It also supports the project’s current priorities:

- more real execution data
- lower API/provider onboarding cost
- faster iteration when testing regional or local providers

## Remaining Gap

The next Tooling Re-entry gap at the time of this report was safe manual testing for write-like operations. That slice is now complete; see `docs/en-US/API2AGENT_MANUAL_WRITE_TEST_PATH_REPORT.md`.

Next task:

```text
Large Spec Performance v0
```
