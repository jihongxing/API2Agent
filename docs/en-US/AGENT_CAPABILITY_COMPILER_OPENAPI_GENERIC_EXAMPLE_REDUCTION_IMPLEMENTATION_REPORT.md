# Agent Capability Compiler OpenAPI Generic Example Reduction Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI generic example reduction v0 is implemented for the Agent Capability Compiler.

Generated sample values now use deterministic name-aware fallbacks after source examples/defaults/enums/consts and schema format/constraint hints. This reduces weak values such as `"example"` in README snippets, smoke tests, manual write tests, and calibration first-call params without changing raw package contracts or runtime behavior.

Implemented:

- optional `name` context in `example_value`
- parameter name-aware fallback through `example_for_parameter`
- object property name-aware fallback when generating request body examples
- semantic string examples such as `user_123`, `Demo`, `active`, `USD`, `cursor_123`, and `REPLACE_ME`
- conservative numeric name hints such as `limit=10` and `offset=0`
- format/constraint/source priority preservation
- calibration `generic_example_count`
- calibration `generic_first_call_params`
- regression coverage for name-aware examples, source/format priority, generated packages, and calibration metrics

No LLM generation, random fake-data dependency, provider execution, runtime validation, hosted service, workflow runtime, marketplace/provider onboarding, vault, billing, public CRUD, production gateway permission source, or automatic propagation was added.

## Files

Implementation:

- `api2agent/generators/examples.py`
- `scripts/api2agent_openapi_real_spec_calibration.py`

Tests:

- `tests/test_examples.py`
- `tests/test_generators.py`
- `tests/test_openapi_real_spec_calibration.py`

Design reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_DESIGN.md`

## Behavior Changes

Examples now preserve the existing priority:

```text
explicit example/default/examples/enum/const
schema format and constraints
name-aware fallback
type fallback
```

Important examples:

```text
user_id -> user_123
name -> Demo
password/token/secret/api_key -> REPLACE_ME
limit/page_size/per_page -> 10
offset -> 0
format=uuid -> 00000000-0000-4000-8000-000000000000
format=email -> user@example.com
```

The fallback is intentionally fake and deterministic. It does not discover real provider records or secrets.

## Dogfood Evidence

Run:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Observed:

```text
OpenAPI real-spec calibration: 4 pass, 2 warn, 0 fail, 1 skipped
- small_reference_basic: pass tools=1 score=87
- schema_rich_keywords: pass tools=2 score=70
- auth_rich_security: pass tools=5 score=62
- server_rich_choices: pass tools=3 score=62
- write_heavy_unsafe: warn tools=2 score=56 - diagnostics_score < 60; no read tools when write/delete tools exist
- large_rest_synthetic: warn tools=60 score=82 - tool_count > 50
- optional_cached_real_spec: skipped tools=0 score=None - optional source_path is not present
```

Generic first-call evidence:

```text
small_reference_basic first_call_params = {"tool": "get_user", "params": {"user_id": "user_123"}}
schema_rich_keywords first_call_params = {"tool": "get_keyword_user", "params": {"user_id": "00000000-0000-4000-8000-000000000000"}}
generic_example_count = 0 for every generated default calibration case
```

## Validation

Passed:

```text
python -m pytest tests\test_examples.py tests\test_generators.py tests\test_openapi_real_spec_calibration.py tests\test_cli.py tests\test_diagnostics.py -q
```

Result:

```text
82 passed
```

Passed:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Passed:

```text
python -m pytest -q
```

Result:

```text
217 passed
```

## Compatibility

Compatibility is preserved:

- raw OpenAPI parsing is unchanged
- generated `capability.json` schema data remains unchanged
- generated runner behavior is unchanged
- generated MCP schemas are unchanged
- diagnostics contract is unchanged
- source examples/defaults/enums/consts/formats still win over name-aware fallback

The intentional behavior change is better deterministic sample values in generated docs, tests, and calibration artifacts.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Closeout + Phase Review v0
```

The closeout should decide whether generic example reduction can close, whether remaining generic values need a broader corpus, and whether the next compiler target should be cached real-spec corpus expansion or final Agent Capability Compiler consolidation.
