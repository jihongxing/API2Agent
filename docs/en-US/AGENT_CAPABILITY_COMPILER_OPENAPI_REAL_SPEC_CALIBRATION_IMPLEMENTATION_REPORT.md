# Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI real-spec calibration harness v0 is implemented for the Agent Capability Compiler.

The repository now has a local, deterministic calibration script that generates capability packages from a curated OpenAPI corpus, extracts package quality metrics, classifies pass/warn/fail/skipped outcomes, writes a machine-readable artifact, and prints a concise review summary.

The implementation supports:

- a Python-defined calibration manifest with purpose-labeled corpus slots
- existing fixture coverage for small, schema-rich, auth-rich, server-rich, and write-heavy cases
- a local synthetic large OpenAPI spec for large-surface calibration without network dependency
- optional cached real-spec cases that skip cleanly when not present
- package metrics for tool counts, safety counts, required inputs, schema hints, response categories, diagnostics, artifact sizes, generation latency, inspect excerpts, sample tool details, and first-call params
- status classification with documented warn/fail thresholds
- `.dogfood/openapi-real-spec-calibration/result.json`
- regression tests for manifest coverage, path containment, status classification, optional skips, artifact contract, and synthetic large-surface warning behavior

No real provider execution, network-dependent main-suite tests, runtime validation, OpenAPI 3.1 dialect enforcement, LLM schema interpretation, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, workflow runtime, or automatic snapshot propagation was added.

## Files

Implementation:

- `scripts/api2agent_openapi_real_spec_calibration.py`

Tests:

- `tests/test_openapi_real_spec_calibration.py`

Design reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_DESIGN.md`

## Harness Contract

Script:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Artifact:

```text
.dogfood/openapi-real-spec-calibration/result.json
```

Contract version:

```text
api2agent.openapi_real_spec_calibration.v0
```

Top-level artifact fields:

```text
contract_version
generated_at
cases
summary
recommendations
```

The generated package directories are local dogfood outputs under:

```text
.dogfood/openapi-real-spec-calibration/generated/
```

## Corpus

Default cases:

- `small_reference_basic`
- `schema_rich_keywords`
- `auth_rich_security`
- `server_rich_choices`
- `write_heavy_unsafe`
- `large_rest_synthetic`
- `optional_cached_real_spec`

The optional cached real-spec case is skipped when the local file is absent, so the harness remains offline and deterministic by default.

## Dogfood Evidence

Run:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Observed:

```text
OpenAPI real-spec calibration: 1 pass, 5 warn, 0 fail, 1 skipped
- small_reference_basic: pass tools=1 score=82
- schema_rich_keywords: warn tools=2 score=50 - diagnostics_score < 60
- auth_rich_security: warn tools=5 score=0 - diagnostics_score < 60
- server_rich_choices: warn tools=3 score=20 - diagnostics_score < 60
- write_heavy_unsafe: warn tools=2 score=40 - diagnostics_score < 60; no read tools when write/delete tools exist
- large_rest_synthetic: warn tools=60 score=80 - tool_count > 50
- optional_cached_real_spec: skipped tools=0 score=None - optional source_path is not present
```

The artifact was written to:

```text
.dogfood/openapi-real-spec-calibration/result.json
```

## Output Review Answers

Noisiest diagnostics:

```text
schema_rich_keywords
```

Largest package:

```text
large_rest_synthetic
```

Hardest summaries to read:

```text
schema_rich_keywords
```

Generated examples that remain generic:

```text
small_reference_basic still uses generic required user_id example because the source fixture has no example/default.
```

Diagnostics that should become more precise:

```text
auth_rich_security and server_rich_choices have low scores because calibration intentionally includes metadata-rich warning cases. Future work can separate expected metadata warnings from user-actionable failures.
```

Next evidence-driven hardening gap:

```text
diagnostics score calibration and summary-noise review across real/cached specs.
```

## Validation

Passed:

```text
python -m py_compile scripts\api2agent_openapi_real_spec_calibration.py
```

Passed:

```text
pytest tests\test_openapi_real_spec_calibration.py tests\test_generators.py tests\test_cli.py
```

Result:

```text
61 passed
```

Passed:

```text
pytest
```

Result:

```text
210 passed
```

## Compatibility

Compatibility is preserved:

- generated package contracts are unchanged
- calibration uses existing parser, generator, diagnostics, schema hint, response category, and inspect-summary helpers
- no production CLI command or runtime behavior was added
- generated dogfood outputs remain under `.dogfood`
- optional real-spec inputs do not fail the main harness when absent

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Closeout + Phase Review v0
```

The closeout should decide whether this local calibration harness is sufficient to close, and whether the next compiler hardening target should be diagnostics score calibration, summary-noise reduction, generic-example reduction, or cached real-spec corpus expansion.
