# Agent Capability Compiler OpenAPI Schema Shaping Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Schema Shaping implementation slice 可以关闭。

Compiler 现在保留 raw schema compatibility，同时让 Agent-facing request bodies、examples、README/inspect summaries、OpenAI tool schemas 和 diagnostics 对常见真实 OpenAPI schema shapes 更清楚。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Discriminator Handling Design v0
```

下一项设计应聚焦 discriminator-aware `oneOf` / `anyOf` readability、examples、diagnostics 和 generated documentation，但不把 compiler 变成完整 JSON Schema validator。

## 现在已完成

### Design

已完成：

- documented current schema handling baseline and gaps
- defined additive compatibility strategy without requiring broad IR churn
- defined direction-aware request/response shaping rules
- defined nullable、readOnly/writeOnly、additionalProperties、array、polymorphism 和 required/optional policies
- defined generated README、tools schema、examples、inspect、diagnostics、tests 和 dogfood effects
- preserved API-first non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_DESIGN.md`

### Implementation

已完成：

- shared schema shaping helpers in `api2agent/schema_shaping.py`
- OpenAPI 3.0 and 3.1 nullable display
- request-direction body shaping that omits `readOnly` fields
- request-direction preservation and display of `writeOnly` fields
- generated examples from shaped request body schemas
- OpenAI tool schema filtering for request bodies
- `additionalProperties` map summaries
- array item summaries and missing `items` 时显示 `array[unknown]`
- bounded `oneOf` / `anyOf` summaries
- required versus optional field display
- inspect schema hint counts
- diagnostics for nullable、readOnly request fields、writeOnly response fields、maps、nested polymorphism、arrays without items 和 large objects
- schema-shaping fixture and regression tests
- local dogfood for generate、README、inspect、diagnose 和 manual write examples

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| raw normalized schema compatibility is preserved | passed |
| request body examples omit read-only fields | passed |
| request body examples preserve write-only fields | passed |
| generated OpenAI tools schema uses request-direction body shaping | passed |
| nullable fields are visible in README and inspect summaries | passed |
| OpenAPI 3.1 nullable type arrays are summarized | passed |
| map semantics from `additionalProperties` are visible | passed |
| arrays show item summaries when known | passed |
| arrays without `items` are shown as `array[unknown]` and diagnosed | passed |
| bounded `oneOf` / `anyOf` summaries are visible | passed |
| required versus optional object fields are visible | passed |
| diagnostics flag schema shapes likely to confuse Agents | passed |
| inspect shows compact schema hint counts | passed |
| old capability JSON without shaped metadata remains valid | passed |
| 未增加 full JSON Schema validator、OpenAPI 3.1 dialect engine、LLM schema simplification、runtime schema coercion、UI form rendering、workflow、marketplace、vault、billing、hosted public CRUD、gateway permission source 或 automatic propagation | passed |

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

Local dogfood 已通过：

- `tests\fixtures\openapi\schema_shaping.yaml`
- generated README body summary
- `api2agent inspect` schema hints
- `api2agent diagnose` schema findings
- generated manual write example 排除 read-only `id`，并保留 write-only `password`

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Compiler 现在处理了最常见的 Agent-facing schema clarity issues，同时没有破坏 raw schema compatibility，也没有扩展成 full schema engine。Request bodies 对 Agent use 更安全，因为明显的 server-owned fields 默认不再要求提供；generated summaries 会显示 nullable、map、array、polymorphic 和 optional shapes。

这关闭了 OpenAPI real-world hardening 中识别出的 schema shaping gap。

## Remaining Risks

### Discriminators Are Preserved But Not Used

`oneOf` / `anyOf` branches 现在会 compact summary，但 discriminator metadata 还没有用于解释 branch selection 或生成更好的 examples。

### Response Shaping Is Mostly Diagnostic

实现会诊断 write-only response fields，但 generated documentation 仍主要聚焦 tool inputs，而不是 rich response shape documentation。

### JSON Schema Coverage Is Intentional But Partial

本实现处理 practical OpenAPI shapes，而不是每一个 JSON Schema keyword 或 OpenAPI 3.1 dialect detail。

### Diagnostics Are Advisory

Schema diagnostics 能帮助发现 likely Agent confusion，但除已有 package quality score semantics 外，不会阻止 generation。

### Large Schemas Are Bounded, Not Semantically Simplified

Large objects 和 nested polymorphism 会 bounded summary。更深的 semantic simplification 需要 explicit product design。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Discriminator Handling Design v0
```

该设计应定义如何 preserve、display、diagnose discriminator metadata，并将其用于 examples，同时保持 offline deterministic generation 和 existing package schema compatibility。
