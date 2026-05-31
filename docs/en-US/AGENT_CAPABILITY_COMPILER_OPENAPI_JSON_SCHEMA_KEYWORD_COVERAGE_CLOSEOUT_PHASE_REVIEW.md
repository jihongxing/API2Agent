# Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage implementation slice can close.

The compiler now makes common JSON Schema/OpenAPI keyword constraints visible in generated packages, improves deterministic examples for common formats and bounded values, preserves raw keyword metadata for downstream tool consumers, and diagnoses advanced keywords that remain metadata-only.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Real-Spec Calibration Design v0
```

The next design should use real OpenAPI specs to calibrate the compiler's keyword coverage, diagnostics precision, summary readability, and generated example quality before adding another large semantic feature.

## What Is Now Complete

### Design

Completed:

- documented the keyword coverage baseline and gaps
- defined Tier 1 display/example keywords
- defined Tier 2 diagnostics-only keywords
- defined compatibility strategy around raw schema dictionaries
- defined README, inspect, OpenAI tool schema, diagnostics, tests, and dogfood effects
- preserved API-first non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_DESIGN.md`

### Implementation

Completed:

- compact schema summary markers for `format`, `pattern`, `minLength`, `maxLength`, numeric bounds, array bounds, `uniqueItems`, `const`, and `deprecated`
- deterministic keyword-hint examples for `const`, common string formats, simple numeric bounds, bounded `minLength`, and bounded `minItems`
- schema hint counts for visible and advanced keyword categories
- diagnostics for schema keywords, string/numeric/array constraints, const values, deprecated fields, patterns, unsupported keywords, conditional schemas, and dependent schemas
- warning severity for required deprecated request inputs and request-body conditional/dependent schemas
- OpenAI tool schema preservation through existing request-direction shaping
- parser/generator/diagnostics/CLI regression tests
- local dogfood for generate, inspect, diagnose, and manual write examples

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| parser preserves raw keyword metadata | passed |
| README summaries show common keyword markers | passed |
| inspect summaries show common keyword markers | passed |
| inspect reports schema hint counts for keyword categories | passed |
| generated examples prefer explicit examples/defaults/enums before keyword hints | passed |
| generated examples use `const` and common format hints when no explicit sample exists | passed |
| generated examples use simple numeric bounds and bounded `minItems` hints | passed |
| generated OpenAI tool schemas preserve raw keyword metadata after request shaping | passed |
| diagnostics report Tier 1 keyword presence | passed |
| diagnostics report Tier 2 unsupported, conditional, and dependent keywords | passed |
| required deprecated request inputs produce warning severity | passed |
| request-body conditional/dependent schemas produce warning severity | passed |
| existing schema shaping, discriminator handling, response docs, auth/server metadata, and runner behavior remain compatible | passed |
| no full JSON Schema validation, OpenAPI 3.1 dialect engine, runtime validation/coercion, UI form rendering, workflow runtime, marketplace, vault, billing, hosted CRUD, gateway permission source, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile api2agent\schema_shaping.py api2agent\generators\examples.py api2agent\diagnostics.py
```

Passed:

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

Result:

```text
87 passed
```

Passed:

```text
pytest
```

Result:

```text
205 passed
```

Passed local dogfood for:

- `tests\fixtures\openapi\schema_keywords.yaml`
- generated README keyword summaries
- `api2agent inspect` keyword summaries and schema hint counts
- `api2agent diagnose` keyword findings
- generated manual write examples with keyword hints

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The compiler now has enough bounded keyword awareness for practical Agent-facing OpenAPI packages. It does not pretend to be a JSON Schema validator, but it no longer hides important constraints such as email/uuid formats, length bounds, numeric bounds, array cardinality, const values, deprecated fields, or conditional/dependent schema caveats.

This is the right stopping point for v0 keyword coverage. The next highest-leverage move is calibration against real specs, not another abstract keyword expansion.

## Remaining Risks

### Keyword Coverage Is Bounded

The compiler surfaces common keywords and diagnoses advanced ones. It does not implement full JSON Schema semantics for `if`/`then`/`else`, `dependentSchemas`, `patternProperties`, `contains`, `unevaluatedProperties`, or dialect-specific behavior.

### Examples Are Heuristic

Keyword-hint examples are deterministic and useful, but they are not validation proofs. Regex patterns are displayed and diagnosed, not synthesized.

### Summary Readability Needs Real-Spec Calibration

The summary format is compact, but real specs may expose cases where marker density becomes too high or where truncation rules need adjustment.

### Diagnostics Are Advisory

Diagnostics call out constraints and unsupported semantics, but they do not block generation except through existing package quality score semantics.

### OpenAPI 3.1 Dialect Nuance Remains Out Of Scope

The implementation preserves unknown keyword metadata, but it does not select or enforce JSON Schema dialects.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Real-Spec Calibration Design v0
```

That design should choose a small set of real OpenAPI specs and define a repeatable calibration loop for generated summaries, examples, diagnostics, package size, and first-call ergonomics.
