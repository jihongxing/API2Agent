# Agent Capability Compiler OpenAPI Response Shape Documentation Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 OpenAPI hardening implementation slice 应该是：

```text
Agent Capability Compiler OpenAPI Response Shape Documentation Implementation v0
```

这个 slice 应让 generated Agent capability packages 中的 OpenAPI response shapes 更可见、更有用，同时保持 deterministic offline generation 和 raw schema compatibility。

它应保持 documentation-first。不得增加 runtime response validation、SDK type generation、LLM response transformation、workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## 为什么现在做这个 Slice

Compiler 现在已有更强的 request-facing 行为：

- examples/defaults 已保留
- security requirement combinations 已文档化
- server metadata 已可见
- request schema shaping 会过滤 read-only fields 并保留 write-only fields
- discriminator metadata 改善了 polymorphic request examples 和 summaries

剩下的不对称点是 response documentation。Generated README 和 inspect output 会告诉 Agents 如何调用 tool，但还没有充分说明 API 可能返回什么。

真实 OpenAPI specs 常包含：

- multiple success status codes
- structured error bodies
- `default` responses
- content-type variants
- response examples
- nullable and polymorphic response payloads
- 不应被暗示为 returned values 的 write-only fields

Agents 需要 compact、deterministic response guidance 来规划调用、检查失败，并判断 provider 是否适合任务。

## 当前 Baseline

已有：

- OpenAPI parser 会提取 `ResponseShape.status_code`、`description` 和 application/json `schema`
- `Response.schema_` 保留 normalized schema dictionaries
- schema shaping 支持 response direction summaries
- diagnostics 会报告 `write_only_response_fields`
- diagnostics 会把 response schemas 纳入 schema hint counts
- `api2agent inspect` 会把 response schemas 纳入 aggregate schema hint counts
- generated runner 返回 raw HTTP `status_code`、`ok`、`body` 和 error metadata

重要缺口：

- generated README 不列出 response status codes
- generated README 不显示 response schema summaries
- `api2agent inspect` 不显示 per-response details
- response content type 除 implicit application/json 行为外没有保留
- response examples 和 examples maps 没有保留
- success responses 和 error responses 没有分组或解释
- `default` response semantics 没有显式暴露
- diagnostics 不标记 documented status codes 缺少 response schemas
- diagnostics 不提示只有 error schemas 或没有 success schema 的 API
- polymorphic response payloads 只通过 aggregate hint counts 间接可见

## Goals

- 在 generated README 和 inspect output 中显示 response status codes
- 区分 success、redirect、client error、server error 和 `default` responses
- 用现有 schema shaping helpers 显示 compact response schema summaries
- 在已知时显示 response content type
- 保留可用的 response examples/default examples
- 让 structured error bodies 可见，同时不改变 runner behavior
- 诊断 missing 或 ambiguous response documentation
- 保持旧 generated `capability.json` files valid
- 保持 deterministic offline generation

## Non-Goals

不实现：

- runtime response validation
- runtime response coercion
- LLM-based response transformation
- existing capability mapping work 之外的 output normalization
- generated SDK classes or response types
- UI response viewers or forms
- full OpenAPI 3.1 JSON Schema dialect support
- content negotiation runtime behavior
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed Compatibility Strategy

保留现有 response schema source of truth：

```text
Response.schema_
```

只在需要时增加 optional response metadata：

```text
ResponseShape.content_type: str | None = None
ResponseShape.content_types: list[str] = []
ResponseShape.example: Any | None = None
ResponseShape.examples: list[Any] = []
```

这些字段必须是 additive，从 OpenAPI response `content` 派生，并对 old package JSON 安全。只包含 `status_code`、`description` 和 `schema` 的现有 packages 仍然 valid。

v0 的 response documentation 应使用 helper functions，而不是大范围 IR churn：

```text
response_category(status_code) -> success | redirect | client_error | server_error | default | unknown
format_response_summary(response) -> compact string
response_doc_findings(tool, response) -> diagnostics
```

## Extraction Rules

对每个 OpenAPI response：

1. preserve `status_code` as a string，包括 `default`
2. preserve `description` when present
3. 优先选择 `application/json` content when available
4. 否则 deterministic 选择第一个 content entry
5. preserve selected content type
6. 提取 selected content schema when present
7. preserve selected content object 上的 `example` 和 `examples`
8. v0 不合并 multiple content types
9. 不验证 examples 是否匹配 schemas
10. 通过现有 schema normalization 保持 raw schema compatibility

如果存在 multiple content types，应文档化 selected one，并可通过 diagnostic 提示 variants were present。

## Response Category Rules

把 response status codes 分类为：

```text
2xx -> success
3xx -> redirect
4xx -> client_error
5xx -> server_error
default -> default
other -> unknown
```

README 和 inspect 应使用这些 categories 提升可读性，但 generated runner behavior 不变。

## Summary Formatting Rules

README response lines 应 compact 且 bounded：

```text
  - responses:
    - 200 success application/json: object {id:string, name:string?} - OK
    - 400 client_error application/json: object {error:string, code:string?} - Bad request
    - default default application/json: object {message:string} - Error
```

没有 schema 时：

```text
    - 204 success: no documented body - No Content
```

content type 已知但 schema 缺失时：

```text
    - 202 success application/json: undocumented schema - Accepted
```

Summaries 应使用现有 schema shaping behavior：

- response direction for response payloads
- nullable display
- map and array summaries
- bounded `oneOf` / `anyOf`
- discriminator-aware polymorphic summaries
- write-only response filtering or marking

## README Effects

Generated README 应：

- 在每个 tool 下有 responses 时显示 response section
- 显示 status code、category、content type、schema summary 和 description
- 当 source examples 较短时，用 bounded inline 或 indented form 显示
- 避免暗示 write-only fields 会被返回
- 把 `default` responses 标识为 catch-all documented responses
- 通过限制每个 tool 的 response count 保持 large specs 可读

建议 bound：

- 每个 tool 最多显示 5 个 responses
- 更多 responses 时显示 overflow marker
- 保持 source order 优先

## Inspect Effects

`api2agent inspect` 应：

- 在 request details 旁显示 per-tool response summaries
- 保留 aggregate schema hint counts
- 以 compact 形式包含 response status category counts
- 为未来 JSON inspect output 保持 machine readability

示例：

```text
responses: 200 success application/json object {id:string}; 404 client_error application/json object {error:string}
```

## Diagnostics

新增 deterministic findings：

- `response_schema_present`
- `response_example_present`
- `response_without_schema`
- `success_response_without_schema`
- `error_response_schema_present`
- `default_response_present`
- `multiple_response_content_types`
- `response_polymorphic_schema`

Severity guidance：

- present schemas、examples、default responses 和 structured error bodies 为 informational
- body likely 存在但 success responses 缺少 schemas 时为 warning
- `204`/`304` 缺少 schemas 为 informational
- multiple content types 根据 selected type 是否明确，为 informational 或 warning
- polymorphic response payloads 为 informational，除非已由 discriminator diagnostics 覆盖 missing discriminator metadata

Diagnostics 保持 advisory，除 existing package quality score semantics 外不阻止 generation。

## Generated Runner Behavior

这个 slice 不改变 generated runner behavior。

Runner 继续返回：

```text
ok
status_code
body
error
```

Response documentation 用于 Agent planning 和 debugging。Runtime validation、coercion 和 normalized outputs 仍是独立产品决策。

## Implementation Plan

1. 给 `ResponseShape` 增加 optional `content_type`、`example` 和 `examples` fields。
2. 更新 OpenAPI response extraction，deterministic 选择并保留 content metadata。
3. 增加 response category 和 response summary helpers。
4. 在 README 每个 tool 下增加 response lines。
5. 增加 inspect response detail output。
6. 增加 diagnostics for missing schemas、examples、default responses、content variants 和 response polymorphism。
7. 增加覆盖 success、no-content、error、default、examples、multiple content types 和 polymorphic response schemas 的 fixtures。
8. 增加 parser、README/generator、diagnostics 和 CLI regression tests。
9. 本地 dogfood generated README、inspect 和 diagnose output。

## Tests

新增 fixtures 覆盖：

- `200` JSON success response with schema
- `201` JSON success response with example
- `204` no-body response
- `400` structured error response
- `404` structured error response
- `default` error response
- response with multiple content types
- response with nullable fields
- response with `oneOf` / `anyOf`
- response with discriminator metadata
- response with write-only property

Regression tests 应覆盖：

- old capability JSON without response metadata remains valid
- parser preserves response status、description、schema、selected content type 和 examples
- README lists response status categories and schema summaries
- README does not imply write-only response fields are returned
- inspect shows per-tool response details
- diagnostics report missing success response schemas
- diagnostics report structured error response schemas
- diagnostics report default responses and multiple content types
- full Python suite remains green

## Dogfood

本地 dogfood：

- new response-shape fixture
- generated README review
- `api2agent inspect`
- `api2agent diagnose`
- 如需确认 existing runner compatibility，可针对 local fixture server 执行 generated package

不需要网络依赖。

## Success Metrics

实现成功的标准：

- generated packages 能告诉 Agents successful responses 长什么样
- structured error bodies 在调用失败前可见
- response examples 在可用时被保留
- `default` 和 no-body responses 可理解
- response docs 复用 existing schema shaping 和 discriminator improvements
- diagnostics 能识别 sparse 或 ambiguous response docs
- existing generated runner behavior remains compatible
- full Python test suite passes

## Acceptance Criteria For This Design

- current response documentation baseline and gaps are documented
- additive compatibility strategy is defined
- response extraction rules are defined
- response category and summary formatting rules are defined
- README、inspect、diagnostics、parser 和 runner effects are defined
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
