# Agent Capability Compiler OpenAPI Generic Example Reduction Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Generic Example Reduction implementation slice can close.

Generated sample params now use deterministic name-aware fallbacks after source examples, defaults, enums, consts, formats, and schema constraints. The result is better first-call quality for generated README snippets, smoke tests, manual write tests, and calibration artifacts while preserving raw OpenAPI package contracts and runtime behavior.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Design v0
```

The strongest remaining compiler risk is corpus breadth. The default calibration set is now clean on generic examples, calibrated on diagnostics score, and readable enough for review, but it still relies mostly on fixtures plus a synthetic large spec. The next design should define how to add a committed cached real public OpenAPI spec or curated local real-spec corpus without network dependency, provider execution, hosted runtime work, or legal/licensing ambiguity.

## What Is Now Complete

### Design

Completed:

- defined deterministic name-aware fallback rules
- preserved explicit source/schema priority
- defined object property name threading
- defined conservative numeric and boolean name hints
- defined calibration generic example metrics
- defined tests, dogfood expectations, compatibility strategy, and non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_DESIGN.md`

### Implementation

Completed:

- optional `name` context in `example_value`
- parameter name-aware examples through `example_for_parameter`
- object property name-aware examples for request bodies
- secret-safe placeholders such as `REPLACE_ME`
- semantic deterministic fallbacks such as `user_123`, `Demo`, `active`, `USD`, and `cursor_123`
- conservative numeric fallbacks such as `limit=10`, `page=1`, and `offset=0`
- calibration `generic_example_count`
- calibration `generic_first_call_params`
- regression coverage for source/schema priority, generated packages, and calibration metrics
- dogfood run with 4 pass, 2 warn, 0 fail, and 1 skipped

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| name-aware example fallback is implemented | passed |
| source examples/defaults/enums/consts still win | passed |
| schema formats and constraints still win over name rules | passed |
| object properties receive property-name context | passed |
| secret-like names use safe placeholders | passed |
| numeric name hints stay conservative | passed |
| generic first-call params decrease in calibration output | passed |
| default generated calibration cases report zero generic examples | passed |
| generated README/smoke/manual examples remain deterministic | passed |
| calibration artifact records generic example metrics | passed |
| targeted and full Python test suites pass | passed |
| no LLM generation, provider execution, runtime validation, hosted service, workflow, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile api2agent\generators\examples.py scripts\api2agent_openapi_real_spec_calibration.py
```

Passed:

```text
python -m pytest tests\test_examples.py tests\test_generators.py tests\test_openapi_real_spec_calibration.py tests\test_cli.py tests\test_diagnostics.py -q
```

Result:

```text
82 passed
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
217 passed
```

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The original concrete gap is closed: `small_reference_basic.first_call_params.params.user_id` is now `user_123` instead of `"example"`. Format-aware behavior remains intact, shown by `schema_rich_keywords.first_call_params.params.user_id` staying a UUID-shaped value. Default generated calibration cases now report `generic_example_count = 0` and empty `generic_first_call_params`.

The fallback remains intentionally fake, deterministic, and local. It improves reviewability and first-call ergonomics, but it does not claim provider validity or discover real IDs/secrets.

## Remaining Risks

### Corpus Breadth Is Still The Largest Gap

The calibration corpus is stable and useful, but it is still mostly fixtures plus a synthetic large spec. A cached real public spec is now the highest-signal way to find remaining compiler gaps.

### Name Rules Are Bounded Heuristics

The fallback rules cover common API names, but they are not semantic understanding. Unknown names still fall back to type-level defaults by design.

### Example Quality Is Advisory

Generated examples help README, tests, and calibration first-call params. Runtime validation and provider-specific validity remain out of scope.

### Write-Heavy Packages Still Need Human Review

`write_heavy_unsafe` remains a warning because write/delete-only generated packages need explicit operator review regardless of better example values.

### Large Package Filtering Remains Important

`large_rest_synthetic` remains a warning because packages with more than 50 tools should still be narrowed before Agent use.

## Phase Review

Agent Capability Compiler completion estimate:

```text
98%
```

The compiler has now closed the core OpenAPI hardening chain: diagnostics, examples/defaults, security combinations, server handling, schema shaping, discriminator handling, response documentation, bounded JSON Schema keyword coverage, real-spec calibration, score calibration, summary noise reduction, and generic example reduction.

The remaining 2% is not a single known implementation bug. It is confidence work: broader real-spec calibration, final corpus-backed review, and a last consolidation pass that decides whether Agent Capability Compiler can exit this re-entry phase.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Design v0
```

That design should define the source criteria, licensing and cache policy, artifact location, calibration manifest changes, redaction rules, expected metrics, and pass/warn thresholds for adding one or more cached real specs while keeping the harness offline and deterministic.
