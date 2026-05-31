# Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

Bounded OpenAPI JSON Schema keyword coverage is implemented for the Agent capability compiler.

Generated packages now surface common schema constraints in README and `api2agent inspect`, use deterministic keyword hints for examples, preserve raw keyword metadata in OpenAI tool schemas, and diagnose advanced keywords that remain metadata-only.

The implementation supports:

- compact summary markers for `format`, `pattern`, length bounds, numeric bounds, array bounds, `uniqueItems`, `const`, and `deprecated`
- deterministic examples for `const`, common string formats, simple numeric bounds, string `minLength`, and bounded `minItems`
- inspect schema hint counts for keyword categories
- diagnostics for visible keywords, string/numeric/array constraints, const values, deprecated fields, patterns, unsupported keywords, conditional keywords, and dependent schemas
- warning severity for required deprecated request inputs and request-body conditional/dependent schemas
- raw keyword preservation through the existing schema dictionaries and request-direction OpenAI tool shaping
- local keyword fixture and regression coverage

No full JSON Schema validation, OpenAPI 3.1 dialect engine, runtime request/response validation, runtime coercion, LLM schema simplification, generated SDK type system, UI form rendering, workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation was added.

## Files

Implementation:

- `api2agent/schema_shaping.py`
- `api2agent/generators/examples.py`
- `api2agent/diagnostics.py`

Tests and fixtures:

- `tests/fixtures/openapi/schema_keywords.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

Design reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_DESIGN.md`

## Generated Artifact Effects

README and inspect schema summaries now expose high-signal keyword facts:

```text
path: user_id string format=uuid required
query: email string format=email maxLength=254, legacy string deprecated
body: object {email:string format=email minLength=6 maxLength=254, website:string format=uri?, age:integer min=0 max=150, rating:number exclusiveMin=0 exclusiveMax=5?, tags:array[string minLength=3] minItems=2 maxItems=3 uniqueItems, status:string const=active, legacy_code:string deprecated, activation_date:string format=date?, ...} required
```

Generated manual write examples now use keyword hints when no explicit example/default/enum is available:

```text
{'body': {'email': 'user@example.com', 'age': 1, 'tags': ['example', 'example'], 'status': 'active', 'legacy_code': 'example'}}
```

OpenAI tool schemas still preserve raw schema metadata after request shaping, including `format`, `minItems`, `const`, `dependentRequired`, and conditional `if`/`then` structures.

## Diagnostics

New diagnostics include:

- `schema_keywords_present`
- `string_constraints_present`
- `numeric_constraints_present`
- `array_constraints_present`
- `const_schema_present`
- `deprecated_schema_fields`
- `pattern_schema_present`
- `unsupported_schema_keywords_present`
- `conditional_schema_present`
- `dependent_schema_present`

These findings are deterministic and advisory. Advanced Tier 2 keywords are preserved and diagnosed rather than partially interpreted as validation logic.

## Dogfood Evidence

Generated package:

```text
python -m api2agent.cli generate tests\fixtures\openapi\schema_keywords.yaml --output tmp\openapi-schema-keywords --force
```

Observed:

```text
Generated capability package: tmp\openapi-schema-keywords
Diagnostics: warn score=50 errors=0 warnings=4 info=27
```

`inspect` showed:

```text
Schema hints: array_constraints=2, conditional_schema=1, const_schema=2, dependent_schema=1, deprecated_schema_fields=2, numeric_constraints=3, pattern_schema=2, schema_keywords=23, string_constraints=11, unsupported_schema_keywords=3
```

`diagnose` showed the new keyword findings, including warning severity for required deprecated request fields, conditional request-body schemas, and dependent request-body schemas.

## Compatibility

Compatibility is preserved:

- old capability JSON remains valid because keyword-specific IR fields were not added
- raw schemas remain the source of truth
- generated runner behavior is unchanged
- request/response direction shaping still controls readOnly/writeOnly visibility
- discriminator, response documentation, examples/defaults, security requirements, server metadata, and OpenAI tool schemas remain compatible

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

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Closeout + Phase Review v0
```

The closeout should decide whether the v0 keyword coverage slice is sufficient to close and whether the next compiler hardening target should be real-spec calibration, diagnostics precision, or another high-friction OpenAPI gap.
