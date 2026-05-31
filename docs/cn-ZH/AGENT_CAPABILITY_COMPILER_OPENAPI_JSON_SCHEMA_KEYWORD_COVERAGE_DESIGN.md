# Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 OpenAPI hardening implementation slice 应该是：

```text
Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Implementation v0
```

这个 slice 应给 Agent-facing summaries、examples、inspect output 和 diagnostics 增加 bounded、high-signal JSON Schema/OpenAPI keyword awareness，同时保持 raw schema compatibility 和 deterministic offline generation。

它不得变成 full JSON Schema validator、OpenAPI 3.1 dialect engine、runtime schema validator/coercer、generated SDK type system、UI form renderer、workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## 为什么现在做这个 Slice

Compiler 现在已经具备主要 OpenAPI hardening surfaces：

- examples/defaults propagation
- security requirement combinations
- server metadata handling
- request/response schema shaping
- discriminator-aware polymorphic summaries and examples
- response shape documentation
- inspect and diagnostics visibility

剩下的 high-friction schema gap 是 keyword-level constraint visibility。真实 OpenAPI specs 经常把重要 Agent instructions 编进 schema keywords：

- `format: email`、`uri`、`uuid`、`date`、`date-time`
- `pattern`
- `minLength`、`maxLength`
- `minimum`、`maximum`、`exclusiveMinimum`、`exclusiveMaximum`
- `minItems`、`maxItems`、`uniqueItems`
- `const`
- `deprecated`
- `dependentRequired`、`if` / `then` / `else`、`not`、`patternProperties`

目前很多 keyword 会保留在 raw schemas 中，但不会出现在 generated summaries、examples 或 diagnostics 里。Agents 可能错过能避免 first-call failure 的 constraints。

## 当前 Baseline

已有：

- parser preserves unknown schema keys in normalized dictionaries
- `enum`、`default` 和 `example` 会影响 generated examples
- `const` 只间接用于 discriminator branch tag selection
- nullable、readOnly/writeOnly、map、array、object、required/optional、`oneOf` / `anyOf`、discriminator 和 response summaries 已可见
- diagnostics 会报告 broad schema shape issues 和 discriminator/response documentation issues
- generated OpenAI tool schemas preserve raw shaped schema dictionaries

重要缺口：

- `format` 不显示，也不用于 examples
- string length 和 regex constraints 不可见
- numeric bounds 不可见
- array cardinality 和 uniqueness 不可见
- `const` 没有作为 field constraint summary 显示
- `deprecated` fields 没有标记
- conditional/dependent schemas 没有 diagnostics
- unsupported high-complexity keywords 没有被指出
- Agent-facing summaries 无法区分 generic string 与 email/uuid/date string

## Goals

- 在 README 和 inspect summaries 中显示 common schema constraints
- 为 common formats 改善 deterministic examples，但不做 validation
- 保持 raw schema compatibility
- 保持 generated OpenAI tool schemas compatible with existing shaping
- 诊断 unsupported 或 complex JSON Schema keywords that may confuse Agents
- 有 simple keyword facts 时，避免生成明显无效的 examples
- 保持 summaries bounded and readable
- 保持 deterministic offline generation

## Non-Goals

不实现：

- full JSON Schema validation
- complete OpenAPI 3.1 dialect support
- runtime request or response validation
- runtime coercion
- LLM-based schema simplification
- generated SDK types or tagged unions
- UI form rendering
- content negotiation
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Keyword Tiers

### Tier 1：Display And Simple Example Hints

为以下 keywords 实现 readable summaries 和 deterministic example hints：

- `format`
- `pattern`
- `minLength`
- `maxLength`
- `minimum`
- `maximum`
- `exclusiveMinimum`
- `exclusiveMaximum`
- `minItems`
- `maxItems`
- `uniqueItems`
- `const`
- `deprecated`

这些 keyword 常见、compact，并且直接有助于 Agent prompting。

### Tier 2：v0 只做 Diagnostics

保留并诊断，但 v0 不尝试 semantic display 或 example generation：

- `multipleOf`
- `minProperties`
- `maxProperties`
- `patternProperties`
- `propertyNames`
- `dependentRequired`
- `dependentSchemas`
- `if`
- `then`
- `else`
- `not`
- `contains`
- `minContains`
- `maxContains`
- `unevaluatedProperties`
- `unevaluatedItems`

这些 keyword 会深度影响 validation，不应半实现成 compiler 是 validator 的样子。

## Compatibility Strategy

保留现有 raw schema fields 作为 source of truth：

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

不增加 required IR fields。优先使用 helper functions 从 raw schema dictionaries 派生 keyword facts：

```text
schema_keyword_markers(schema) -> list[str]
schema_keyword_hint_counts(schema) -> dict[str, int]
schema_paths_with_keyword(schema, keyword) -> list[str]
```

Generated `capability.json` 保持 backward compatible，因为现有 schema dictionaries 保持不变。

## Summary Formatting Rules

保持 compact summaries readable：

```text
email:string format=email maxLength=254
id:string format=uuid
age:integer min=0 max=150
code:string pattern=^[A-Z]{3}-\d{4}$
tags:array[string] minItems=1 maxItems=5 uniqueItems
status:string const=active
old_field:string deprecated?
```

规则：

- 使用 `min`、`max`、`minLength`、`maxLength` 等 short aliases
- `exclusiveMinimum` / `exclusiveMaximum` 显示为 `exclusiveMin` / `exclusiveMax`
- truncate long `pattern` values
- `deprecated` 显示为 marker
- 输出过长时不要显示每个 keyword
- 保留现有 nullable/readOnly/writeOnly/required/optional markers
- 保留现有 `oneOf` / `anyOf` / discriminator summaries

## Example Generation Rules

仅当没有 explicit example、examples map、default、enum 或 const 时，才使用 keyword hints。

建议 deterministic examples：

| Keyword | Example behavior |
| --- | --- |
| `const` | use const value |
| `format: email` | `user@example.com` |
| `format: uri` / `url` | `https://example.com` |
| `format: uuid` | `00000000-0000-4000-8000-000000000000` |
| `format: date` | `2026-01-01` |
| `format: date-time` | `2026-01-01T00:00:00Z` |
| `format: hostname` | `example.com` |
| numeric `minimum` / `maximum` | choose a simple in-range value when possible |
| `minLength` | pad the generic string to the minimum length when small |
| `minItems` | emit up to a small bounded number of item examples |

v0 不从 arbitrary `pattern` values 合成 regex-matching strings。Patterns 应 display and diagnose，不解释。

## README And Inspect Effects

README 和 `api2agent inspect` 应：

- show common string formats
- show bounded string and numeric constraints
- show array min/max/unique constraints
- show const values
- mark deprecated fields or parameters
- keep object summaries bounded
- keep response/request direction shaping intact
- keep discriminator and response summaries intact

## OpenAI Tool Schema Effects

Generated OpenAI tool schemas 应：

- preserve raw keyword metadata after request-direction shaping
- keep `readOnly` request filtering and `writeOnly` request preservation
- keep discriminator metadata
- avoid flattening or rewriting keyword constraints into descriptions
- avoid dropping constraints that downstream tool consumers may understand

## Diagnostics

新增 deterministic findings：

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

Severity guidance：

- visible Tier 1 keywords 为 informational
- `deprecated` fields 为 informational，除非它们是 required request inputs
- required deprecated request inputs 为 warning
- Tier 2 unsupported keywords 为 informational
- request bodies 中的 conditional/dependent schemas 为 warning，因为 examples 可能无法表达完整 validity semantics

Diagnostics 保持 advisory，除 existing package quality score semantics 外不阻止 generation。

## Implementation Plan

1. 在 `api2agent/schema_shaping.py` 或小型 sibling helper module 中增加 keyword detection helpers。
2. 用 bounded Tier 1 keyword markers 扩展 compact schema summaries。
3. 用 deterministic format/const/simple-bound hints 扩展 example generation。
4. 通过现有 shaped schema paths 保持 OpenAI tool schema compatibility。
5. 增加 keyword categories 的 schema hint counts。
6. 增加 diagnostics for Tier 1/Tier 2 keyword presence 和 risky combinations。
7. 增加覆盖 string、numeric、array、const、deprecated、conditional/dependent schemas 的 OpenAPI fixture。
8. 增加 parser、generator、diagnostics 和 CLI regression tests。
9. 本地 dogfood generated README、inspect、diagnose 和 manual examples。

## Tests

新增 fixtures 覆盖：

- `format: email`、`uri`、`uuid`、`date`、`date-time`
- `pattern`
- `minLength` and `maxLength`
- numeric minimum/maximum and exclusive bounds
- array minItems/maxItems/uniqueItems
- `const`
- deprecated fields and parameters
- required deprecated request field
- conditional schemas (`if` / `then` / `else`)
- dependent schemas or dependent required
- patternProperties

Regression tests 应覆盖：

- parser preserves raw keyword metadata
- README summaries show keyword markers
- generated examples use const and common format examples
- generated examples prefer explicit examples/defaults/enums over keyword hints
- inspect shows keyword hint counts and summaries
- diagnostics report Tier 1 and Tier 2 keyword findings
- OpenAI tool schemas preserve keyword metadata after request shaping
- old capability JSON without keyword-specific metadata remains valid

## Dogfood

本地 dogfood：

- new JSON Schema keyword fixture
- generated README review
- `api2agent inspect`
- `api2agent diagnose`
- generated manual write examples

不需要网络依赖。

## Success Metrics

实现成功的标准：

- common schema constraints are visible in generated docs
- common format examples are more realistic
- complex unsupported keyword semantics are diagnosed rather than silently ignored
- generated tool schemas preserve source keyword metadata
- existing schema shaping、discriminator 和 response documentation behavior remains compatible
- full Python test suite passes

## Acceptance Criteria For This Design

- current keyword coverage baseline and gaps are documented
- Tier 1 and Tier 2 keyword scopes are defined
- compatibility strategy is defined
- summary formatting rules are defined
- example generation rules are defined
- README、inspect、OpenAI tool schema 和 diagnostics effects are defined
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
