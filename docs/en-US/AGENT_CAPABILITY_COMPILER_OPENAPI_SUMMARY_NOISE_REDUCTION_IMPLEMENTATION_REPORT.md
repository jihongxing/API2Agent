# Agent Capability Compiler OpenAPI Summary Noise Reduction Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI summary noise reduction v0 is implemented for the Agent Capability Compiler.

The implementation keeps raw package and diagnostics contracts intact while making default human-facing output easier to scan. `inspect` now folds dense aggregate lists, clips very long detail previews, and caps response previews. `diagnose` text output groups repeated findings. Generated README files now include a compact Package Overview with tool count, safety distribution, diagnostics status/score, and key caveats. The real-spec calibration harness now records summary-density metrics.

Implemented:

- bounded aggregate rendering for inspect schema hints and response categories
- response preview selection and folding in inspect tool details
- line clipping for long inspect detail previews
- repeated finding grouping in diagnostics text output
- README `Package Overview`
- key caveat grouping in README
- calibration summary-density metrics
- calibration recommendations for long inspect lines and repeated finding groups
- regression coverage for compact inspect output, grouped diagnostics text, README overview, and calibration metrics

No parser behavior, OpenAPI schema semantics, runtime validation, LLM summarization, provider execution, hosted diagnostics, workflow runtime, marketplace/provider onboarding, vault, billing, public CRUD, production gateway permission source, or automatic propagation was added.

## Files

Implementation:

- `api2agent/cli.py`
- `api2agent/diagnostics.py`
- `api2agent/generators/readme.py`
- `scripts/api2agent_openapi_real_spec_calibration.py`

Tests:

- `tests/test_cli.py`
- `tests/test_diagnostics.py`
- `tests/test_generators.py`
- `tests/test_openapi_real_spec_calibration.py`

Design reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_DESIGN.md`

## Behavior Changes

### Inspect

Default `api2agent inspect` output now:

- limits aggregate count lists and appends `+N more`
- prioritizes high-signal schema hint keys
- selects representative response summaries instead of dumping every response
- clips long detail lines at a bounded preview length
- preserves full raw capability output through `--json`

### Diagnostics Text

Default `api2agent diagnose` text output now groups repeated finding ids:

```text
- [warning] success_response_without_schema x5: Success response has no documented schema.
```

Diagnostics JSON remains one finding per occurrence.

### README

Generated README now includes:

```text
## Package Overview

- Tools: 5
- Safety: read=5
- Diagnostics: warn score=62
- Key caveats: success_response_without_schema(5), weak_tool_description(5)
```

Tool-level README details remain present for compatibility and review.

### Calibration Harness

The calibration artifact now includes:

```text
inspect_line_count
sample_tool_detail_line_count
max_inspect_line_chars
readme_tool_section_lines
repeated_finding_groups
```

These metrics let later hardening work track summary-density regressions without making the harness a strict CI gate.

## Dogfood Evidence

Run:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Observed:

```text
OpenAPI real-spec calibration: 4 pass, 2 warn, 0 fail, 1 skipped
- small_reference_basic: pass tools=1 score=87
- schema_rich_keywords: pass tools=2 score=70
- auth_rich_security: pass tools=5 score=62
- server_rich_choices: pass tools=3 score=62
- write_heavy_unsafe: warn tools=2 score=56 - diagnostics_score < 60; no read tools when write/delete tools exist
- large_rest_synthetic: warn tools=60 score=82 - tool_count > 50
- optional_cached_real_spec: skipped tools=0 score=None - optional source_path is not present
```

Summary-density review after implementation:

```text
small_reference_basic max_inspect_line_chars=41
schema_rich_keywords max_inspect_line_chars=180
auth_rich_security max_inspect_line_chars=41
server_rich_choices max_inspect_line_chars=41
write_heavy_unsafe max_inspect_line_chars=41
large_rest_synthetic max_inspect_line_chars=85
```

The previous schema-rich long-line recommendation is gone after compact schema hint formatting and detail clipping. Remaining recommendations are expected: large-surface filtering, write-heavy low score, and repeated diagnostic groups to review.

## Validation

Passed:

```text
python -m py_compile api2agent\diagnostics.py api2agent\cli.py api2agent\generators\readme.py scripts\api2agent_openapi_real_spec_calibration.py
```

Passed:

```text
python -m pytest tests\test_diagnostics.py tests\test_cli.py tests\test_generators.py tests\test_openapi_real_spec_calibration.py -q
```

Result:

```text
78 passed
```

Passed:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Passed:

```text
python -m pytest -q
```

Result:

```text
213 passed
```

## Compatibility

Compatibility is preserved:

- raw `capability.json` is unchanged
- raw `diagnostics.json` remains full-fidelity
- `api2agent inspect --json` still prints full capability JSON
- `api2agent diagnose --json` still prints full diagnostics JSON
- generated runner behavior is unchanged
- generated MCP tool schemas are unchanged
- diagnostics contract fields remain present

Default text output is intentionally more compact.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Closeout + Phase Review v0
```

The closeout should decide whether v0 summary budgets are sufficient, whether repeated diagnostic group recommendations should remain advisory, and whether the next compiler hardening target should be generic-example reduction, cached real-spec corpus expansion, or another summary-quality slice.
