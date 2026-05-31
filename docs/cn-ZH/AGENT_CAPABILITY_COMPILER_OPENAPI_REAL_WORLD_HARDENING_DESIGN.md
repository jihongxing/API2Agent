# Agent Capability Compiler OpenAPI Real-World Hardening Design v0

日期：2026-06-01

状态：complete

## 决策

OpenAPI real-world hardening 从这项开始：

```text
Agent Capability Compiler OpenAPI Examples + Defaults Propagation v0
```

这是第一项 implementation slice，因为它直接降低 generated package 到 first successful Agent/API call 之间的距离。真实 OpenAPI specs 往往包含可用的 examples、defaults、enums 和 request-body examples，但 compiler 还没有稳定地把它们保留进 generated test params、README examples 和 diagnostics evidence。

更大的 OpenAPI hardening track 继续保持 API-first，不引入 workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## 为什么这项先做

Quality diagnostics 已经能告诉用户 generated packages 哪里 risky、vague 或 missing useful metadata。下一步 compiler improvement 应把 source OpenAPI metadata 转化成更好的 generated artifacts。

Examples/defaults 杠杆很高，因为它影响：

- generated README first-call commands
- `api2agent test . --tool ... --params ...`
- smoke/manual write test usefulness
- required parameters 的 diagnostics findings
- 带 required path/query/header/body inputs 的真实 API onboarding time

## 当前 Parser Baseline

已经具备：

- OpenAPI file parsing
- local `$ref` resolution
- `allOf` object merge
- `oneOf` / `anyOf` preservation
- document/path/operation server URL handling
- server variable default substitution
- document and endpoint-level auth inference
- path/query/header parameter extraction
- JSON 和 first available request body content extraction
- response schema extraction
- parse 阶段的 tag/path/operation/max-tools filtering

重要缺口：

- parameter-level `example` 和 `examples` 未提升到 generated params
- request body media examples 未提升到 generated params
- schema `example`、`examples`、`default` 和 `enum` intent 未稳定展示
- nested object examples 未用于改善 body params
- diagnostics 还不能区分 "required but no example/default" 和 "required and source provided good sample data"
- filtering diagnostics 还不能解释为什么真实 spec 仍生成过多 Agent tools

## Goals

- 在不破坏现有 generated package contracts 的前提下，在 IR 中保留有用 OpenAPI examples/defaults
- 改善 required path/query/header/body inputs 的 generated README 和 test params
- 当 source examples 存在时，减少 generic `"example"` placeholder
- 用更好的 evidence 支撑 diagnostics 判断 required inputs 是否有可用 sample values
- 保持所有变化 deterministic 且 offline

## Non-Goals

不要实现：

- generation 期间真实 API execution
- LLM-based schema interpretation
- workflow composition
- non-API adapters
- provider marketplace submission
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- production gateway permission source
- automatic snapshot publish/reload

## 第一项 Implementation Slice

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Examples + Defaults Propagation v0
```

### Source Fields To Preserve

Parameters：

- `parameter.example`
- `parameter.examples`
- `parameter.schema.default`
- `parameter.schema.example`
- `parameter.schema.examples`
- first `parameter.schema.enum` value as fallback

Request bodies：

- `requestBody.content[content-type].example`
- `requestBody.content[content-type].examples`
- `requestBody.content[content-type].schema.default`
- `requestBody.content[content-type].schema.example`
- `requestBody.content[content-type].schema.examples`
- object property defaults/examples
- required scalar properties 的 first enum value as fallback

### IR Strategy

保持现有 `Capability` / `Tool` shape backward compatible。

推荐 additive model changes：

- `Parameter` 增加 `example: Any | None`
- `Parameter` 增加 `examples: list[Any]`
- `RequestBody` 增加 `example: Any | None`
- `RequestBody` 增加 `examples: list[Any]`

这些字段是 additive，现有 generated `capability.json` readers 应继续工作。

### Example Selection Order

Parameter example value：

1. explicit `parameter.example`
2. `parameter.examples` 的第一个 value
3. `schema.default`
4. `schema.example`
5. `schema.examples` 的第一个 value
6. `schema.enum` 的第一个 scalar
7. 现有 type-based fallback

Request body example value：

1. media `example`
2. media `examples` 的第一个 value
3. schema `default`
4. schema `example`
5. schema `examples` 的第一个 value
6. 使用 property defaults/examples/enums 从 required properties 构造 object
7. 现有 type-based fallback

### Generated Artifact Effects

Generated README：

- first-call params 应使用 preserved examples/defaults
- parameter/body details 应在有用时展示 default/example

Generated smoke/manual tests：

- selected tool calls 应使用更好的 example params
- write/delete tests 仍不得在没有 explicit opt-in 时执行

Diagnostics：

- 有 example/default 的 required parameters 不应在后续 diagnostics expansion 中触发 noisy missing-example findings
- 没有 source sample data 的 required parameters 可以继续保留 informational findings

## Later OpenAPI Hardening Tracks

### Security Requirement Combinations

后续设计：

- multiple security requirements
- OR vs AND requirement semantics
- query apiKey auth
- cookie apiKey auth
- OAuth scopes as metadata only
- diagnostics 和 README 中的 per-tool auth summaries

### Server Handling

后续设计：

- generated metadata 中的 multiple server choices
- staging/prod/regional servers 的 environment/profile hinting
- 更清晰的 operation-level server summaries
- safer handling of relative server URLs

### Schema Shaping

后续设计：

- `nullable`
- `readOnly` / `writeOnly`
- `additionalProperties`
- `array` examples
- nested `oneOf` / `anyOf` readability
- Agent-facing inputs 的 required-vs-optional object shaping

### Filtering Diagnostics

后续设计：

- explain unmatched filters
- generation 前 summarize top tags/path prefixes
- 为 oversized packages 推荐 filters
- 将 generation context persist 到 diagnostics

## Tests

Implementation 应增加 fixtures 和 tests 覆盖：

- parameter `example`
- parameter `examples`
- schema `default`
- schema `example`
- schema `enum`
- request body media `example`
- request body media `examples`
- nested object property examples/defaults
- generated README first-call params 使用 source examples
- generated smoke/manual tests 保持 safe write behavior
- 没有 example fields 的 old capability JSON 仍 valid

## Dogfood

本地 dogfood：

- existing `basic.yaml`
- examples/defaults fixture
- mixed-auth fixture，确保 auth behavior 不变
- curl-derived package，确保 curl generation 不受影响

如果本地有 safe real OpenAPI fixture，运行：

```text
api2agent generate real-openapi.yaml --include-path <safe-read-path> --output tmp/openapi-hardening
api2agent diagnose tmp/openapi-hardening
api2agent test tmp/openapi-hardening --tool <safe-read-tool> --params '<generated-example-params>'
```

Implementation tests 不需要 network dependency。

## Success Metrics

Implementation 成功条件：

- generated first-call examples 在 source OpenAPI examples/defaults 存在时使用它们
- required parameter/body examples 更少 generic
- refs、servers、auth、filters 和 safety 的既有 parser behavior 保持兼容
- diagnostics 和 README 更有用，且不变 noisy
- full Python test suite passes

## Acceptance Criteria For This Design

- first OpenAPI hardening implementation slice 已选择
- current parser baseline 和 gaps 已文档化
- example/default source fields 已指定
- additive IR changes 已指定
- example selection order deterministic
- generated artifact effects 已指定
- tests 和 dogfood 已命名
- non-goals 保持 API-first compiler boundaries
