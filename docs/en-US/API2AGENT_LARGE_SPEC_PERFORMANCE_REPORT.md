# API2Agent Large Spec Performance Report v0

Date: 2026-05-31

Status: complete

## Summary

API2Agent now handles large OpenAPI specs with stronger scale control and better developer guidance.

This slice targets GitHub REST-style APIs where a single OpenAPI document can produce 1000+ tools. The goal is not to hide that risk; it is to make the package understandable, bounded when requested, and testable without editing generated source.

Scope stayed constrained:

- API-first only
- OpenAPI generation, inspection, and generated-package test usability
- no workflow engine
- no marketplace or billing
- no hosted control-plane changes

## What Changed

### Parse-time Filtering

OpenAPI filters are now applied during parsing for:

- `--include-tag`
- `--include-path`
- `--include-operation`
- `--max-tools`

This avoids building every tool before applying filters, which matters for large specs. Bounded generation such as `--max-tools 5` no longer needs an extra full operation-count pass just to decide whether to warn.

### Large Package Inspect Summary

`api2agent inspect` now prints a compact package summary before listing tools:

```text
Tool count: 1200
Safety: read=1200
Top tags: group-0(100), group-1(100)
Top path prefixes: /groups(1200)
Large package hint: regenerate with --include-tag, --include-path, --include-operation, or --max-tools before wiring this into an Agent.
```

Tool listing remains truncated by default and can still be expanded with `--all`.

### Targeted Tool Test

`api2agent test` can now run one selected generated tool:

```bash
api2agent test ./package --tool get_repo --params '{"owner":"octocat","repo":"Hello-World"}'
```

This improves large-package usability because developers do not have to rely on whichever read-only tool was selected for `smoke_test.py`.

Safety remains intact:

- selected write/delete tools require `--allow-write`
- default `api2agent test` remains read-only
- `api2agent test --allow-write` still runs the guarded manual write path

### Generated README Guidance

Generated package READMEs now document targeted read checks with `api2agent test --tool ... --params ...`.

## Dogfood

Repro command:

```bash
python scripts/api2agent_large_spec_performance_dogfood.py
```

Artifact:

```text
.dogfood/large-spec-performance/result.json
```

Dogfood flow:

```text
synthetic 1200-operation OpenAPI spec
  -> unfiltered generation
  -> large package warning
  -> inspect summary with limit=3
  -> bounded generation with --max-tools 5
  -> bounded generation with --include-tag group-7 --max-tools 5
  -> targeted api2agent test --tool get_group7_item0
  -> one local provider GET
```

Dogfood checks:

- unfiltered generation succeeds with 1200 tools
- unfiltered generation warns about excessive tool count
- inspect prints tool count, summary, truncation, and large-package hint
- `--max-tools 5` produces 5 tools without a large-package warning
- `--include-tag group-7 --max-tools 5` produces 5 tools
- targeted `api2agent test --tool` calls exactly one selected read tool
- API-first and no-workflow-engine constraints remain explicit

## Result

The dogfood passed.

Key observed values:

```json
{
  "unfiltered_tool_count_1200": true,
  "unfiltered_generation_warns_large_package": true,
  "inspect_prints_tool_count": true,
  "inspect_truncates_tools": true,
  "max_tools_limited_to_5": true,
  "tag_filtered_limited_to_5": true,
  "selected_tool_test_success": true,
  "selected_tool_called_provider_once": true
}
```

## Why This Matters

Large specs are a real API2Agent onboarding problem:

- they can overwhelm Agent tool selection
- they make package inspection noisy
- they make smoke testing arbitrary
- they increase generation cost before the developer has chosen a useful capability slice

This slice keeps large APIs usable while preserving the current product goals:

- more real execution data
- lower API/provider onboarding cost
- faster and more controllable generated-package iteration

## Remaining Gap

The remaining Tooling Re-entry item at the time of this report was a curl naming residual review. That review is now complete; see `docs/en-US/API2AGENT_CURL_NAMING_RESIDUAL_REVIEW.md`.

That phase closeout is now complete. Next task:

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```
