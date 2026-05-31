# Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent capability compiler 已实现 bounded OpenAPI JSON Schema keyword coverage。

Generated packages 现在会在 README 和 `api2agent inspect` 中显示常见 schema constraints，使用 deterministic keyword hints 生成 examples，在 OpenAI tool schemas 中保留 raw keyword metadata，并诊断仍然只作为 metadata 保留的 advanced keywords。

本实现支持：

- `format`、`pattern`、length bounds、numeric bounds、array bounds、`uniqueItems`、`const` 和 `deprecated` 的 compact summary markers
- `const`、常见 string formats、simple numeric bounds、string `minLength` 和 bounded `minItems` 的 deterministic examples
- inspect schema hint counts for keyword categories
- diagnostics for visible keywords、string/numeric/array constraints、const values、deprecated fields、patterns、unsupported keywords、conditional keywords 和 dependent schemas
- required deprecated request inputs、request-body conditional/dependent schemas 的 warning severity
- 通过现有 schema dictionaries 和 request-direction OpenAI tool shaping 保留 raw keyword metadata
- local keyword fixture 和 regression coverage

本 slice 未增加 full JSON Schema validation、OpenAPI 3.1 dialect engine、runtime request/response validation、runtime coercion、LLM schema simplification、generated SDK type system、UI form rendering、workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## Files

Implementation：

- `api2agent/schema_shaping.py`
- `api2agent/generators/examples.py`
- `api2agent/diagnostics.py`

Tests and fixtures：

- `tests/fixtures/openapi/schema_keywords.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

Design reference：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_DESIGN.md`

## Generated Artifact Effects

README 和 inspect schema summaries 现在会显示 high-signal keyword facts：

```text
path: user_id string format=uuid required
query: email string format=email maxLength=254, legacy string deprecated
body: object {email:string format=email minLength=6 maxLength=254, website:string format=uri?, age:integer min=0 max=150, rating:number exclusiveMin=0 exclusiveMax=5?, tags:array[string minLength=3] minItems=2 maxItems=3 uniqueItems, status:string const=active, legacy_code:string deprecated, activation_date:string format=date?, ...} required
```

Generated manual write examples 现在会在没有 explicit example/default/enum 时使用 keyword hints：

```text
{'body': {'email': 'user@example.com', 'age': 1, 'tags': ['example', 'example'], 'status': 'active', 'legacy_code': 'example'}}
```

OpenAI tool schemas 在 request shaping 后仍保留 raw schema metadata，包括 `format`、`minItems`、`const`、`dependentRequired` 和 conditional `if`/`then` structures。

## Diagnostics

新增 diagnostics：

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

这些 findings 是 deterministic 和 advisory。Advanced Tier 2 keywords 会被 preserve and diagnose，而不是被半实现成 validation logic。

## Dogfood Evidence

已生成 package：

```text
python -m api2agent.cli generate tests\fixtures\openapi\schema_keywords.yaml --output tmp\openapi-schema-keywords --force
```

观察到：

```text
Generated capability package: tmp\openapi-schema-keywords
Diagnostics: warn score=50 errors=0 warnings=4 info=27
```

`inspect` 显示：

```text
Schema hints: array_constraints=2, conditional_schema=1, const_schema=2, dependent_schema=1, deprecated_schema_fields=2, numeric_constraints=3, pattern_schema=2, schema_keywords=23, string_constraints=11, unsupported_schema_keywords=3
```

`diagnose` 显示新增 keyword findings，并对 required deprecated request fields、conditional request-body schemas 和 dependent request-body schemas 给出 warning severity。

## Compatibility

Compatibility 已保留：

- 没有新增 keyword-specific IR fields，old capability JSON 仍然 valid
- raw schemas remain the source of truth
- generated runner behavior is unchanged
- request/response direction shaping 继续控制 readOnly/writeOnly visibility
- discriminator、response documentation、examples/defaults、security requirements、server metadata 和 OpenAI tool schemas remain compatible

## Validation

已通过：

```text
python -m py_compile api2agent\schema_shaping.py api2agent\generators\examples.py api2agent\diagnostics.py
```

已通过：

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

结果：

```text
87 passed
```

已通过：

```text
pytest
```

结果：

```text
205 passed
```

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Closeout + Phase Review v0
```

Closeout 应判断 v0 keyword coverage slice 是否足够 close，并决定下一项 compiler hardening target 是 real-spec calibration、diagnostics precision，还是另一个 high-friction OpenAPI gap。
