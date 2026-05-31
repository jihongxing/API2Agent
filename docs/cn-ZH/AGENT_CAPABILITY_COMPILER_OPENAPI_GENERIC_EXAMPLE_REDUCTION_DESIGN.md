# Agent Capability Compiler OpenAPI Generic Example Reduction Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 Agent Capability Compiler implementation slice 应为：

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Implementation v0
```

这个 slice 应在 source OpenAPI specs 缺少 explicit examples/defaults 时，减少 first-call params、README snippets、smoke tests 和 manual write tests 中的 `"example"` 这类 generic generated example values。实现应使用 deterministic schema-aware and name-aware fallback rules，同时保留 source-provided examples、defaults、enums、consts 和 schema keyword hints 的现有优先级。

## 为什么现在做这个 Slice

Compiler 现在已有：

- examples/defaults propagation
- formats、numeric bounds、string lengths、arrays、consts 和 enums 的 schema keyword example hints
- 带 `first_call_params` 的 real-spec calibration
- calibrated diagnostics scoring
- compact README/inspect/diagnostics summaries

Calibration harness 仍暴露一个具体缺口：

```text
small_reference_basic first_call_params:
{
  "tool": "get_user",
  "params": {
    "user_id": "example"
  }
}
```

这个值 deterministic，但偏弱。当没有 source example 时，`user_id: "user_123"` 比 `"example"` 更有用。first-call params 会出现在 README instructions、generated smoke tests、manual write tests 和 calibration artifact 中，所以这是现在最高杠杆的 hardening slice。

## Current Baseline

`api2agent/generators/examples.py` 中已有：

Priority order：

```text
parameter.example
parameter.examples[0]
schema.default
schema.example
schema.examples[0]
schema.enum[0]
schema.const
schema-derived fallback
```

Schema-derived fallback 已处理：

- `format: email`
- `format: uri` / `url`
- `format: uuid`
- `format: date`
- `format: date-time`
- `format: hostname`
- numeric min/max and exclusive min/max
- string min/max length
- array minItems/maxItems
- discriminator branch selection
- request-direction object shaping

重要缺口：

- generic string fallback 总是 `"example"`
- fallback 收不到 parameter/property name
- object field examples 不能使用 field names
- path/query/header parameter examples 不能使用 parameter names
- calibration 不统计 generic example values

## Goals

- reduce generic `"example"` values in generated first-call params
- preserve source-provided examples/defaults/enums/consts exactly
- preserve format/constraint-aware behavior
- use deterministic name-aware fallback for common API parameter names
- 让 generated README/test params 更真实，但不声称它们是 valid provider records
- keep implementation offline and deterministic
- keep raw package contracts compatible
- add calibration metrics for generic example frequency

## Non-Goals

不实现：

- LLM example generation
- provider calls to discover real IDs
- runtime request validation
- runtime schema validation
- random fake data
- seeded faker dependency
- 超出 bounded local name rules 的 semantic parsing
- secret generation or credential inference
- user/project-specific data generation
- workflow runtime
- marketplace/provider onboarding
- vault、billing、public CRUD、production gateway permission source 或 automatic propagation

## Example Priority Rules

Existing explicit-source priority 必须保持：

1. parameter/request-body explicit `example`
2. parameter/request-body explicit `examples`
3. schema `default`
4. schema `example`
5. schema `examples`
6. schema `enum`
7. schema `const`
8. schema format/constraint fallback
9. name-aware semantic fallback
10. type fallback

Name-aware fallback 绝不能覆盖 source-provided values 或 stronger schema facts。

## Name-Aware String Fallbacks

建议 bounded rules：

| Name Pattern | Example |
| --- | --- |
| `user_id`, `customer_id`, `item_id`, `order_id` | `user_123`, `customer_123`, `item_123`, `order_123` |
| any `*_id` | `{stem}_123` |
| `id` | `id_123` |
| `slug` / `*_slug` | `example-slug` |
| `name` / `*_name` | `Demo` |
| `title` | `Demo title` |
| `email` | `user@example.com` |
| `url`, `uri`, `website` | `https://example.com` |
| `phone` | `+15555550100` |
| `country` / `country_code` | `US` |
| `region` | `us-east-1` |
| `locale` | `en-US` |
| `currency` | `USD` |
| `status` | `active` |
| `type` / `kind` | `standard` |
| `cursor` / `page_token` / `next_token` | `cursor_123` |
| `trace_id` / `request_id` / `correlation_id` | `trace_123`, `request_123`, `correlation_123` |
| `api_key`, `token`, `secret`, `password` | `REPLACE_ME` |

规则：

- normalize names by lowercasing and converting `-` / spaces to `_`
- examples 要明显是 fake
- 不生成 real-looking secrets
- `format: uuid` 优先于 `_id` names
- semantic selection 后仍要 apply string length bounds
- 若没有 rule matched，最终 fallback 仍为 `"example"`

## Object Field Fallbacks

`example_value(schema)` 当前在递归 object properties 时不知道 property name。

Implementation 应 thread optional context：

```text
example_value(schema, name=None, required_only=False)
example_for_parameter(parameter) -> example_value(parameter.schema_, name=parameter.name)
```

Object properties：

```text
example_value(child_schema, name=property_name)
```

这样 request bodies 可生成：

```json
{
  "name": "Demo",
  "email": "user@example.com",
  "status": "active"
}
```

同时不新增 IR fields。

## Numeric And Boolean Name Hints

保留 existing numeric schema bounds 的优先级。仅在没有 bounds/defaults/examples 时增加小型 name-aware defaults：

| Name Pattern | Example |
| --- | --- |
| `limit`, `page_size`, `per_page` | `10` |
| `page` | `1` |
| `quantity`, `count` | `1` |
| `offset` | `0` |
| `active`, `enabled`, `published` | `true` |

这些规则应保持 conservative，并继续尊重 numeric min/max 和 integer/number type。

## Calibration Harness Effects

扩展 calibration metrics：

```text
generic_example_count
generic_first_call_params
```

建议 generic detection：

- exact string `"example"`
- minLength fallback 产生的 `"examplexxx"` 这类 repeated padding strings
- optional：nested occurrence counting inside first-call params

当 generated cases 中仍有 generic first-call params 时，harness 应增加 recommendation。

## Diagnostics Effects

v0 不需要新增 diagnostics finding。

Calibration harness 更适合测量 generic example quality，因为 example generation 是 advisory and package-local，不是 package correctness problem。

如果后续添加 diagnostics，也应只是 informational。

## README / Smoke Test / Manual Test Effects

Generated examples 会在现有使用 `example_for_parameter`、`example_for_request_body` 或 `example_value` 的地方自动改善：

- README sample command params
- README parameter/body example markers
- smoke test read-tool params
- manual write test params
- calibration first-call params

Generated runner behavior 不应改变。

## Test Plan

新增或更新 tests：

- `basic.yaml` first-call/readme/smoke params 使用 `user_123` 而不是 `example`
- explicit examples/defaults still win
- `format: uuid`、`format: email`、enums 和 consts 仍优先于 name rules
- object properties receive name-aware examples
- secret-like names use `REPLACE_ME`
- numeric name hints use conservative values
- string min/max bounds still apply after semantic selection
- calibration artifact reports generic example counts

优先直接测试 `api2agent.generators.examples`，再加一个 generated package regression 和一个 calibration regression。

## Dogfood Plan

运行：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Implementation 后预期：

- `small_reference_basic.first_call_params.params.user_id == "user_123"`
- `schema_rich_keywords` keeps UUID/email/date/const-aware examples
- examples/defaults fixture remains unchanged
- no calibration case fails from example changes
- generic example count decreases in generated cases

## Compatibility Strategy

Compatibility 已保留：

- raw OpenAPI parsing remains unchanged
- generated `capability.json` remains unchanged except generated sample artifacts may contain better examples
- generated runner behavior remains unchanged
- generated MCP schemas remain unchanged
- diagnostics contract remains unchanged

唯一有意改变的是 generated docs/tests/calibration artifacts 中更好的 deterministic sample values。

## Acceptance Criteria

- name-aware example fallback is implemented without overriding source examples/defaults/enums/consts/formats
- generic first-call params decrease in calibration output
- `basic.yaml` no longer emits `user_id: "example"` in generated sample params
- generated README/smoke/manual examples stay deterministic
- calibration artifact records generic example metrics
- targeted and full test suites pass
- 未新增 LLM generation、provider execution、runtime validation、hosted service、workflow、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Implementation v0
```
