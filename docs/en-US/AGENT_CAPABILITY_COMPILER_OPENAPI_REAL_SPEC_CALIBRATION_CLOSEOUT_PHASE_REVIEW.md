# Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Real-Spec Calibration Harness implementation slice can close.

The compiler now has a repeatable, offline evidence loop for comparing generated OpenAPI packages across small, schema-rich, auth-rich, server-rich, write-heavy, and large-surface cases. The harness produces a machine-readable artifact and concise review output without changing generated package contracts or production runtime behavior.

Recommended next task:

```text
Agent Capability Compiler Diagnostics Score Calibration Design v0
```

The calibration run showed that metadata-rich packages can produce very low diagnostic scores even when the warnings are expected and reviewable. The next design should separate user-actionable risk from expected metadata richness so diagnostics remain useful as the compiler handles more realistic specs.

## What Is Now Complete

### Design

Completed:

- documented why real-spec calibration follows keyword coverage
- defined purpose-labeled corpus slots
- defined metric contract and result artifact
- defined pass/warn/fail/skipped status behavior
- defined harness, manifest, artifact, tests, dogfood, and non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_DESIGN.md`

### Implementation

Completed:

- `scripts/api2agent_openapi_real_spec_calibration.py`
- local default manifest with stable fixtures
- local synthetic large OpenAPI spec generation
- optional cached real-spec skip behavior
- package generation and metric extraction
- inspect-style excerpts and sample tool details
- first-call params capture
- status classification and recommendations
- `.dogfood/openapi-real-spec-calibration/result.json`
- regression tests for manifest coverage, path containment, status classification, optional skips, artifact contract, and large-surface warnings
- dogfood run with 1 pass, 5 warn, 0 fail, and 1 skipped

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| calibration can run locally without network access | passed |
| result artifact is machine-readable | passed |
| default corpus includes small, schema-rich, auth-rich, server-rich, write-heavy, and large-surface cases | passed |
| optional cached real-spec inputs skip cleanly when absent | passed |
| package metrics are comparable across cases | passed |
| oversized packages are visible | passed |
| diagnostics-heavy cases are visible | passed |
| inspect excerpts and sample tool details are captured | passed |
| first-call params are captured for a representative tool | passed |
| generated output paths are contained under the dogfood calibration directory | passed |
| full Python test suite passes | passed |
| no production runtime, provider execution, hosted service, workflow, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation is added | passed |

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

Passed local dogfood:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Observed:

```text
OpenAPI real-spec calibration: 1 pass, 5 warn, 0 fail, 1 skipped
```

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The harness gives the compiler a working measurement loop. It is intentionally local and report-oriented: it does not execute providers, enforce runtime validation, or add production CLI/runtime behavior. It is enough to make future hardening decisions evidence-driven.

The first useful signal is already visible: score calibration needs attention. `auth_rich_security`, `server_rich_choices`, and `schema_rich_keywords` are valuable calibration cases, but their diagnostic scores are low because expected metadata warnings currently count like user-actionable risks.

## Remaining Risks

### Corpus Still Uses Mostly Fixtures

The default corpus is stable and offline, but it does not yet include a committed cached real public spec. The optional case enables this later without making the harness network-dependent.

### Score Semantics Are Too Blunt

Diagnostics score currently penalizes warning and info volume uniformly. Metadata-rich but well-explained packages can score too low.

### Summary Noise Needs Better Measurement

The harness captures excerpts, but it does not yet compute a summary-density score or identify the exact fields causing readability issues.

### Generic Examples Remain Visible

The harness now exposes generic first-call params, but reducing them requires a separate examples/defaults calibration pass.

### Calibration Is Report-Oriented

The harness is not yet a CI gate. This is intentional until score semantics and corpus composition stabilize.

## Next Recommended Task

```text
Agent Capability Compiler Diagnostics Score Calibration Design v0
```

That design should use the calibration harness output to distinguish expected metadata-rich findings from user-actionable risks, refine score penalties, and define tests that keep diagnostics useful without hiding real failures.
