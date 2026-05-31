# Agent Capability Compiler OpenAPI Schema Shaping Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 OpenAPI hardening implementation slice 应为：

```text
Agent Capability Compiler OpenAPI Schema Shaping Implementation v0
```

这个 slice 应改进 OpenAPI request 和 response schemas 的 normalization、display，以及 Agent-facing input examples 生成方式，但不把 compiler 变成完整 JSON Schema compiler。

它必须保持 API-first，不得增加 workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## 为什么现在做这个 slice

Compiler 现在已经保留 examples/defaults、security requirement combinations 和 server metadata。下一个真实 specs 接入 gap 是 schema clarity。

真实 OpenAPI specs 经常包含：

- OpenAPI 3.0 `nullable: true`
- OpenAPI 3.1 `type: ["string", "null"]`
- request body schemas 里的 `readOnly` server-generated fields
- response schemas 里的 `writeOnly` secrets
- 通过 `additionalProperties` 表达的 dictionary objects
- 包含 nested object 或 polymorphic item schemas 的 arrays
- nested `oneOf` / `anyOf` branches
- required 和 optional fields 很难区分的大对象

当前 generation 会保留很多 raw schema details，但 generated README、tool schemas、examples、diagnostics 和 inspect output 还没有把这些 shape 表达得足够清楚，难以保证可靠 Agent use。

## Current Baseline

已有：

- local `$ref` resolution
- recursive schema normalization
- `allOf` object merge
- `oneOf` 和 `anyOf` preservation
- parameter、request body 和 response schemas 使用 normalized schema dictionaries
- README schema summaries 支持 object、array、`oneOf`、`anyOf`、scalar type 和 default
- generated examples 优先使用 explicit examples、defaults 和 enums
- object request body examples 支持 required-only
- diagnostics 支持 broad object schemas 和 required bodies without schemas

重要 gaps：

- OpenAPI 3.0 `nullable` 没有显示为 nullable input/output information
- OpenAPI 3.1 type arrays 没有一致 summarization
- request examples 和 tool schemas 可能包含 `readOnly` server-generated fields
- response summaries 可能在没有 context 的情况下暴露 `writeOnly` fields
- dictionary objects 被展示成 broad objects，而不是 map semantics
- README 和 examples 中 array item details 偏浅
- nested `oneOf` / `anyOf` 可能难以阅读
- compact schema summaries 没有展示 required versus optional object properties
- diagnostics 没有指出常见会迷惑 Agents 的 schema complexity patterns

## Goals

- 让 Agent-facing request input schemas 更清楚，并减少要求用户提供 server-generated fields 的概率
- 保持现有 generated `capability.json` backward compatibility
- 尽量以 additive compatible 方式保留 raw schema dictionaries
- 把 nullable forms normalise 成 readable metadata，不丢 OpenAPI 3.0 或 3.1 intent
- 按 request/response direction 处理 `readOnly` 和 `writeOnly`
- 展示 `additionalProperties` 的 dictionary/map semantics
- 改进 array item display 和 generated examples
- 改进 README 和 inspect 中 nested `oneOf` / `anyOf` readability
- 在 compact summaries 中展示 required 和 optional object fields
- 为需要 user attention 的 schema shapes 增加 deterministic diagnostics
- 保持 generation deterministic and offline

## Non-Goals

不实现：

- full JSON Schema validator
- 完整 OpenAPI 3.1 JSON Schema dialect support
- LLM-based schema simplification
- runtime schema coercion
- generated UI form rendering
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed IR Strategy

保留现有 schema fields：

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

如果 implementation 需要，只增加 optional shaped metadata：

```text
SchemaAnnotations:
  nullable: bool
  read_only_fields: list[str]
  write_only_fields: list[str]
  map_fields: list[str]
  polymorphic_paths: list[str]
  array_without_items: list[str]
  required_fields: list[str]
  optional_fields: list[str]

RequestBody.input_schema: dict | None
Response.output_schema: dict | None
```

v0 implementation 应优先使用 helper functions，避免大幅 IR churn。如果增加 `input_schema` 或 `output_schema`，它们必须是 additive，并由现有 normalized schema 派生。

Generated `capability.json` 保持 backward compatible，因为现有 `schema` fields 仍保留。旧 consumers 可以继续读取当前 schema dictionaries。

## Shaping Rules

Schema shaping 应具备 context-aware 能力：

```text
request input schema
response output schema
neutral documentation schema
```

对于 request input schemas：

1. 保留 `writeOnly` fields，因为 clients 可能需要发送 secrets
2. omit 或明确标记 `readOnly` fields，避免 Agents 要求用户提供 server-generated values
3. read-only filtering 后 required fields 仍保持 deterministic
4. nullable fields 在 summaries 和 examples 中可见
5. 保留 `additionalProperties` 作为 map semantics

对于 response output schemas：

1. 保留 `readOnly` fields，因为 server-generated values 是预期结果
2. omit 或明确标记 `writeOnly` fields，避免 response summaries 暗示 secrets 会返回
3. nullable fields 在 summaries 中可见
4. 保留 map 和 polymorphic semantics

对于 neutral documentation schemas：

1. 在存在时同时展示 `readOnly` 和 `writeOnly` markers
2. 展示 required versus optional properties
3. 保持 nested polymorphic branches readable and bounded

## Nullable Policy

OpenAPI 3.0：

```yaml
type: string
nullable: true
```

OpenAPI 3.1：

```yaml
type:
  - string
  - "null"
```

两者都应在 generated documentation 和 inspect output 中显示为 nullable。除非本地 parser convention 已经这么做，否则 implementation 不应强行把 raw schema 中的一种表示改成另一种。

Examples 应在存在可用值时选择 non-null example。只有在 schema 允许且没有更好的 default、example、enum 或 type fallback 时，才使用 null。

当 nullable request fields 存在时，diagnostics 可以发出 informational finding：`nullable_fields_present`。

## ReadOnly And WriteOnly Policy

Request direction：

- `readOnly: true` 表示字段由 server 拥有，默认不应要求 user 提供
- `writeOnly: true` 表示字段可以保留在 request input examples 和 tool schemas 中

Response direction：

- `readOnly: true` 保持可见
- `writeOnly: true` 应 hidden 或明确标记，避免 docs 暗示该值会被返回

Implementation 应避免改变 raw OpenAPI source semantics。Direction-specific shaped helpers 可为 generated tool parameters、README request examples、smoke/manual examples 和 response summaries 过滤字段。

Diagnostics candidates：

- `read_only_request_fields`
- `write_only_response_fields`

## Additional Properties Policy

`additionalProperties` 应被保留并解释：

```yaml
type: object
additionalProperties:
  type: string
```

README 和 inspect 应把它显示为 map-like object，例如：

```text
object map[string]
```

对于 `additionalProperties: true`，显示 broad map/object shape，而不是 closed object。对于 `additionalProperties: false`，避免暗示允许 arbitrary keys。

Diagnostics candidate：

- `additional_properties_present`

## Array Policy

Arrays 应在可知时显示 item schemas：

```text
array[string]
array[object {id:string, name:string?}]
array[oneOf[string | object]]
```

当 `items` 缺失时，保持 generation compatible，但暴露 ambiguity：

- README：`array[unknown]`
- examples：除非存在 explicit example/default，否则使用 `[]`
- diagnostics：`array_without_item_schema`

Nested arrays 应 compact summary，避免展开成不可读输出。

## Polymorphism Policy

`oneOf` 和 `anyOf` 应继续保留。v0 应改进它们的 summarization，而不是自动选择 branches。

README 和 inspect 应：

- 区分 `oneOf` 和 `anyOf`
- 显示 bounded list of branch summaries
- 避免无限递归展开大型 nested branches
- 在存在时显示 discriminator names

Generated examples 应保留当前 deterministic behavior，除非 explicit examples/defaults 已经选择 shape。不要用 LLM 发明 branch selection。

Diagnostics candidate：

- `nested_polymorphic_schema`

## Required And Optional Field Display

Object summaries 应让 required fields 可见：

```text
object {id:string, name:string?, email:string?}
```

具体 display syntax 可以保持 compact，但 generated docs 不应让 optional fields 看起来像 required。对于 request bodies，这一点尤其重要，因为 read-only filtering 后，server-generated required response field 不一定是 shaped input 中的 required field。

Diagnostics candidate：

- `large_object_schema`

## Generated Artifact Effects

README：

- 清楚显示 nullable fields
- mark 或 omit read-only request fields
- 在有用时标记 write-only request fields
- 显示 `additionalProperties` 的 map semantics
- 显示 array item summaries
- 显示 bounded `oneOf` / `anyOf` branch summaries
- 区分 required 和 optional object fields

OpenAI tools schema / generated tool params：

- request bodies 使用 request-direction shaping
- 默认不要求 `readOnly` fields
- 保留 `writeOnly` fields
- 保持现有 parameter schemas compatible

Examples and smoke/manual tests：

- 像现在一样优先 explicit examples/defaults/enums
- 从 shaped request input schemas 构造 object examples
- nullable examples 尽量选择 non-null 值
- ambiguous arrays 在没有 examples/defaults 时保持 empty

`api2agent inspect`：

- 显示 schema shaping summary counts
- compact 暴露 nullable、read-only/write-only、map、array 和 polymorphic hints

Diagnostics：

- `nullable_fields_present`
- `read_only_request_fields`
- `write_only_response_fields`
- `additional_properties_present`
- `nested_polymorphic_schema`
- `array_without_item_schema`
- `large_object_schema`

## Implementation Plan

1. 增加 direction-aware shaping 和 compact summaries 的 schema helper functions。
2. 保留现有 raw normalized schemas。
3. 增加 OpenAPI 3.0 和 OpenAPI 3.1 forms 的 nullable detection。
4. 增加过滤或标记 `readOnly` object fields 的 request-body shaping。
5. 增加过滤或标记 `writeOnly` object fields 的 response shaping。
6. 改进 README schema formatter，覆盖 nullable、maps、arrays、polymorphism 和 optional fields。
7. 更新 generated tool parameter schemas，对 bodies 使用 request-direction shaping。
8. 更新 example generation，使用 shaped request input schemas。
9. 增加 schema complexity 和 directionality diagnostics。
10. 增加 fixtures 和 regression tests。

## Tests

新增 fixtures：

- OpenAPI 3.0 nullable fields
- OpenAPI 3.1 nullable type arrays
- 包含 `readOnly` 和 `writeOnly` properties 的 request body objects
- 包含 `readOnly` 和 `writeOnly` properties 的 response objects
- `additionalProperties` 为 schema、`true` 和 `false`
- arrays with object items、polymorphic items 和 missing items
- nested `oneOf` / `anyOf`
- required 和 optional object properties

Regression tests 应覆盖：

- parser preserves raw schema compatibility
- README displays nullable fields
- README displays required versus optional fields
- generated request body examples do not require read-only fields
- generated request body examples preserve write-only fields
- response summaries do not imply write-only fields are returned
- map object summaries are readable
- arrays without item schemas are diagnosed
- nested polymorphic schemas are bounded in summaries
- old capability JSON without shaped schema metadata remains valid

## Dogfood

使用 local dogfood：

- existing `composition.yaml`
- new schema-shaping fixture with nullable/readOnly/writeOnly/map/array cases
- generated README review
- `api2agent inspect`
- `api2agent diagnose`
- generated smoke/manual examples

不需要网络依赖。

## Success Metrics

Implementation 成功条件：

- generated Agent-facing inputs 不再要求 obvious server-generated fields
- nullable 和 map semantics 在 generated docs 中可见
- arrays 和 polymorphic schemas 被 compact summary
- request body examples 保持 deterministic 且更有用
- diagnostics 标记 likely to confuse Agents 的 schema shapes
- 现有 schema composition behavior 保持 compatible
- full Python test suite passes

## Acceptance Criteria For This Design

- current schema handling baseline and gaps 已文档化
- additive compatibility strategy 已定义
- direction-aware request/response shaping rules 已定义
- nullable、readOnly/writeOnly、additionalProperties、array、polymorphism 和 required/optional policies 已定义
- generated README、tools schema、examples、inspect 和 diagnostics effects 已定义
- tests and dogfood 已命名
- non-goals 保持 API-first compiler boundaries
