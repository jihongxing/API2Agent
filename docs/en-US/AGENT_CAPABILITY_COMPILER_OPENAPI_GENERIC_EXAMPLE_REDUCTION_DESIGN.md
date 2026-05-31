# Agent Capability Compiler OpenAPI Generic Example Reduction Design v0

Date: 2026-06-01

Status: complete

## Decision

The next Agent Capability Compiler implementation slice should be:

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Implementation v0
```

This slice should reduce generic generated example values such as `"example"` in first-call params, README snippets, smoke tests, and manual write tests when source OpenAPI specs lack explicit examples/defaults. It should use deterministic schema-aware and name-aware fallback rules while preserving the existing priority of source-provided examples, defaults, enums, consts, and schema keyword hints.

## Why This Slice Now

The compiler now has:

- examples/defaults propagation
- schema keyword example hints for formats, numeric bounds, string lengths, arrays, consts, and enums
- real-spec calibration with `first_call_params`
- calibrated diagnostics scoring
- compact README/inspect/diagnostics summaries

The calibration harness still exposes a concrete gap:

```text
small_reference_basic first_call_params:
{
  "tool": "get_user",
  "params": {
    "user_id": "example"
  }
}
```

That value is deterministic, but weak. For first-call quality, `user_id: "user_123"` is more useful than `"example"` when no source example exists. This is now a high-leverage hardening slice because first-call params are used in README instructions, generated smoke tests, manual write tests, and the calibration artifact.

## Current Baseline

Already present in `api2agent/generators/examples.py`:

Priority order:

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

Schema-derived fallback already handles:

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

Important gap:

- generic string fallback is always `"example"`
- fallback does not receive the parameter/property name
- object field examples cannot use field names
- path/query/header parameter examples cannot use parameter names
- calibration does not count generic example values

## Goals

- reduce generic `"example"` values in generated first-call params
- preserve source-provided examples/defaults/enums/consts exactly
- preserve format/constraint-aware behavior
- use deterministic name-aware fallback for common API parameter names
- make generated README/test params more realistic without claiming they are valid provider records
- keep implementation offline and deterministic
- keep raw package contracts compatible
- add calibration metrics for generic example frequency

## Non-Goals

Do not implement:

- LLM example generation
- provider calls to discover real IDs
- runtime request validation
- runtime schema validation
- random fake data
- seeded faker dependency
- semantic parsing beyond bounded local name rules
- secret generation or credential inference
- user/project-specific data generation
- workflow runtime
- marketplace/provider onboarding
- vault, billing, public CRUD, production gateway permission source, or automatic propagation

## Example Priority Rules

The existing explicit-source priority must remain:

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

Name-aware fallback must never override source-provided values or stronger schema facts.

## Name-Aware String Fallbacks

Suggested bounded rules:

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

Rules:

- normalize names by lowercasing and converting `-` / spaces to `_`
- keep examples obviously fake
- do not generate real-looking secrets
- preserve `format: uuid` over `_id` names
- apply string length bounds after semantic selection
- if no rule matches, keep `"example"` as the final fallback

## Object Field Fallbacks

`example_value(schema)` currently does not know the property name when recursing into object properties.

Implementation should thread an optional context:

```text
example_value(schema, name=None, required_only=False)
example_for_parameter(parameter) -> example_value(parameter.schema_, name=parameter.name)
```

For object properties:

```text
example_value(child_schema, name=property_name)
```

This lets request bodies produce:

```json
{
  "name": "Demo",
  "email": "user@example.com",
  "status": "active"
}
```

without adding new IR fields.

## Numeric And Boolean Name Hints

Keep existing numeric schema bounds as primary. Add only small name-aware defaults when no bounds/defaults/examples exist:

| Name Pattern | Example |
| --- | --- |
| `limit`, `page_size`, `per_page` | `10` |
| `page` | `1` |
| `quantity`, `count` | `1` |
| `offset` | `0` |
| `active`, `enabled`, `published` | `true` |

These should be conservative and still respect numeric min/max and integer/number type.

## Calibration Harness Effects

Extend calibration metrics:

```text
generic_example_count
generic_first_call_params
```

Suggested generic detection:

- exact string `"example"`
- strings ending with repeated padding such as `"examplexxx"` from minLength fallback
- optional: nested occurrence counting inside first-call params

The harness should add a recommendation when generic first-call params remain in generated cases.

## Diagnostics Effects

No new diagnostics finding is required for v0.

The calibration harness is the better place to measure generic example quality because example generation is advisory and package-local, not a package correctness problem.

If diagnostics are added later, they should be informational only.

## README / Smoke Test / Manual Test Effects

Generated examples should improve anywhere `example_for_parameter`, `example_for_request_body`, or `example_value` is already used:

- README sample command params
- README parameter/body example markers
- smoke test read-tool params
- manual write test params
- calibration first-call params

No generated runner behavior should change.

## Test Plan

Add or update tests for:

- `basic.yaml` first-call/readme/smoke params use `user_123` instead of `example`
- explicit examples/defaults still win
- `format: uuid`, `format: email`, enums, and consts still win over name rules
- object properties receive name-aware examples
- secret-like names use `REPLACE_ME`
- numeric name hints use conservative values
- string min/max bounds still apply after semantic selection
- calibration artifact reports generic example counts

Prefer testing `api2agent.generators.examples` directly plus one generated package regression and one calibration regression.

## Dogfood Plan

Run:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Expected after implementation:

- `small_reference_basic.first_call_params.params.user_id == "user_123"`
- `schema_rich_keywords` keeps UUID/email/date/const-aware examples
- examples/defaults fixture remains unchanged
- no calibration case fails from example changes
- generic example count decreases in generated cases

## Compatibility Strategy

Compatibility is preserved:

- raw OpenAPI parsing remains unchanged
- generated `capability.json` remains unchanged except generated sample artifacts may contain better examples
- generated runner behavior remains unchanged
- generated MCP schemas remain unchanged
- diagnostics contract remains unchanged

The only intentional behavior change is better deterministic sample values in generated docs/tests/calibration artifacts.

## Acceptance Criteria

- name-aware example fallback is implemented without overriding source examples/defaults/enums/consts/formats
- generic first-call params decrease in calibration output
- `basic.yaml` no longer emits `user_id: "example"` in generated sample params
- generated README/smoke/manual examples stay deterministic
- calibration artifact records generic example metrics
- targeted and full test suites pass
- no LLM generation, provider execution, runtime validation, hosted service, workflow, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation is added

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Implementation v0
```
