# Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion implementation slice can close.

The compiler now has a committed offline cached real-spec case in the default calibration corpus, with source metadata, checksum verification, redaction/cache policy evidence, path containment checks, additive calibration result fields, regression tests, and dogfood evidence. This is enough for v0. Additional cached public specs should wait until after the final Agent Capability Compiler consolidation review, so the project does not drift into corpus collection before closing the compiler re-entry phase.

Recommended next task:

```text
Agent Capability Compiler Final Re-entry Closeout + Consolidation Review v0
```

That final review should decide whether the Agent Capability Compiler can exit the current re-entry phase at 99%+ completion, what residual risks remain, and whether the project should return to the paused hosted Control Plane backlog or address one last compiler gap.

## What Is Now Complete

### Design

Completed:

- defined cached real-spec source criteria
- defined license/cache metadata requirements
- defined redaction policy
- defined artifact layout
- defined manifest changes
- defined calibration metrics and status thresholds
- defined implementation, tests, dogfood expectations, and non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_DESIGN.md`

### Implementation

Completed:

- cached source metadata support on `CalibrationCase`
- metadata validation for required cached cases
- SHA-256 checksum verification
- cached source and metadata path containment checks
- additive cached-source fields in calibration `result.json`
- committed Apache-2.0 Swagger Petstore excerpt and metadata
- optional user-provided cached spec compatibility
- regression coverage for metadata success, checksum mismatch, missing metadata, path containment, optional skips, and manifest inclusion
- dogfood run with 5 pass, 2 warn, 0 fail, and 1 skipped

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| cached real-spec corpus policy is implemented | passed |
| at least one committed cached real/public-spec case has source metadata | passed |
| normal calibration remains offline and deterministic | passed |
| required cached cases validate checksum, metadata, and path containment | passed |
| optional cached cases still skip cleanly when absent | passed |
| result artifact includes safe source/cache metadata | passed |
| calibration recommendations include cached real-spec issues when present | passed |
| targeted and full test suites pass | passed |
| no LLM generation, provider execution, network-dependent tests, hosted service, workflow, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile scripts\api2agent_openapi_real_spec_calibration.py
```

Passed:

```text
python -m pytest tests\test_openapi_real_spec_calibration.py tests\test_generators.py tests\test_cli.py tests\test_diagnostics.py -q
```

Result:

```text
82 passed
```

Passed:

```text
python -m pytest -q
```

Result:

```text
221 passed
```

Passed local dogfood:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Observed:

```text
OpenAPI real-spec calibration: 5 pass, 2 warn, 0 fail, 1 skipped
```

Passed:

```text
git diff --cached --check
```

## Closeout Judgment

This implementation slice is complete.

One required cached real-spec case is sufficient for v0 because it adds a real public OpenAPI shape without changing the project boundary. The cached Petstore case exercises mixed read/write/delete tools, request bodies, server metadata, `allOf` response schema shaping, default responses, and real-world operation naming. It passes calibration with `tool_count=4`, `diagnostics_score=82`, and `generic_example_count=0`.

More cached specs would be useful later, but adding them now risks turning the final compiler phase into corpus harvesting. The right next step is consolidation: review the whole compiler chain, decide whether remaining risks are acceptable, and make an explicit handoff decision.

## Remaining Risks

### Corpus Is Broader, But Still Small

The corpus now includes a committed real public spec, but only one required cached case. This is enough for v0 confidence expansion, not a comprehensive public API benchmark.

### Cached Spec Is A Curated Excerpt

The Petstore cache is intentionally reduced and redacted. It is real public material, but it does not prove behavior on very large production specs.

### Repeated Finding Groups Remain Advisory

The cached Petstore case adds repeated diagnostic groups to the recommendation list. This is useful review signal, not a failure.

### Write/Delete Presence Still Needs Human Review

The cached case includes write/delete tools but also read tools, so it passes. Operators still need explicit review before executing write/delete tools.

### Final Consolidation Is Still Needed

The compiler has accumulated many hardening slices. A final re-entry closeout should verify that the docs, tests, calibration signals, and next-project direction are aligned.

## Phase Review

Agent Capability Compiler completion estimate:

```text
99%
```

The remaining 1% is final consolidation rather than a known implementation hole. The compiler now has core OpenAPI semantics, diagnostics, examples, summaries, calibration, and one cached real public spec in the default evidence loop.

## Next Recommended Task

```text
Agent Capability Compiler Final Re-entry Closeout + Consolidation Review v0
```

That review should summarize the full Agent Capability Compiler re-entry, list residual risks, decide whether the compiler can pause, and name the next project lane.
