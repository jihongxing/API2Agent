# Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage implementation slice 可以关闭。

Compiler 现在会在 generated packages 中显示常见 JSON Schema/OpenAPI keyword constraints，为 common formats 和 bounded values 生成更好的 deterministic examples，为 downstream tool consumers 保留 raw keyword metadata，并诊断仍然只作为 metadata 保留的 advanced keywords。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Real-Spec Calibration Design v0
```

下一项设计应使用真实 OpenAPI specs 来校准 compiler 的 keyword coverage、diagnostics precision、summary readability 和 generated example quality，再决定是否增加下一项大型 semantic feature。

## 现在已完成

### Design

已完成：

- documented keyword coverage baseline and gaps
- defined Tier 1 display/example keywords
- defined Tier 2 diagnostics-only keywords
- defined compatibility strategy around raw schema dictionaries
- defined README、inspect、OpenAI tool schema、diagnostics、tests 和 dogfood effects
- preserved API-first non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_DESIGN.md`

### Implementation

已完成：

- `format`、`pattern`、`minLength`、`maxLength`、numeric bounds、array bounds、`uniqueItems`、`const` 和 `deprecated` 的 compact schema summary markers
- `const`、common string formats、simple numeric bounds、bounded `minLength` 和 bounded `minItems` 的 deterministic keyword-hint examples
- visible 和 advanced keyword categories 的 schema hint counts
- diagnostics for schema keywords、string/numeric/array constraints、const values、deprecated fields、patterns、unsupported keywords、conditional schemas 和 dependent schemas
- required deprecated request inputs 和 request-body conditional/dependent schemas 的 warning severity
- 通过现有 request-direction shaping 保留 OpenAI tool schema metadata
- parser/generator/diagnostics/CLI regression tests
- generate、inspect、diagnose 和 manual write examples 的 local dogfood

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| parser preserves raw keyword metadata | passed |
| README summaries show common keyword markers | passed |
| inspect summaries show common keyword markers | passed |
| inspect reports schema hint counts for keyword categories | passed |
| generated examples prefer explicit examples/defaults/enums before keyword hints | passed |
| generated examples use `const` and common format hints when no explicit sample exists | passed |
| generated examples use simple numeric bounds and bounded `minItems` hints | passed |
| generated OpenAI tool schemas preserve raw keyword metadata after request shaping | passed |
| diagnostics report Tier 1 keyword presence | passed |
| diagnostics report Tier 2 unsupported、conditional 和 dependent keywords | passed |
| required deprecated request inputs produce warning severity | passed |
| request-body conditional/dependent schemas produce warning severity | passed |
| existing schema shaping、discriminator handling、response docs、auth/server metadata 和 runner behavior remain compatible | passed |
| 未增加 full JSON Schema validation、OpenAPI 3.1 dialect engine、runtime validation/coercion、UI form rendering、workflow runtime、marketplace、vault、billing、hosted CRUD、gateway permission source 或 automatic propagation | passed |

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

Local dogfood 已通过：

- `tests\fixtures\openapi\schema_keywords.yaml`
- generated README keyword summaries
- `api2agent inspect` keyword summaries 和 schema hint counts
- `api2agent diagnose` keyword findings
- generated manual write examples with keyword hints

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Compiler 现在具备足够 bounded keyword awareness，可以服务 practical Agent-facing OpenAPI packages。它不假装自己是 JSON Schema validator，但也不再隐藏 email/uuid formats、length bounds、numeric bounds、array cardinality、const values、deprecated fields 或 conditional/dependent schema caveats 等重要 constraints。

这是 v0 keyword coverage 的合适停止点。下一步最高杠杆动作是 against real specs 做 calibration，而不是继续抽象扩展 keyword list。

## Remaining Risks

### Keyword Coverage Is Bounded

Compiler 会显示常见 keywords 并诊断 advanced ones。它不实现 `if`/`then`/`else`、`dependentSchemas`、`patternProperties`、`contains`、`unevaluatedProperties` 或 dialect-specific behavior 的完整 JSON Schema semantics。

### Examples Are Heuristic

Keyword-hint examples 是 deterministic 且有用的，但不是 validation proofs。Regex patterns 会被显示和诊断，不会被 synthesized。

### Summary Readability Needs Real-Spec Calibration

当前 summary format 很 compact，但真实 specs 可能暴露 marker density 过高或 truncation rules 需要调整的情况。

### Diagnostics Are Advisory

Diagnostics 会指出 constraints 和 unsupported semantics，但除 existing package quality score semantics 外不会阻止 generation。

### OpenAPI 3.1 Dialect Nuance Remains Out Of Scope

实现会保留 unknown keyword metadata，但不会选择或执行 JSON Schema dialects。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Real-Spec Calibration Design v0
```

该设计应选择一小组真实 OpenAPI specs，并定义 repeatable calibration loop，用来校准 generated summaries、examples、diagnostics、package size 和 first-call ergonomics。
