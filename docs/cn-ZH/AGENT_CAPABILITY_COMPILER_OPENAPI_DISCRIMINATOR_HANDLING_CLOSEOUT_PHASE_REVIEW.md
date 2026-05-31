# Agent Capability Compiler OpenAPI Discriminator Handling Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Discriminator Handling implementation slice 可以关闭。

Compiler 现在保留 raw discriminator metadata，同时让 discriminator-aware `oneOf` / `anyOf` schemas 在 generated README summaries、inspect output、OpenAI tool schemas、request examples 和 diagnostics 中更清楚。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Response Shape Documentation Design v0
```

下一项设计应聚焦为 Agent 生成更丰富的 response documentation，但不把 compiler 扩展成 full JSON Schema validator、SDK type generator、UI form system 或 runtime response validator。

## 现在已完成

### Design

已完成：

- documented current discriminator handling baseline and gaps
- defined compatibility strategy using raw OpenAPI schema dictionaries as the source of truth
- defined discriminator extraction from `propertyName`、`mapping`、`oneOf` 和 `anyOf`
- defined bounded summary formatting for discriminator-aware polymorphic schemas
- defined deterministic request example behavior using discriminator mapping keys
- defined README、inspect、OpenAI tools schema、diagnostics、tests 和 dogfood effects
- preserved API-first non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_DESIGN.md`

### Implementation

已完成：

- `api2agent/schema_shaping.py` 中的 discriminator extraction helpers
- discriminator-aware `oneOf` / `anyOf` summaries
- bounded polymorphic summaries 中的 mapping key display
- discriminator-aware generated request body example fallback selection
- generated request examples 中插入 discriminator property
- polymorphic branches 内的 request-direction readOnly filtering
- generated request body examples 和 OpenAI tool schemas 中保留 writeOnly
- inspect schema hint counts for discriminators and discriminator mappings
- diagnostics for discriminator presence、mappings、missing `propertyName`、discriminator without polymorphism、unresolved mappings 和 untagged branches
- discriminator fixture 和 parser/generator/diagnostics/CLI regression tests
- local dogfood for generate、inspect、diagnose、generated README summaries、OpenAI tool schema preservation 和 manual write examples

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| raw discriminator metadata is preserved | passed |
| discriminator property is shown in schema summaries | passed |
| mapping keys are shown in bounded summaries | passed |
| generated examples include discriminator values | passed |
| request-direction shaping is preserved inside polymorphic branches | passed |
| OpenAI tool schemas preserve discriminator metadata | passed |
| inspect shows discriminator hint counts | passed |
| diagnostics report discriminator presence and mappings | passed |
| diagnostics report missing discriminator `propertyName` | passed |
| diagnostics report discriminator without polymorphism | passed |
| diagnostics report unresolved mappings | passed |
| diagnostics report branches without matching discriminator tags | passed |
| parser/generator/diagnostics/CLI regression tests are added | passed |
| old capability JSON without discriminator metadata remains valid | passed |
| 未增加 full JSON Schema validator、runtime validation、LLM branch selection、SDK type system、UI forms、workflow runtime、marketplace、vault、billing、hosted public CRUD、gateway permission source 或 automatic propagation | passed |

## Validation

已通过：

```text
python -m py_compile api2agent\schema_shaping.py api2agent\generators\examples.py api2agent\diagnostics.py api2agent\cli.py
```

已通过：

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

结果：

```text
79 passed
```

已通过：

```text
pytest
```

结果：

```text
197 passed
```

Local dogfood 已通过：

- `tests\fixtures\openapi\discriminator.yaml`
- generated README body summary
- `api2agent inspect` discriminator schema hints
- `api2agent diagnose` discriminator findings
- generated manual write example 选择并设置 discriminator value

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Compiler 现在会在最能帮助 Agent capability packages 的地方使用 discriminator metadata：human-readable polymorphic summaries、deterministic example generation、inspect hints 和 advisory diagnostics。它保持 raw schema compatibility，也避免跨入 runtime branch validation 或 type generation。

这关闭了 schema shaping 之后识别出的 discriminator handling gap。

## Remaining Risks

### Branch Matching Is Pragmatic

Mapping 和 tag matching 使用可用的 resolved branch labels、titles 和 tag property values。这有助于 generated capability clarity，但不是完整 discriminator semantic validation。

### Mapping Resolution Is Bounded

部分 `$ref` intent 在 normalization 后无法完全重建。Unresolved mappings 会通过 diagnostics 报告，而不是作为 generation blockers。

### Response Documentation Remains Sparse

Request body examples 和 tool input schemas 现在更清楚，但 generated response documentation 对 success/error payloads 和 polymorphic response bodies 仍缺少同等丰富度。

### Diagnostics Are Advisory

Discriminator diagnostics 用于识别 likely Agent confusion。除 existing package quality score semantics 外，它们不会阻止 generation。

### No Runtime Branch Validation

Generated runners 不会在 runtime coerce payloads、validate branch selection 或用 LLM 选择 branch。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Response Shape Documentation Design v0
```

该设计应定义 generated documentation、inspect output、diagnostics 和 dogfood evidence 如何表达 response payload shapes、status-code differences、error bodies、examples 和 schema caveats，同时保持 deterministic offline generation，并兼容 existing package schemas。
