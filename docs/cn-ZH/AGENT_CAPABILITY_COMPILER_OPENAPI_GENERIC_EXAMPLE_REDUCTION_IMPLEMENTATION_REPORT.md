# Agent Capability Compiler OpenAPI Generic Example Reduction Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent Capability Compiler 已实现 OpenAPI generic example reduction v0。

Generated sample values 现在会在 source examples/defaults/enums/consts 和 schema format/constraint hints 之后，使用 deterministic name-aware fallbacks。这减少了 README snippets、smoke tests、manual write tests 和 calibration first-call params 中的 `"example"` 这类弱值，同时不改变 raw package contracts 或 runtime behavior。

已实现：

- `example_value` 的 optional `name` context
- `example_for_parameter` 的 parameter name-aware fallback
- 生成 request body examples 时的 object property name-aware fallback
- `user_123`、`Demo`、`active`、`USD`、`cursor_123` 和 `REPLACE_ME` 等 semantic string examples
- `limit=10`、`offset=0` 等 conservative numeric name hints
- format/constraint/source priority preservation
- calibration `generic_example_count`
- calibration `generic_first_call_params`
- name-aware examples、source/format priority、generated packages 和 calibration metrics 的 regression coverage

本 slice 未新增 LLM generation、random fake-data dependency、provider execution、runtime validation、hosted service、workflow runtime、marketplace/provider onboarding、vault、billing、public CRUD、production gateway permission source 或 automatic propagation。

## Files

Implementation：

- `api2agent/generators/examples.py`
- `scripts/api2agent_openapi_real_spec_calibration.py`

Tests：

- `tests/test_examples.py`
- `tests/test_generators.py`
- `tests/test_openapi_real_spec_calibration.py`

Design reference：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_DESIGN.md`

## Behavior Changes

Examples 继续保留现有优先级：

```text
explicit example/default/examples/enum/const
schema format and constraints
name-aware fallback
type fallback
```

重要示例：

```text
user_id -> user_123
name -> Demo
password/token/secret/api_key -> REPLACE_ME
limit/page_size/per_page -> 10
offset -> 0
format=uuid -> 00000000-0000-4000-8000-000000000000
format=email -> user@example.com
```

Fallback 有意保持 fake and deterministic，不发现真实 provider records 或 secrets。

## Dogfood Evidence

运行：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

观察到：

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

Generic first-call evidence：

```text
small_reference_basic first_call_params = {"tool": "get_user", "params": {"user_id": "user_123"}}
schema_rich_keywords first_call_params = {"tool": "get_keyword_user", "params": {"user_id": "00000000-0000-4000-8000-000000000000"}}
generic_example_count = 0 for every generated default calibration case
```

## Validation

已通过：

```text
python -m pytest tests\test_examples.py tests\test_generators.py tests\test_openapi_real_spec_calibration.py tests\test_cli.py tests\test_diagnostics.py -q
```

结果：

```text
82 passed
```

已通过：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

已通过：

```text
python -m pytest -q
```

结果：

```text
217 passed
```

## Compatibility

Compatibility 已保留：

- raw OpenAPI parsing unchanged
- generated `capability.json` schema data unchanged
- generated runner behavior unchanged
- generated MCP schemas unchanged
- diagnostics contract unchanged
- source examples/defaults/enums/consts/formats 仍优先于 name-aware fallback

唯一有意改变的是 generated docs、tests 和 calibration artifacts 中更好的 deterministic sample values。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Closeout + Phase Review v0
```

Closeout 应判断 generic example reduction 是否可以关闭、remaining generic values 是否需要更广 corpus，并判断下一项 compiler target 是 cached real-spec corpus expansion 还是 final Agent Capability Compiler consolidation。
