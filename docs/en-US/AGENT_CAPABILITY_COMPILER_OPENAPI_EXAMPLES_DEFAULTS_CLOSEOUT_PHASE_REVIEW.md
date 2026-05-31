# Agent Capability Compiler OpenAPI Examples + Defaults Propagation Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Examples + Defaults Propagation implementation slice can close.

The compiler now carries source OpenAPI sample data from parsing into generated package artifacts, which makes first local Agent/API calls less generic and more likely to be immediately actionable.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Security Requirement Combinations Design v0
```

The next design should address real-world OpenAPI auth semantics, especially OR vs AND security requirements, query/cookie API keys, and per-tool auth summaries. It must remain API-first and must not add workflow execution, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation.

## What Is Now Complete

### Design

Completed:

- selected examples/defaults propagation as the first OpenAPI hardening implementation slice
- specified source fields to preserve for parameters and request bodies
- specified additive IR model changes
- defined deterministic example selection order
- defined README/test artifact effects
- named tests, dogfood, and non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_WORLD_HARDENING_DESIGN.md`

### Implementation

Completed:

- additive `Parameter.example`
- additive `Parameter.examples`
- additive `RequestBody.example`
- additive `RequestBody.examples`
- parser preservation for OpenAPI parameter `example` and `examples`
- parser preservation for request body media `example` and `examples`
- shared example selection helper for parameters, request bodies, schemas, defaults, examples, enums, and type fallbacks
- README parameter/body details with source examples
- README first-call params using source examples/defaults/enums
- generated read smoke tests using source examples
- generated manual write tests using source body examples while preserving explicit write opt-in
- regression fixture covering parameter examples, examples maps, defaults, body examples, property examples/defaults, and enum fallback

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_EXAMPLES_DEFAULTS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| parameter `example` is preserved | passed |
| parameter `examples` are normalized and preserved | passed |
| request body media `example` is preserved | passed |
| request body media `examples` are normalized and preserved | passed |
| schema defaults/examples/enums feed generated params | passed |
| README first-call commands use source examples/defaults | passed |
| README parameter/body details show useful examples | passed |
| generated smoke tests use source examples for required read inputs | passed |
| generated manual write tests use source body examples | passed |
| write/delete execution remains explicitly opt-in | passed |
| curl-derived object fallback behavior is preserved | passed |
| old capability JSON remains compatible | passed |
| no workflow, marketplace, vault, billing, hosted public CRUD, gateway permission source, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\generators\examples.py api2agent\generators\readme.py api2agent\generators\smoke_test.py
```

Passed:

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_runner_generation.py tests\test_diagnostics.py
```

Result:

```text
40 passed
```

Passed:

```text
pytest
```

Result:

```text
179 passed
```

Passed local generated-runner dogfood against a loopback HTTP target:

- read call used `user_123`, `profile`, and `trace-123`
- opt-in write call used `sku_123` and `quantity: 2`

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

Examples/defaults propagation is now a reliable OpenAPI hardening primitive:

- generated package examples are less generic
- required path/query/header/body inputs have better first-call values
- README guidance and generated tests are aligned
- write safety remains explicit
- the IR change is additive and compatible

This closes the first OpenAPI hardening implementation slice and leaves the compiler in a better position to tackle auth, server, and schema complexity.

## Remaining Risks

### Schema Example Coverage Is Still Conservative

The implementation handles common schema defaults, examples, example arrays, enums, and object properties. Deeply nested polymorphic schemas, nullable shapes, and `oneOf` / `anyOf` readability still need later schema shaping work.

### Diagnostics Do Not Yet Score Example Quality

Diagnostics can benefit from richer evidence now that source examples are preserved, but this slice does not add new diagnostics findings for "required input has usable source sample" vs "required input is generic fallback."

### Real Specs May Use Complex Example Objects

OpenAPI examples objects can include metadata, external references, or media-specific structures. v0 intentionally keeps extraction deterministic and local, using inline `value` when available.

### Auth Semantics Are Now The Bigger Onboarding Gap

After examples/defaults, many real OpenAPI specs will still be hard to use correctly because security requirement combinations are nuanced. Multiple alternatives, API key locations, cookies, and OAuth scope metadata need a dedicated design before implementation.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Security Requirement Combinations Design v0
```

That design should define how OpenAPI document/path/operation security requirements map into per-tool auth metadata, README guidance, diagnostics evidence, and generated runner/proxy behavior while preserving API-first compiler boundaries.
