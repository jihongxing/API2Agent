# Agent Capability Compiler OpenAPI Response Shape Documentation Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI response shape documentation is implemented for the Agent capability compiler.

Generated packages now preserve response content metadata and make response status codes, categories, schemas, examples, and error/default outcomes visible in README, inspect, diagnostics, and generated `capability.json`.

The implementation supports:

- additive response metadata in `ResponseShape`
- deterministic response content selection
- response content type and content type variant preservation
- response examples and examples maps
- compact response summary formatting
- README response sections under each tool
- `api2agent inspect` response summaries and response category counts
- diagnostics for documented schemas, examples, missing schemas, missing success schemas, structured error bodies, default responses, multiple content types, and polymorphic response schemas
- response-direction schema summaries that avoid showing `writeOnly` fields as returned values
- local response-shape fixture and regression coverage

No runtime response validation, runtime response coercion, LLM response transformation, generated SDK response types, UI response viewer, workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation was added.

## Files

Implementation:

- `api2agent/ir/models.py`
- `api2agent/parsers/openapi.py`
- `api2agent/response_docs.py`
- `api2agent/generators/readme.py`
- `api2agent/diagnostics.py`
- `api2agent/cli.py`

Tests and fixtures:

- `tests/fixtures/openapi/response_shapes.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

Design reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_DESIGN.md`

## Contract

Existing response schema compatibility is preserved:

```text
Response.schema_
```

The implementation adds optional fields:

```text
ResponseShape.content_type
ResponseShape.content_types
ResponseShape.example
ResponseShape.examples
```

Old generated `capability.json` files that only contain `status_code`, `description`, and `schema` remain valid.

Generated runner behavior is unchanged. Runners still return raw execution results:

```text
ok
status_code
body
error
```

## Response Extraction

OpenAPI response extraction now:

- preserves response status codes as strings, including `default`
- preserves descriptions
- selects `application/json` when present
- otherwise selects the first content entry deterministically
- preserves selected `content_type`
- preserves all offered `content_types`
- extracts selected content schema
- preserves selected content `example` and `examples`
- does not merge content types
- does not validate examples against schemas

## Generated Artifact Effects

README now includes response summaries under tools:

```text
  - responses:
    - 200 success application/json object {id:string readOnly, name:string} example={"id": "item_123", "name": "Demo"} - OK
    - 204 success no documented body - No Content
    - 400 client_error application/json object {error:string, code:string?} example={"code": "invalid", "error": "invalid_request"} - Bad request
    - default default application/json object {error:string, code:string?} - Default error
```

`api2agent inspect` now shows response category counts:

```text
Response categories: client_error=2, default=1, success=4
```

Per-tool inspect output now includes response summaries:

```text
responses: 200 success application/json object {id:string readOnly, name:string}; 204 success no documented body; 400 client_error application/json object {error:string, code:string?}; default default application/json object {error:string, code:string?}
```

Response-direction summaries reuse schema shaping and discriminator handling. For example, `writeOnly` response fields are not shown as returned values, and polymorphic response summaries can show discriminator mappings:

```text
200 success application/json oneOf[discriminator=kind: hit=>SearchHit | empty=>SearchEmpty]
```

## Diagnostics

New diagnostics include:

- `response_schema_present`
- `response_example_present`
- `response_without_schema`
- `success_response_without_schema`
- `error_response_schema_present`
- `default_response_present`
- `multiple_response_content_types`
- `response_polymorphic_schema`

These findings are deterministic and advisory. They do not validate runtime responses or block generation except through existing package quality score semantics.

## Dogfood Evidence

Generated package:

```text
python -m api2agent.cli generate tests\fixtures\openapi\response_shapes.yaml --output tmp\openapi-response-shapes --force
```

Observed:

```text
Generated capability package: tmp\openapi-response-shapes
Diagnostics: warn score=70 errors=0 warnings=2 info=20
```

`inspect` showed:

```text
Response categories: client_error=2, default=1, success=4
responses: 200 success application/json object {id:string readOnly, name:string}; 204 success no documented body; 400 client_error application/json object {error:string, code:string?}; default default application/json object {error:string, code:string?}
```

`diagnose` showed the new response documentation findings:

```text
response_schema_present
response_example_present
response_without_schema
success_response_without_schema
error_response_schema_present
default_response_present
multiple_response_content_types
response_polymorphic_schema
```

## Compatibility

Compatibility is preserved:

- old capability JSON without response metadata remains valid
- raw response schemas remain the source of truth
- generated runner behavior is unchanged
- response docs use response-direction schema shaping
- request-body shaping, discriminator handling, examples/defaults, security requirements, server metadata, and OpenAI tool schemas remain compatible

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

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Response Shape Documentation Closeout + Phase Review v0
```

The closeout should decide whether this response documentation slice can close and whether the next OpenAPI hardening target should be deeper JSON Schema keyword coverage, response examples calibration against more real specs, or another high-friction real-spec gap.
