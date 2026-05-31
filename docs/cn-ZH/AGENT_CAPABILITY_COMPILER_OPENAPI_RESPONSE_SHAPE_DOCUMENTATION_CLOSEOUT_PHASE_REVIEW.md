# Agent Capability Compiler OpenAPI Response Shape Documentation Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Response Shape Documentation implementation slice 可以关闭。

Compiler 现在会在 generated packages 中显示 response status codes、categories、content types、schemas、examples、structured error bodies、default responses 和 response documentation caveats，同时不改变 runtime runner behavior。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Design v0
```

下一项设计应聚焦 practical、high-signal JSON Schema/OpenAPI schema keywords，用来改善 Agent-facing docs 和 examples，同时保持 deterministic、offline 和 compatibility-preserving。

## 现在已完成

### Design

已完成：

- documented response documentation baseline and gaps
- defined additive response metadata strategy
- defined deterministic response content selection rules
- defined response status category and summary formatting rules
- defined README、inspect、diagnostics、parser、runner、tests 和 dogfood effects
- preserved API-first non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_DESIGN.md`

### Implementation

已完成：

- `ResponseShape` 中的 optional response metadata
- deterministic OpenAPI response content selection
- selected content type 和 content type variant preservation
- response `example` 和 `examples` extraction
- shared response summary formatting helpers
- generated README 每个 tool 下的 response sections
- `api2agent inspect` response category counts 和 per-tool response summaries
- diagnostics for response schemas、examples、missing schemas、missing success schemas、structured error bodies、default responses、multiple content types 和 polymorphic response schemas
- response-direction summaries，避免把 `writeOnly` fields 显示成 returned values
- response-shape fixture 和 parser/generator/diagnostics/CLI regression tests
- local dogfood for generate、README、inspect 和 diagnose

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| old capability JSON without response metadata remains valid | passed |
| raw response schemas remain the source of truth | passed |
| selected response content type is preserved | passed |
| offered response content types are preserved | passed |
| response examples and examples maps are preserved | passed |
| README shows response status codes and categories | passed |
| README shows compact response schema summaries | passed |
| README shows no-body and default responses clearly | passed |
| README avoids showing `writeOnly` response fields as returned values in schema summaries | passed |
| inspect shows response category counts | passed |
| inspect shows per-tool response summaries | passed |
| diagnostics report response schema presence and examples | passed |
| diagnostics report missing response schemas and missing success schemas | passed |
| diagnostics report structured error bodies、default responses、multiple content types 和 polymorphic responses | passed |
| generated runner behavior is unchanged | passed |
| parser/generator/diagnostics/CLI regression tests are added | passed |
| 未增加 runtime response validation、runtime response coercion、LLM response transformation、generated SDK response types、UI response viewer、workflow runtime、marketplace、vault、billing、hosted public CRUD、gateway permission source 或 automatic propagation | passed |

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

Local dogfood 已通过：

- `tests\fixtures\openapi\response_shapes.yaml`
- generated README response summaries
- `api2agent inspect` response category counts 和 per-tool response summaries
- `api2agent diagnose` response documentation findings

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Generated packages 现在给 Agents 足够的 response-shape context，让它们在执行前理解 common success、no-body、error 和 default outcomes。这个实现关闭了 request schema shaping 和 discriminator handling 之后剩下的 response documentation asymmetry。

这保持 documentation-first：不验证 provider responses，不 coerce outputs，也不创建 SDK response types。

## Remaining Risks

### Content Negotiation Is Not Runtime Behavior

Compiler 会保留 offered content types，并 deterministic 选择一个用于 documentation。它不做 runtime content negotiation，也不合并 multiple response media types。

### Examples Are Preserved, Not Validated

Source response examples 会在存在时显示，但不会 against schemas 做 validation，也不会超出现有 source-trust boundaries 做 scrub。

### Diagnostics Are Advisory

Response documentation diagnostics 用于识别 missing 或 ambiguous docs。除 existing package quality score semantics 外，它们不会阻止 generation。

### Runtime Output Validation Is Still Out Of Scope

Generated runners 继续返回 raw `ok`、`status_code`、`body` 和 `error` values。它们不 validate、coerce 或 normalize response bodies。

### JSON Schema Keyword Coverage Remains Partial

Compiler 现在能显示很多 practical schema shapes，但 `format`、`pattern`、`minLength`、`maxLength`、`minimum`、`maximum`、`minItems`、`maxItems`、`uniqueItems`、`deprecated`、`const`、`dependentRequired` 和 conditional schemas 等 keywords 仍需要明确产品设计后再实现。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Design v0
```

该设计应选择 bounded set of high-value schema keywords，用于 Agent-facing summaries、examples、diagnostics 和 compatibility tests，同时避免把 compiler 变成 full JSON Schema validator。
