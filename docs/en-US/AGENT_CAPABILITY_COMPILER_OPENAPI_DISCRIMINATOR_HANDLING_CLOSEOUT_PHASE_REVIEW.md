# Agent Capability Compiler OpenAPI Discriminator Handling Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Discriminator Handling implementation slice can close.

The compiler now preserves raw discriminator metadata while making discriminator-aware `oneOf` / `anyOf` schemas clearer in generated README summaries, inspect output, OpenAI tool schemas, request examples, and diagnostics.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Response Shape Documentation Design v0
```

The next design should focus on richer generated response documentation for Agents without turning the compiler into a full JSON Schema validator, SDK type generator, UI form system, or runtime response validator.

## What Is Now Complete

### Design

Completed:

- documented current discriminator handling baseline and gaps
- defined compatibility strategy using raw OpenAPI schema dictionaries as the source of truth
- defined discriminator extraction from `propertyName`, `mapping`, `oneOf`, and `anyOf`
- defined bounded summary formatting for discriminator-aware polymorphic schemas
- defined deterministic request example behavior using discriminator mapping keys
- defined README, inspect, OpenAI tools schema, diagnostics, tests, and dogfood effects
- preserved API-first non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_DESIGN.md`

### Implementation

Completed:

- discriminator extraction helpers in `api2agent/schema_shaping.py`
- discriminator-aware `oneOf` / `anyOf` summaries
- mapping key display in bounded polymorphic summaries
- discriminator-aware generated request body example fallback selection
- discriminator property insertion in generated request examples
- request-direction readOnly filtering inside polymorphic branches
- writeOnly preservation inside generated request body examples and OpenAI tool schemas
- inspect schema hint counts for discriminators and discriminator mappings
- diagnostics for discriminator presence, mappings, missing `propertyName`, discriminator without polymorphism, unresolved mappings, and untagged branches
- discriminator fixture and parser/generator/diagnostics/CLI regression tests
- local dogfood for generate, inspect, diagnose, generated README summaries, OpenAI tool schema preservation, and manual write examples

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| raw discriminator metadata is preserved | passed |
| discriminator property is shown in schema summaries | passed |
| mapping keys are shown in bounded summaries | passed |
| generated examples include discriminator values | passed |
| request-direction shaping is preserved inside polymorphic branches | passed |
| OpenAI tool schemas preserve discriminator metadata | passed |
| inspect shows discriminator hint counts | passed |
| diagnostics report discriminator presence and mappings | passed |
| diagnostics report missing discriminator `propertyName` | passed |
| diagnostics report discriminator without polymorphism | passed |
| diagnostics report unresolved mappings | passed |
| diagnostics report branches without matching discriminator tags | passed |
| parser/generator/diagnostics/CLI regression tests are added | passed |
| old capability JSON without discriminator metadata remains valid | passed |
| no full JSON Schema validator, runtime validation, LLM branch selection, SDK type system, UI forms, workflow runtime, marketplace, vault, billing, hosted public CRUD, gateway permission source, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile api2agent\schema_shaping.py api2agent\generators\examples.py api2agent\diagnostics.py api2agent\cli.py
```

Passed:

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

Result:

```text
79 passed
```

Passed:

```text
pytest
```

Result:

```text
197 passed
```

Passed local dogfood for:

- `tests\fixtures\openapi\discriminator.yaml`
- generated README body summary
- `api2agent inspect` discriminator schema hints
- `api2agent diagnose` discriminator findings
- generated manual write example selecting and setting the discriminator value

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The compiler now uses discriminator metadata where it most helps Agent capability packages: human-readable polymorphic summaries, deterministic example generation, inspect hints, and advisory diagnostics. It keeps raw schema compatibility and avoids crossing into runtime branch validation or type generation.

This closes the discriminator handling gap identified after schema shaping.

## Remaining Risks

### Branch Matching Is Pragmatic

Mapping and tag matching use available resolved branch labels, titles, and tag property values. This is useful for generated capability clarity but is not full discriminator semantic validation.

### Mapping Resolution Is Bounded

Some `$ref` intent cannot be fully reconstructed after normalization. Unresolved mappings are reported through diagnostics rather than treated as generation blockers.

### Response Documentation Remains Sparse

Request body examples and tool input schemas are now much clearer, but generated response documentation still lacks the same richness for success/error payloads and polymorphic response bodies.

### Diagnostics Are Advisory

Discriminator diagnostics identify likely Agent confusion. They do not block generation except through existing package quality score semantics.

### No Runtime Branch Validation

Generated runners do not coerce payloads, validate branch selection at runtime, or select branches with an LLM.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Response Shape Documentation Design v0
```

That design should define how generated documentation, inspect output, diagnostics, and dogfood evidence should represent response payload shapes, status-code differences, error bodies, examples, and schema caveats while preserving deterministic offline generation and compatibility with existing package schemas.
