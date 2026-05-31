# Agent Capability Compiler Diagnostics Score Calibration Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler Diagnostics Score Calibration implementation slice can close.

Diagnostics scoring now separates expected metadata visibility from user-actionable risk while preserving existing diagnostics status semantics. The calibrated profile makes the real-spec harness output easier to trust: metadata-rich schema/auth/server cases no longer look broken just because the compiler is transparent, while write-heavy and large-surface cases remain visible warnings.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Design v0
```

Score calibration fixed the false-low score signal. The next evidence-driven gap is readability density: generated README, inspect output, and diagnostic excerpts now expose plenty of useful metadata, but complex OpenAPI specs still need better grouping and prioritization so humans and Agents can scan the generated package quickly.

## What Is Now Complete

### Design

Completed:

- documented the scoring weakness found by real-spec calibration
- defined compatibility strategy for additive diagnostics fields
- defined impact classes and initial finding mappings
- defined metadata penalty capping
- defined `scoring_profile` and `score_breakdown`
- defined tests and dogfood expectations
- kept parser behavior, runtime validation, provider execution, hosted diagnostics, workflow, marketplace, vault, billing, public CRUD, gateway permission source, and automatic propagation out of scope

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_DESIGN.md`

### Implementation

Completed:

- impact-based scoring in `api2agent/diagnostics.py`
- `api2agent.diagnostics.score_profile.v0`
- top-level `scoring_profile`
- top-level `score_breakdown`
- metadata review penalty cap
- repeated action-finding penalty cap
- zero-penalty readiness findings
- severity-based `status` compatibility
- regression tests for score breakdown shape, metadata-rich fixture scores, blocking findings, and write-heavy unsafe packages
- dogfood run improving OpenAPI real-spec calibration from 1 pass / 5 warn to 4 pass / 2 warn

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| existing diagnostics JSON fields remain present | passed |
| `status` remains severity-based | passed |
| `score` is recalibrated from finding impact/actionability | passed |
| `scoring_profile` is exposed | passed |
| `score_breakdown` explains base, penalties, score, impact counts, and finding impacts | passed |
| readiness findings do not reduce score | passed |
| metadata-rich schema/auth/server cases score above the calibration threshold | passed |
| write-heavy unsafe package remains below the calibration score threshold | passed |
| blocking diagnostics still produce fail status and low score | passed |
| real-spec calibration harness output improves without hiding large-surface warnings | passed |
| full Python test suite passes | passed |
| no production runtime, provider execution, hosted service, workflow, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation is added | passed |

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

Passed local dogfood:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Observed:

```text
OpenAPI real-spec calibration: 4 pass, 2 warn, 0 fail, 1 skipped
```

Passed:

```text
python -m pytest -q
```

Result:

```text
212 passed
```

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The calibrated score profile is sufficient for v0 because it preserves compatibility, provides machine-readable score explanation, and makes calibration output line up with the actual usability risk of the package. It also leaves true risk cases visible: write-only packages, large toolsets, missing base URLs, duplicate tool names, and required bodies without schemas still produce strong signals.

The most important product shift is that diagnostics can now be transparent without making valid metadata-rich packages look unusable.

## Remaining Risks

### Action Penalty Cap Needs More Real Specs

The repeated action-finding cap is calibrated against the current fixture corpus. It should be rechecked once a committed cached real public spec is added.

### Score Is Still Heuristic

The score is deterministic and explainable, but not a runtime success predictor. It should remain an advisory package readiness signal.

### Summary Noise Is Now More Visible

With false-low scores reduced, the next user-facing friction is how much metadata appears in generated summaries, inspect output, README sections, and diagnostics excerpts.

### Generic Examples Still Need Separate Work

The calibration harness still exposes generic first-call params where source specs lack examples/defaults. Reducing that requires a separate examples/defaults or sample synthesis pass.

### Corpus Is Still Mostly Local Fixtures

The offline corpus is stable, but broader confidence requires a checked-in cached real public spec or a curated local corpus expansion.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Design v0
```

That design should use the calibration harness and diagnostics score breakdown to decide how generated README, inspect output, and diagnostic excerpts group, prioritize, and suppress repetitive metadata without hiding safety, auth, server, response, or schema caveats.
