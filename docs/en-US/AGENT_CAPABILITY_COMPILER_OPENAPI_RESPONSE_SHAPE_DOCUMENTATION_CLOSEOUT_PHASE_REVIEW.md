# Agent Capability Compiler OpenAPI Response Shape Documentation Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Response Shape Documentation implementation slice can close.

The compiler now makes response status codes, categories, content types, schemas, examples, structured error bodies, default responses, and response documentation caveats visible in generated packages without changing runtime runner behavior.

Recommended next task:

```text
Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Design v0
```

The next design should focus on practical, high-signal JSON Schema/OpenAPI schema keywords that improve Agent-facing docs and examples while staying deterministic, offline, and compatibility-preserving.

## What Is Now Complete

### Design

Completed:

- documented response documentation baseline and gaps
- defined additive response metadata strategy
- defined deterministic response content selection rules
- defined response status category and summary formatting rules
- defined README, inspect, diagnostics, parser, runner, tests, and dogfood effects
- preserved API-first non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_DESIGN.md`

### Implementation

Completed:

- optional response metadata in `ResponseShape`
- deterministic OpenAPI response content selection
- selected content type and content type variant preservation
- response `example` and `examples` extraction
- shared response summary formatting helpers
- generated README response sections under each tool
- `api2agent inspect` response category counts and per-tool response summaries
- diagnostics for response schemas, examples, missing schemas, missing success schemas, structured error bodies, default responses, multiple content types, and polymorphic response schemas
- response-direction summaries that avoid showing `writeOnly` fields as returned values
- response-shape fixture and parser/generator/diagnostics/CLI regression tests
- local dogfood for generate, README, inspect, and diagnose

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| old capability JSON without response metadata remains valid | passed |
| raw response schemas remain the source of truth | passed |
| selected response content type is preserved | passed |
| offered response content types are preserved | passed |
| response examples and examples maps are preserved | passed |
| README shows response status codes and categories | passed |
| README shows compact response schema summaries | passed |
| README shows no-body and default responses clearly | passed |
| README avoids showing `writeOnly` response fields as returned values in schema summaries | passed |
| inspect shows response category counts | passed |
| inspect shows per-tool response summaries | passed |
| diagnostics report response schema presence and examples | passed |
| diagnostics report missing response schemas and missing success schemas | passed |
| diagnostics report structured error bodies, default responses, multiple content types, and polymorphic responses | passed |
| generated runner behavior is unchanged | passed |
| parser/generator/diagnostics/CLI regression tests are added | passed |
| no runtime response validation, runtime response coercion, LLM response transformation, generated SDK response types, UI response viewer, workflow runtime, marketplace, vault, billing, hosted public CRUD, gateway permission source, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\response_docs.py api2agent\generators\readme.py api2agent\diagnostics.py api2agent\cli.py
```

Passed:

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

Result:

```text
83 passed
```

Passed:

```text
pytest
```

Result:

```text
201 passed
```

Passed local dogfood for:

- `tests\fixtures\openapi\response_shapes.yaml`
- generated README response summaries
- `api2agent inspect` response category counts and per-tool response summaries
- `api2agent diagnose` response documentation findings

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

Generated packages now give Agents enough response-shape context to understand common success, no-body, error, and default outcomes before execution. The implementation closes the response documentation asymmetry that remained after request schema shaping and discriminator handling.

This is intentionally documentation-first. It does not validate provider responses, coerce outputs, or create SDK response types.

## Remaining Risks

### Content Negotiation Is Not Runtime Behavior

The compiler preserves offered content types and selects one deterministically for documentation. It does not perform runtime content negotiation or merge multiple response media types.

### Examples Are Preserved, Not Validated

Source response examples are displayed when present, but they are not validated against schemas or scrubbed beyond existing source-trust boundaries.

### Diagnostics Are Advisory

Response documentation diagnostics identify missing or ambiguous docs. They do not block generation except through existing package quality score semantics.

### Runtime Output Validation Is Still Out Of Scope

Generated runners continue returning raw `ok`, `status_code`, `body`, and `error` values. They do not validate, coerce, or normalize response bodies.

### JSON Schema Keyword Coverage Remains Partial

The compiler now displays many practical schema shapes, but keywords such as `format`, `pattern`, `minLength`, `maxLength`, `minimum`, `maximum`, `minItems`, `maxItems`, `uniqueItems`, `deprecated`, `const`, `dependentRequired`, and conditional schemas still need explicit product design before implementation.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Design v0
```

That design should select a bounded set of high-value schema keywords for Agent-facing summaries, examples, diagnostics, and compatibility tests without turning the compiler into a full JSON Schema validator.
