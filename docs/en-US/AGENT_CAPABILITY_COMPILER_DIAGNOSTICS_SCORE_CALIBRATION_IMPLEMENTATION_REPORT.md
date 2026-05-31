# Agent Capability Compiler Diagnostics Score Calibration Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

Diagnostics score calibration v0 is implemented for the Agent Capability Compiler.

The diagnostics contract remains compatible: existing `status`, `score`, `summary`, `metrics`, `generation_context`, and `findings` fields are preserved. Scoring now uses an explicit impact profile instead of only severity counts, and each diagnostics payload includes `scoring_profile` plus a machine-readable `score_breakdown`.

The implementation supports:

- `api2agent.diagnostics.score_profile.v0`
- impact classes for `blocking`, `action_required`, `review_required`, `metadata_review`, and `readiness`
- metadata penalty capping so schema/auth/server-rich packages are not punished for useful visibility findings
- per-finding action penalty capping so repeated per-operation warnings do not dominate the package score
- zero-penalty readiness findings such as `proxy_identity_ready`
- severity-based `status` compatibility: errors still fail, warnings still warn
- regression coverage for score breakdown shape, metadata-rich fixtures, blocking findings, and unsafe write-heavy packages

No parser behavior, OpenAPI schema semantics, runtime validation, provider execution, hosted diagnostics service, workflow runtime, marketplace/provider onboarding, vault, billing, public CRUD, production gateway permission source, or automatic propagation was added.

## Files

Implementation:

- `api2agent/diagnostics.py`

Tests:

- `tests/test_diagnostics.py`

Design reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_DESIGN.md`

## Diagnostics Contract

Added top-level fields:

```text
scoring_profile
score_breakdown
```

Score profile:

```text
api2agent.diagnostics.score_profile.v0
```

`score_breakdown` includes:

```text
base
penalty
score
impact_counts
penalties
finding_impacts
```

The score is now derived from `score_breakdown["score"]`. `status` remains derived from severity summary counts.

## Calibration Evidence

Before this slice, the local real-spec calibration harness reported:

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

After this slice:

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

The intended signal is now clearer:

- metadata-rich schema/auth/server fixtures no longer fail the score threshold just for expected review metadata
- write-heavy unsafe packages still warn and stay below the score threshold
- large surfaces still warn through the calibration harness because `tool_count > 50`

## Validation

Passed:

```text
python -m py_compile api2agent\diagnostics.py scripts\api2agent_openapi_real_spec_calibration.py
```

Passed:

```text
python -m pytest tests\test_diagnostics.py tests\test_openapi_real_spec_calibration.py -q
```

Result:

```text
21 passed
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
212 passed
```

## Compatibility

Compatibility is preserved:

- diagnostics contract version remains `api2agent.capability_diagnostics.v0`
- existing top-level diagnostics fields remain present
- `status` semantics remain severity-based
- generated packages still write `diagnostics.json`
- CLI and README diagnostics summaries continue to read the same `score` field
- added fields are optional for existing consumers

## Next Recommended Task

```text
Agent Capability Compiler Diagnostics Score Calibration Closeout + Phase Review v0
```

The closeout should decide whether the calibrated score profile can close, whether action penalty capping is sufficient for larger cached real specs, and whether the next compiler hardening target should be summary-noise reduction, generic-example reduction, cached real-spec corpus expansion, or another evidence-driven gap.
