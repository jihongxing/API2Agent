# Agent Capability Compiler OpenAPI Examples + Defaults Propagation Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI examples/defaults propagation is implemented for the Agent capability compiler.

Generated packages now preserve useful OpenAPI sample data into the IR and reuse it in:

- generated README parameter/body details
- generated README first-call commands
- generated read-only smoke tests
- generated manual write tests
- generated `capability.json`

No workflow engine, marketplace, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation was added.

## Files

Implementation:

- `api2agent/ir/models.py`
- `api2agent/parsers/openapi.py`
- `api2agent/generators/examples.py`
- `api2agent/generators/readme.py`
- `api2agent/generators/smoke_test.py`

Tests and fixtures:

- `tests/fixtures/openapi/examples_defaults.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`

## Contract

The IR model additions are backward-compatible and additive:

- `Parameter.example`
- `Parameter.examples`
- `RequestBody.example`
- `RequestBody.examples`

Existing generated package readers continue to work because old packages can omit these fields and new packages still serialize normal JSON capability data.

## Example Selection

Parameter example selection is deterministic:

1. explicit `parameter.example`
2. first value from `parameter.examples`
3. `schema.default`
4. `schema.example`
5. first value from `schema.examples`
6. first value from `schema.enum`
7. existing type fallback

Request body example selection is deterministic:

1. media `example`
2. first value from media `examples`
3. schema `default`
4. schema `example`
5. first value from schema `examples`
6. object built from required properties using property defaults/examples/enums
7. existing type fallback

For object bodies with no `required` list, the fallback keeps all properties to preserve existing curl-derived README behavior.

## Generated Artifact Effects

README files now show useful examples where source metadata exists:

```text
path: user_id string required example=user_123
query: include string example=profile
header: X-Trace-Id string default=trace-123 required example=trace-123
body: object {sku:string, quantity:integer default=1, priority:string} required example={'sku': 'sku_123', 'quantity': 2}
```

README first-call commands now use source values:

```text
api2agent test . --tool get_user_by_example --params '{"user_id": "user_123", "include": "profile", "X-Trace-Id": "trace-123"}'
```

Generated tests now use source examples/defaults where available while preserving the existing manual write-test guard.

## Dogfood Evidence

Generated an examples/defaults package:

```text
python -m api2agent.cli generate tests\fixtures\openapi\examples_defaults.yaml --output tmp\openapi-examples-defaults --force
```

Observed:

```text
Generated capability package: tmp\openapi-examples-defaults
Diagnostics: warn score=72 errors=0 warnings=2 info=4
```

`inspect` showed three generated tools with expected required parameters and defaults. README and generated tests included:

- `user_123`
- `profile`
- `trace-123`
- `sku_123`
- `quantity: 2`
- `order_123`

Local generated runner dogfood passed through a local loopback HTTP target:

```text
api2agent test tmp\openapi-examples-defaults --tool get_user_by_example --params '{"user_id":"user_123","include":"profile","X-Trace-Id":"trace-123"}'
```

Result:

```text
{'ok': True, 'status_code': 200, 'body': {'method': 'GET', 'path': '/users/user_123?include=profile', 'trace': 'trace-123', 'body': None}}
```

Manual write path remained opt-in and also passed against the local safe target:

```text
api2agent test tmp\openapi-examples-defaults --tool create_order_with_example --allow-write --params '{"body":{"sku":"sku_123","quantity":2}}'
```

Result:

```text
{'ok': True, 'status_code': 200, 'body': {'method': 'POST', 'path': '/orders', 'trace': None, 'body': {'sku': 'sku_123', 'quantity': 2}}}
```

## Compatibility

The implementation is additive:

- old capability JSON remains valid
- curl-derived packages keep object-body fallback behavior
- write/delete tests still require explicit opt-in
- diagnostics behavior remains advisory
- no network dependency is required during generation or regression tests

## Validation

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
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\generators\examples.py api2agent\generators\readme.py api2agent\generators\smoke_test.py
```

Passed:

```text
pytest
```

Result:

```text
179 passed
```

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Examples + Defaults Propagation Closeout + Phase Review v0
```

The closeout should decide whether this first OpenAPI hardening slice can close and whether the next compiler expansion should move to OpenAPI security requirement combinations, server handling, schema shaping, or filtering diagnostics.
