# Agent Capability Compiler OpenAPI Summary Noise Reduction Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Summary Noise Reduction implementation slice can close.

Default human-facing package output is now more compact without reducing raw data fidelity. `inspect` folds dense aggregate summaries, clips long detail previews, and selects representative response summaries. `diagnose` groups repeated findings in text output while preserving full JSON. Generated README files now include a Package Overview with diagnostics and key caveats. The calibration harness records summary-density metrics for future regressions.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Design v0
```

The next evidence-driven gap is generic first-call examples. The calibration harness still shows `small_reference_basic` using `user_id: "example"` because the source fixture lacks examples/defaults. Now that score and summary readability are less noisy, improving deterministic first-call params is the highest-leverage compiler hardening target.

## What Is Now Complete

### Design

Completed:

- defined summary noise taxonomy
- defined bounded summary budgets
- defined risk-first rendering order
- defined repeated finding folding
- defined README, inspect, diagnostics text, and calibration harness effects
- defined summary-density metrics
- defined tests, dogfood expectations, compatibility strategy, and non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_DESIGN.md`

### Implementation

Completed:

- compact inspect aggregate rendering
- high-signal schema hint prioritization
- representative inspect response previews
- long detail line clipping
- grouped diagnostics text output
- README Package Overview and key caveats
- calibration summary-density metrics
- regression tests across CLI, diagnostics, README generation, and calibration harness
- dogfood run with 4 pass, 2 warn, 0 fail, and 1 skipped

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| raw package contracts remain unchanged | passed |
| raw diagnostics JSON remains full-fidelity | passed |
| `api2agent inspect --json` remains full-fidelity | passed |
| `api2agent diagnose --json` remains full-fidelity | passed |
| default inspect output folds dense aggregate summaries | passed |
| default inspect output clips long detail previews | passed |
| default inspect output selects representative response previews | passed |
| default diagnostics text groups repeated finding ids | passed |
| README includes Package Overview and key caveats | passed |
| calibration artifact includes summary-density metrics | passed |
| real-spec calibration remains 4 pass, 2 warn, 0 fail, 1 skipped | passed |
| full Python test suite passes | passed |
| no production runtime, provider execution, hosted service, workflow, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation is added | passed |

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
213 passed
```

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The v0 summary budgets are sufficient for the current corpus. The most obvious schema-rich long-line issue is controlled, repeated diagnostics are grouped in text output, and README now starts with a package-level overview before detailed tool notes. The remaining repeated diagnostic group recommendations should stay advisory because they are useful signals for future fixture and real-spec review, not implementation failures.

## Remaining Risks

### Full Text Output Still Has Opinionated Budgets

The defaults are intentionally compact, but future users may want a formal `--verbose` or `--detail full` mode for non-JSON full text output.

### README Tool Sections Can Still Be Large

README keeps tool-level details for compatibility and review. Large packages still need filtering guidance rather than full README compression.

### Repeated Diagnostic Groups Remain Advisory

The calibration harness reports repeated finding groups so reviewers can detect noisy packages. These should not become strict failures until the corpus is larger.

### Generic First-Call Params Remain

The harness still shows generic examples for required fields when source specs lack examples/defaults. This affects first-call quality more directly than remaining summary noise.

### Corpus Is Still Mostly Fixtures

The current offline corpus is stable, but broader confidence still requires a cached real public spec or curated corpus expansion.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Design v0
```

That design should use calibration `first_call_params`, existing schema keyword hints, parameter names, formats, enums, defaults, and examples to reduce generic values such as `"example"` without adding LLM generation, runtime validation, provider calls, or new non-API inputs.
