# Agent Capability Compiler OpenAPI Response Shape Documentation Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent capability compiler 已实现 OpenAPI response shape documentation。

Generated packages 现在会保留 response content metadata，并在 README、inspect、diagnostics 和 generated `capability.json` 中显示 response status codes、categories、schemas、examples 和 error/default outcomes。

本实现支持：

- `ResponseShape` 中的 additive response metadata
- deterministic response content selection
- response content type 和 content type variants preservation
- response examples 和 examples maps
- compact response summary formatting
- 每个 tool 下的 README response sections
- `api2agent inspect` response summaries 和 response category counts
- diagnostics for documented schemas、examples、missing schemas、missing success schemas、structured error bodies、default responses、multiple content types 和 polymorphic response schemas
- response-direction schema summaries，避免把 `writeOnly` fields 显示为 returned values
- local response-shape fixture 和 regression coverage

本 slice 未增加 runtime response validation、runtime response coercion、LLM response transformation、generated SDK response types、UI response viewer、workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## Files

Implementation：

- `api2agent/ir/models.py`
- `api2agent/parsers/openapi.py`
- `api2agent/response_docs.py`
- `api2agent/generators/readme.py`
- `api2agent/diagnostics.py`
- `api2agent/cli.py`

Tests and fixtures：

- `tests/fixtures/openapi/response_shapes.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

Design reference：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_DESIGN.md`

## Contract

现有 response schema compatibility 已保留：

```text
Response.schema_
```

本实现增加 optional fields：

```text
ResponseShape.content_type
ResponseShape.content_types
ResponseShape.example
ResponseShape.examples
```

只包含 `status_code`、`description` 和 `schema` 的旧 generated `capability.json` files 仍然 valid。

Generated runner behavior 不变。Runners 继续返回 raw execution results：

```text
ok
status_code
body
error
```

## Response Extraction

OpenAPI response extraction 现在会：

- preserve response status codes as strings，包括 `default`
- preserve descriptions
- 有 `application/json` 时优先选择它
- 否则 deterministic 选择第一个 content entry
- preserve selected `content_type`
- preserve all offered `content_types`
- extract selected content schema
- preserve selected content `example` 和 `examples`
- 不合并 content types
- 不验证 examples against schemas

## Generated Artifact Effects

README 现在会在 tools 下包含 response summaries：

```text
  - responses:
    - 200 success application/json object {id:string readOnly, name:string} example={"id": "item_123", "name": "Demo"} - OK
    - 204 success no documented body - No Content
    - 400 client_error application/json object {error:string, code:string?} example={"code": "invalid", "error": "invalid_request"} - Bad request
    - default default application/json object {error:string, code:string?} - Default error
```

`api2agent inspect` 现在显示 response category counts：

```text
Response categories: client_error=2, default=1, success=4
```

Per-tool inspect output 现在包含 response summaries：

```text
responses: 200 success application/json object {id:string readOnly, name:string}; 204 success no documented body; 400 client_error application/json object {error:string, code:string?}; default default application/json object {error:string, code:string?}
```

Response-direction summaries 会复用 schema shaping 和 discriminator handling。例如，`writeOnly` response fields 不会显示成 returned values，polymorphic response summaries 可以显示 discriminator mappings：

```text
200 success application/json oneOf[discriminator=kind: hit=>SearchHit | empty=>SearchEmpty]
```

## Diagnostics

新增 diagnostics：

- `response_schema_present`
- `response_example_present`
- `response_without_schema`
- `success_response_without_schema`
- `error_response_schema_present`
- `default_response_present`
- `multiple_response_content_types`
- `response_polymorphic_schema`

这些 findings 是 deterministic 和 advisory。它们不做 runtime response validation，也不会在 existing package quality score semantics 之外阻止 generation。

## Dogfood Evidence

已生成 package：

```text
python -m api2agent.cli generate tests\fixtures\openapi\response_shapes.yaml --output tmp\openapi-response-shapes --force
```

观察到：

```text
Generated capability package: tmp\openapi-response-shapes
Diagnostics: warn score=70 errors=0 warnings=2 info=20
```

`inspect` 显示：

```text
Response categories: client_error=2, default=1, success=4
responses: 200 success application/json object {id:string readOnly, name:string}; 204 success no documented body; 400 client_error application/json object {error:string, code:string?}; default default application/json object {error:string, code:string?}
```

`diagnose` 显示新增 response documentation findings：

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

Compatibility 已保留：

- old capability JSON without response metadata remains valid
- raw response schemas remain the source of truth
- generated runner behavior is unchanged
- response docs use response-direction schema shaping
- request-body shaping、discriminator handling、examples/defaults、security requirements、server metadata 和 OpenAI tool schemas remain compatible

## Validation

已通过：

```text
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\response_docs.py api2agent\generators\readme.py api2agent\diagnostics.py api2agent\cli.py
```

已通过：

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

结果：

```text
83 passed
```

已通过：

```text
pytest
```

结果：

```text
201 passed
```

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Response Shape Documentation Closeout + Phase Review v0
```

Closeout 应判断这个 response documentation slice 是否可以关闭，并决定下一项 OpenAPI hardening target 是 deeper JSON Schema keyword coverage、response examples calibration against more real specs，还是另一个 high-friction real-spec gap。
