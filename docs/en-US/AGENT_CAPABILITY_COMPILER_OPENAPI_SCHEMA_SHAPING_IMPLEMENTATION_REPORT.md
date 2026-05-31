# Agent Capability Compiler OpenAPI Schema Shaping Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI schema shaping is implemented for the Agent capability compiler.

Generated packages now preserve raw normalized schemas while using direction-aware shaping for Agent-facing request bodies, generated examples, README/inspect summaries, OpenAI tool schemas, and schema diagnostics.

The implementation supports:

- OpenAPI 3.0 `nullable: true` display
- OpenAPI 3.1 `type: ["string", "null"]` display
- request-direction filtering of `readOnly` body fields
- request-direction preservation of `writeOnly` fields
- response diagnostics for `writeOnly` fields
- `additionalProperties` map/object summaries
- array item summaries and `array[unknown]` for arrays without `items`
- compact `oneOf` / `anyOf` summaries
- required versus optional object field display
- inspect schema hint counts
- deterministic diagnostics for schema complexity and directionality

No full JSON Schema validator, OpenAPI 3.1 dialect engine, LLM schema simplification, runtime schema coercion, UI form rendering, workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation was added.

## Files

Implementation:

- `api2agent/schema_shaping.py`
- `api2agent/generators/examples.py`
- `api2agent/generators/readme.py`
- `api2agent/generators/tools.py`
- `api2agent/diagnostics.py`
- `api2agent/cli.py`

Tests and fixtures:

- `tests/fixtures/openapi/schema_shaping.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

## Contract

The implementation does not add required IR fields.

Existing raw schema fields remain the compatibility source of truth:

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

Direction-aware shaping is derived at generation time:

```text
request body input schema -> omit readOnly fields, keep writeOnly fields
response output schema -> diagnose writeOnly fields
neutral docs schema -> preserve markers and summarize compactly
```

Old generated `capability.json` files remain valid.

## Generated Artifact Effects

README and inspect now use compact shaped schema summaries. Example output:

```text
body: object {name:string, nickname:string nullable?, password:string writeOnly, labels:object map[string]?, tags:array[object {key:string, value:string?}]?, loose:array[unknown]?, choice:oneOf[string | object {nested:anyOf[string | integer]?}]?} required
```

`api2agent inspect` now shows schema hint counts:

```text
Schema hints: arrays_without_items=1, maps=2, nested_polymorphic=2, nullable=3, polymorphic=2, read_only=2, write_only=2
```

Generated OpenAI tools schemas use request-direction shaping for request bodies, so `readOnly` fields are not requested as Agent inputs.

Generated manual write examples use shaped request body schemas:

```text
{'body': {'name': 'example', 'password': 'example'}}
```

## Diagnostics

New diagnostics include:

- `nullable_fields_present`
- `read_only_request_fields`
- `write_only_response_fields`
- `additional_properties_present`
- `nested_polymorphic_schema`
- `array_without_item_schema`
- `large_object_schema`

These findings are advisory except `array_without_item_schema`, which is a warning because generated examples cannot infer element shape safely.

## Dogfood Evidence

Generated package:

```text
python -m api2agent.cli generate tests\fixtures\openapi\schema_shaping.yaml --output tmp\openapi-schema-shaping --force
```

Observed:

```text
Generated capability package: tmp\openapi-schema-shaping
Diagnostics: warn score=50 errors=0 warnings=4 info=10
```

`inspect` showed:

```text
Schema hints: arrays_without_items=1, maps=2, nested_polymorphic=2, nullable=3, polymorphic=2, read_only=2, write_only=2
body: object {name:string, nickname:string nullable?, password:string writeOnly, labels:object map[string]?, tags:array[object {key:string, value:string?}]?, loose:array[unknown]?, choice:oneOf[string | object {nested:anyOf[string | integer]?}]?} required
```

`diagnose` showed the new schema findings:

```text
read_only_request_fields
nullable_fields_present
additional_properties_present
nested_polymorphic_schema
array_without_item_schema
write_only_response_fields
```

Generated manual write example excluded the `readOnly` `id` field and preserved the `writeOnly` `password` field:

```text
{'body': {'name': 'example', 'password': 'example'}}
```

## Compatibility

Compatibility is preserved:

- parser still preserves raw source schema metadata
- existing `allOf` merge and `oneOf` / `anyOf` preservation remain compatible
- existing `capability.json` schema fields remain unchanged
- old capability JSON without shaped metadata remains valid
- generated examples still prefer explicit examples/defaults/enums before type fallbacks
- generated runner behavior is unchanged

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

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Schema Shaping Closeout + Phase Review v0
```

The closeout should decide whether this schema shaping slice can close and whether the next OpenAPI hardening target should be response shaping depth, discriminator handling, or another real-spec friction point.
