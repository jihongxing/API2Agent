# Agent Capability Compiler OpenAPI Schema Shaping Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Schema Shaping implementation slice can close.

The compiler now preserves raw schema compatibility while making Agent-facing request bodies, examples, README/inspect summaries, OpenAI tool schemas, and diagnostics clearer for common real-world OpenAPI schema shapes.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Discriminator Handling Design v0
```

The next design should focus on discriminator-aware `oneOf` / `anyOf` readability, examples, diagnostics, and generated documentation without turning the compiler into a full JSON Schema validator.

## What Is Now Complete

### Design

Completed:

- documented current schema handling baseline and gaps
- defined additive compatibility strategy without requiring broad IR churn
- defined direction-aware request/response shaping rules
- defined nullable, readOnly/writeOnly, additionalProperties, array, polymorphism, and required/optional policies
- defined generated README, tools schema, examples, inspect, diagnostics, tests, and dogfood effects
- preserved API-first non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_DESIGN.md`

### Implementation

Completed:

- shared schema shaping helpers in `api2agent/schema_shaping.py`
- OpenAPI 3.0 and 3.1 nullable display
- request-direction body shaping that omits `readOnly` fields
- request-direction preservation and display of `writeOnly` fields
- generated examples from shaped request body schemas
- OpenAI tool schema filtering for request bodies
- `additionalProperties` map summaries
- array item summaries and `array[unknown]` for missing `items`
- bounded `oneOf` / `anyOf` summaries
- required versus optional field display
- inspect schema hint counts
- diagnostics for nullable, readOnly request fields, writeOnly response fields, maps, nested polymorphism, arrays without items, and large objects
- schema-shaping fixture and regression tests
- local dogfood for generate, README, inspect, diagnose, and manual write examples

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| raw normalized schema compatibility is preserved | passed |
| request body examples omit read-only fields | passed |
| request body examples preserve write-only fields | passed |
| generated OpenAI tools schema uses request-direction body shaping | passed |
| nullable fields are visible in README and inspect summaries | passed |
| OpenAPI 3.1 nullable type arrays are summarized | passed |
| map semantics from `additionalProperties` are visible | passed |
| arrays show item summaries when known | passed |
| arrays without `items` are shown as `array[unknown]` and diagnosed | passed |
| bounded `oneOf` / `anyOf` summaries are visible | passed |
| required versus optional object fields are visible | passed |
| diagnostics flag schema shapes likely to confuse Agents | passed |
| inspect shows compact schema hint counts | passed |
| old capability JSON without shaped metadata remains valid | passed |
| no full JSON Schema validator, OpenAPI 3.1 dialect engine, LLM schema simplification, runtime schema coercion, UI form rendering, workflow, marketplace, vault, billing, hosted public CRUD, gateway permission source, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile api2agent\schema_shaping.py api2agent\generators\examples.py api2agent\generators\readme.py api2agent\generators\tools.py api2agent\diagnostics.py api2agent\cli.py
```

Passed:

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

Result:

```text
75 passed
```

Passed:

```text
pytest
```

Result:

```text
193 passed
```

Passed local dogfood for:

- `tests\fixtures\openapi\schema_shaping.yaml`
- generated README body summary
- `api2agent inspect` schema hints
- `api2agent diagnose` schema findings
- generated manual write example excluding read-only `id` and preserving write-only `password`

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The compiler now handles the most common Agent-facing schema clarity issues without breaking raw schema compatibility or expanding into a full schema engine. Request bodies are safer for Agent use because obvious server-owned fields are no longer requested by default, and generated summaries make nullable, map, array, polymorphic, and optional shapes visible.

This closes the schema shaping gap identified during OpenAPI real-world hardening.

## Remaining Risks

### Discriminators Are Preserved But Not Used

`oneOf` / `anyOf` branches are now summarized compactly, but discriminator metadata is not yet used to explain branch selection or build better examples.

### Response Shaping Is Mostly Diagnostic

The implementation diagnoses write-only response fields, but generated documentation still focuses primarily on tool inputs rather than rich response shape documentation.

### JSON Schema Coverage Is Intentional But Partial

The implementation handles practical OpenAPI shapes, not every JSON Schema keyword or OpenAPI 3.1 dialect detail.

### Diagnostics Are Advisory

Schema diagnostics help identify likely Agent confusion, but they do not block generation except through existing package quality score semantics.

### Large Schemas Are Bounded, Not Semantically Simplified

Large objects and nested polymorphism are summarized with bounds. Deeper semantic simplification would need explicit product design.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Discriminator Handling Design v0
```

That design should define how discriminator metadata is preserved, displayed, diagnosed, and used for examples while preserving offline deterministic generation and compatibility with existing package schemas.
