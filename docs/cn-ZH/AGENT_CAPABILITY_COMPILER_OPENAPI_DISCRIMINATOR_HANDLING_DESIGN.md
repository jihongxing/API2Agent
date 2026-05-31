# Agent Capability Compiler OpenAPI Discriminator Handling Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 OpenAPI hardening implementation slice 应为：

```text
Agent Capability Compiler OpenAPI Discriminator Handling Implementation v0
```

这个 slice 应让 OpenAPI discriminator metadata 对 Agent-facing polymorphic schemas 可见且有用，同时保留 raw schema compatibility 和 offline deterministic generation。

它必须保持 API-first，不得增加 full JSON Schema validator、generated SDK type system、workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## 为什么现在做这个 slice

Schema shaping 现在已经处理 nullable fields、readOnly/writeOnly directionality、maps、arrays、required/optional summaries 和 bounded `oneOf` / `anyOf` display。剩下最大的 polymorphism gap 是 discriminator handling。

真实 OpenAPI specs 经常用 discriminators 解释哪个 schema branch 生效：

```yaml
oneOf:
  - $ref: "#/components/schemas/CardPayment"
  - $ref: "#/components/schemas/BankTransfer"
discriminator:
  propertyName: type
  mapping:
    card: "#/components/schemas/CardPayment"
    bank_transfer: "#/components/schemas/BankTransfer"
```

当前 generation 会保留 raw dictionary，但 generated summaries、examples 和 diagnostics 不会解释 `type=card` 如何映射到 card branch。Agents 看到的是 polymorphic object，却看不到 branch-selection key。

## Current Baseline

已有：

- local `$ref` resolution
- recursive schema normalization
- raw `discriminator` dictionaries 会保留，因为 unknown schema keys 被保留
- `oneOf` 和 `anyOf` preservation
- schema shaping 显示 bounded polymorphic summaries
- diagnostics 可以报告 nested polymorphic schemas
- generated examples 保持 deterministic，不使用 LLM branch selection

重要 gaps：

- README 或 inspect schema summaries 不显示 discriminator `propertyName`
- discriminator `mapping` entries 不显示
- generated examples 不设置 discriminator property
- branch labels 是 generic summaries，而不是 mapped names
- diagnostics 不报告 discriminator presence 或 malformed discriminator metadata
- unresolved mapping targets 不会浮出
- 无法设置 discriminator value 的 branches 不会被标记

## Goals

- 保留 raw discriminator metadata，不改变现有 schema fields
- 在 README 和 inspect summaries 中显示 discriminator property names
- compact 显示 mapping values 和 branch labels
- 当没有 explicit example/default 时，使用 discriminator metadata 改进 deterministic request examples
- 诊断真实 specs 中常见 discriminator 问题
- 保持 generated OpenAI tool schemas 与 request-direction schema shaping compatible
- 保持 generation deterministic and offline
- 不变成 schema validator 或 type generator

## Non-Goals

不实现：

- full JSON Schema validation
- complete OpenAPI 3.1 discriminator semantics
- runtime branch validation or coercion
- LLM branch selection
- generated SDK classes or tagged union types
- UI form rendering
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed Compatibility Strategy

保留现有 raw schema fields：

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

v0 不要求新增 IR model。优先在 schema shaping layer 中使用 helper functions，从 raw schemas 派生 discriminator facts：

```text
DiscriminatorSummary:
  property_name: str
  mapping_keys: list[str]
  branch_count: int
  unresolved_mappings: list[str]
  branch_labels: list[str]
```

如果未来 implementation 需要 additive metadata，它必须是 optional，并由 raw schema dictionaries 派生。

旧 generated `capability.json` files 仍然 valid。

## Discriminator Extraction Rules

对于任何 schema object：

1. 只有当 `discriminator` 是 object 时才检测
2. 当 `propertyName` 是非空 string 时读取它
3. 当 `mapping` 是 object 时读取它
4. 保留 mapping keys 作为 candidate discriminator values
5. 保留 mapping targets 为 strings；不要求所有 targets 都是 local refs
6. 将 discriminator metadata 与 sibling `oneOf` / `anyOf` branches 关联
7. parsing 阶段不选择或验证 branches

Parser 可以继续保留 raw schemas。v0 大部分行为可放在 schema shaping helpers、diagnostics、README formatting、inspect 和 example generation 中。

## Summary Formatting Rules

Schema summaries 应让 discriminator intent 可见：

```text
oneOf[discriminator=type: card=>CardPayment | bank_transfer=>BankTransfer]
```

当 branch labels 无法 resolve 时，回退到已有 bounded branch summaries：

```text
oneOf[discriminator=type: card=>object {...} | bank_transfer=>object {...}]
```

对于 missing 或 invalid mapping：

```text
oneOf[discriminator=type: object {...} | object {...}]
```

Summaries 应保持 bounded：

- 最多显示现有 branch display limit
- 对 additional branches 使用 `...`
- 不无限递归展开同一 recursive branch
- 保留 `oneOf` 与 `anyOf` 的区别

## Example Generation Rules

当 request body schema 有 discriminator 且没有 explicit example/default/examples map 时：

1. 如果存在 `mapping`，使用 source order 中第一个 mapping key
2. 否则使用第一个 branch
3. 使用现有 deterministic example rules 从该 branch 构造 example
4. 尽可能把 discriminator property 设置为 selected mapping key
5. 如果 branch 用 `const`、`enum`、`default` 或 `example` 声明了 discriminator property，优先使用该值
6. 除非没有 mapping 或 branch value，否则不要从 branch names 合成 values
7. 保持 schema shaping 中的 readOnly filtering 和 writeOnly preservation

这会改进 first-call examples，但不假装验证每个 branch。

## OpenAI Tools Schema Rules

Generated OpenAI tool schemas 应：

- 在 compatible downstream schema consumers 可接受时保留 raw discriminator metadata
- 对 request bodies 继续使用 request-direction shaping
- 当 discriminator property 不是 readOnly 时，为 request input 保持可见
- 不把 polymorphic branches flatten 成一个 merged object
- 不要求 source schema 未要求的 branch-specific fields

## Diagnostics

新增 deterministic findings：

- `discriminator_present`
- `discriminator_mapping_present`
- `discriminator_missing_property`
- `discriminator_without_polymorphism`
- `discriminator_mapping_unresolved`
- `discriminator_branch_without_tag`

Severity guidance：

- presence 和 mapping summaries 为 informational
- missing `propertyName` 为 warning
- discriminator without sibling `oneOf` / `anyOf` 为 warning
- unresolved local mapping targets 为 warning
- 无法识别 discriminator value 的 branch 根据是否影响 examples，设为 informational 或 warning

## Inspect And README Effects

README：

- 在 schema summaries 中显示 discriminator property
- 在 bounded branch summaries 中显示 mapping keys
- 当 examples 从 schema fallback 生成时，让 first-call/manual examples 包含 discriminator values

`api2agent inspect`：

- 在 schema hints 中包含 discriminator counts
- 显示 discriminator-aware body 和 parameter summaries

Diagnostics：

- 报告 discriminator quality findings
- 在 evidence 中包含 mapping keys 和 unresolved mapping targets

## Implementation Plan

1. 在 `api2agent/schema_shaping.py` 增加 discriminator extraction helpers。
2. 更新 polymorphic schema summaries，包含 discriminator property 和 mapping keys。
3. 为 request bodies 增加 deterministic discriminator-aware branch/example selection。
4. 选择 branches 时保留 request-direction readOnly/writeOnly shaping。
5. 为 discriminators 增加 schema hint counts。
6. 增加 diagnostics：presence、malformed metadata、unresolved mappings 和 untagged branches。
7. 通过现有 summary paths 覆盖 README 和 inspect。
8. 增加带 discriminator mapping 和 intentionally imperfect discriminator case 的 OpenAPI fixture。
9. 增加 parser、generator、diagnostics 和 CLI regression tests。
10. 本地 dogfood generated README、inspect、diagnose 和 manual examples。

## Tests

新增 fixtures：

- `oneOf` with discriminator `propertyName`
- `oneOf` with discriminator `mapping`
- `anyOf` with discriminator metadata
- missing `propertyName`
- discriminator without sibling `oneOf` / `anyOf`
- mapping target pointing at a local `$ref`
- mapping target that cannot be resolved
- branch with discriminator property enum/const/default/example
- request body branch with readOnly/writeOnly fields

Regression tests 应覆盖：

- raw discriminator metadata remains in parsed schema
- README schema summary shows `discriminator=<property>`
- README summary shows mapping keys
- request body examples set the discriminator property
- generated OpenAI tool body schema keeps discriminator metadata and request-direction shaping
- inspect shows discriminator schema hints
- diagnostics report discriminator presence and malformed mappings
- old capability JSON without discriminator metadata remains valid

## Dogfood

使用 local dogfood：

- a new discriminator fixture
- generated README review
- `api2agent inspect`
- `api2agent diagnose`
- generated manual write example

不需要网络依赖。

## Success Metrics

Implementation 成功条件：

- polymorphic schema summaries explain the branch selection key
- generated examples include a discriminator value when source metadata allows it
- malformed discriminator metadata is diagnosed
- existing schema shaping behavior remains compatible
- existing composition and schema shaping tests still pass
- full Python test suite passes

## Acceptance Criteria For This Design

- current discriminator baseline and gaps 已文档化
- compatibility strategy 已定义
- discriminator extraction rules 已定义
- summary formatting rules 已定义
- example generation rules 已定义
- OpenAI tools schema、README、inspect 和 diagnostics effects 已定义
- tests and dogfood 已命名
- non-goals 保持 API-first compiler boundaries
