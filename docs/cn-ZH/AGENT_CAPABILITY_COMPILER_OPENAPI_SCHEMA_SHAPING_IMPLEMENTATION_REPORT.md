# Agent Capability Compiler OpenAPI Schema Shaping Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent capability compiler 已实现 OpenAPI schema shaping。

Generated packages 现在会保留 raw normalized schemas，同时在 Agent-facing request bodies、generated examples、README/inspect summaries、OpenAI tool schemas 和 schema diagnostics 中使用 direction-aware shaping。

本实现支持：

- OpenAPI 3.0 `nullable: true` display
- OpenAPI 3.1 `type: ["string", "null"]` display
- request-direction filtering of `readOnly` body fields
- request-direction preservation of `writeOnly` fields
- response diagnostics for `writeOnly` fields
- `additionalProperties` map/object summaries
- array item summaries，以及缺少 `items` 时显示 `array[unknown]`
- compact `oneOf` / `anyOf` summaries
- required versus optional object field display
- inspect schema hint counts
- deterministic diagnostics for schema complexity and directionality

本 slice 未增加 full JSON Schema validator、OpenAPI 3.1 dialect engine、LLM schema simplification、runtime schema coercion、UI form rendering、workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## Files

Implementation：

- `api2agent/schema_shaping.py`
- `api2agent/generators/examples.py`
- `api2agent/generators/readme.py`
- `api2agent/generators/tools.py`
- `api2agent/diagnostics.py`
- `api2agent/cli.py`

Tests and fixtures：

- `tests/fixtures/openapi/schema_shaping.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

## Contract

本实现没有增加 required IR fields。

现有 raw schema fields 仍然是 compatibility source of truth：

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

Direction-aware shaping 在 generation time 派生：

```text
request body input schema -> omit readOnly fields, keep writeOnly fields
response output schema -> diagnose writeOnly fields
neutral docs schema -> preserve markers and summarize compactly
```

旧 generated `capability.json` files 仍然 valid。

## Generated Artifact Effects

README 和 inspect 现在使用 compact shaped schema summaries。示例输出：

```text
body: object {name:string, nickname:string nullable?, password:string writeOnly, labels:object map[string]?, tags:array[object {key:string, value:string?}]?, loose:array[unknown]?, choice:oneOf[string | object {nested:anyOf[string | integer]?}]?} required
```

`api2agent inspect` 现在显示 schema hint counts：

```text
Schema hints: arrays_without_items=1, maps=2, nested_polymorphic=2, nullable=3, polymorphic=2, read_only=2, write_only=2
```

Generated OpenAI tools schemas 对 request bodies 使用 request-direction shaping，所以 `readOnly` fields 不会作为 Agent inputs 被要求提供。

Generated manual write examples 使用 shaped request body schemas：

```text
{'body': {'name': 'example', 'password': 'example'}}
```

## Diagnostics

新增 diagnostics：

- `nullable_fields_present`
- `read_only_request_fields`
- `write_only_response_fields`
- `additional_properties_present`
- `nested_polymorphic_schema`
- `array_without_item_schema`
- `large_object_schema`

除 `array_without_item_schema` 是 warning 外，其余 finding 是 advisory；缺少 array item schema 时 generated examples 无法安全推断 element shape。

## Dogfood Evidence

已生成 package：

```text
python -m api2agent.cli generate tests\fixtures\openapi\schema_shaping.yaml --output tmp\openapi-schema-shaping --force
```

观察到：

```text
Generated capability package: tmp\openapi-schema-shaping
Diagnostics: warn score=50 errors=0 warnings=4 info=10
```

`inspect` 显示：

```text
Schema hints: arrays_without_items=1, maps=2, nested_polymorphic=2, nullable=3, polymorphic=2, read_only=2, write_only=2
body: object {name:string, nickname:string nullable?, password:string writeOnly, labels:object map[string]?, tags:array[object {key:string, value:string?}]?, loose:array[unknown]?, choice:oneOf[string | object {nested:anyOf[string | integer]?}]?} required
```

`diagnose` 显示新增 schema findings：

```text
read_only_request_fields
nullable_fields_present
additional_properties_present
nested_polymorphic_schema
array_without_item_schema
write_only_response_fields
```

Generated manual write example 排除了 `readOnly` `id` field，并保留 `writeOnly` `password` field：

```text
{'body': {'name': 'example', 'password': 'example'}}
```

## Compatibility

Compatibility 已保留：

- parser still preserves raw source schema metadata
- existing `allOf` merge and `oneOf` / `anyOf` preservation remain compatible
- existing `capability.json` schema fields remain unchanged
- old capability JSON without shaped metadata remains valid
- generated examples still prefer explicit examples/defaults/enums before type fallbacks
- generated runner behavior is unchanged

## Validation

已通过：

```text
python -m py_compile api2agent\schema_shaping.py api2agent\generators\examples.py api2agent\generators\readme.py api2agent\generators\tools.py api2agent\diagnostics.py api2agent\cli.py
```

已通过：

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

结果：

```text
75 passed
```

已通过：

```text
pytest
```

结果：

```text
193 passed
```

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Schema Shaping Closeout + Phase Review v0
```

Closeout 应判断这个 schema shaping slice 是否可以关闭，并决定下一项 OpenAPI hardening target 是 response shaping depth、discriminator handling，还是另一个 real-spec friction point。
