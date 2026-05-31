# Agent Capability Compiler Diagnostics Score Calibration Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 Agent Capability Compiler implementation slice 应为：

```text
Agent Capability Compiler Diagnostics Score Calibration Implementation v0
```

这个 slice 应重新校准 diagnostics scoring，避免 metadata-rich OpenAPI packages 被当作真正 risky 或 broken packages 一样重罚。实现应保持 existing finding severities 和 diagnostic status semantics 兼容，但用明确的 finding impact/actionability rules 来计算 `score`，并暴露 `score_breakdown` 方便 review。

## 为什么现在做这个 Slice

OpenAPI real-spec calibration harness 给出了有用信号：

```text
OpenAPI real-spec calibration: 1 pass, 5 warn, 0 fail, 1 skipped
- schema_rich_keywords: warn score=50
- auth_rich_security: warn score=0
- server_rich_choices: warn score=20
```

这些 packages 是刻意 metadata-rich 的。它们的 warnings 和 info findings 有用，但很多是 expected review notes，而不是 severe risks。当前 score formula 太钝：

```text
penalty = errors * 35 + warnings * 10 + min(info * 2, 10)
score = 100 - penalty
```

这个公式把所有 warnings 一视同仁，也会让 expected metadata findings 把 package 分数压得比实际可用性更糟。

## Current Baseline

已有能力：

- deterministic findings with `id`、`severity`、`category`、`message`、`location`、`recommendation` 和 `evidence`
- summary counts by severity
- status derived from severity counts：
  - any errors -> `fail`
  - any warnings -> `warn`
  - otherwise `pass`
- score derived only from severity counts
- calibration harness captures diagnostics status、score、summary 和 finding counts

重要缺口：

- score 不区分 user-actionable risks 和 expected metadata richness
- 没有 score breakdown 解释 package 为什么扣分
- positive readiness findings，例如 `proxy_identity_ready`，仍会进入 info volume，间接降低 score
- metadata visibility findings 会主导 complex but valid OpenAPI specs 的 score

## Goals

- 保持 existing diagnostics JSON compatibility
- 保持 existing `severity` 和 `status` semantics stable
- 让 `score` 更反映 user-actionable risk，而不是 metadata volume
- 增加 machine-readable score explanation
- 降低 metadata-rich but usable packages 的 false-low scores
- 保持 true failures and unsafe packages visible
- 让 calibration harness output 更适合决定下一项 hardening task

## Non-Goals

不实现：

- new parser behavior
- new OpenAPI schema semantics
- runtime request or response validation
- LLM-based diagnostic triage
- provider execution
- hosted diagnostics service
- workflow runtime
- marketplace/provider onboarding
- vault、billing、public CRUD、gateway permission source 或 automatic propagation

## Compatibility Strategy

保留 existing fields：

```text
contract_version
status
score
summary
metrics
generation_context
findings
```

增加 optional fields：

```text
score_breakdown
scoring_profile
```

只读取 `status`、`score`、`summary` 和 `findings` 的 existing consumers 继续兼容。

v0 中保持 `status` 仍基于 severity。一个有 warnings 的 package 仍然报告 `warn`，即使 calibrated score 较高。

## Scoring Model

引入小型 score profile：

```text
api2agent.diagnostics.score_profile.v0
```

每个 finding id 映射到一个 impact class：

| Impact | Meaning | Suggested Penalty |
| --- | --- | --- |
| `blocking` | generation/runtime cannot be trusted | 35 |
| `action_required` | likely needs user action before Agent use | 10 |
| `review_required` | useful review item, not necessarily blocking | 4 |
| `metadata_review` | expected metadata visibility or caveat | 1 |
| `readiness` | positive readiness signal | 0 |

Score formula：

```text
penalty = sum(finding penalties)
score = max(0, min(100, 100 - penalty))
```

Cap `metadata_review` penalties：

```text
metadata_review_penalty <= 8
```

这样 rich schemas 不会因为 compiler 更透明而丢掉过多分数。

## Initial Finding Impact Mapping

### Blocking

- `duplicate_tool_names`
- `missing_base_url`
- `required_body_without_schema`

### Action Required

- `large_toolset`
- `no_read_tools`
- `write_only_package`
- `generic_capability_name`
- `generic_tool_name`
- `unknown_safety`
- `write_tools_present`
- `weak_tool_description`
- `many_required_parameters`
- `array_without_item_schema`
- `discriminator_missing_property`
- `discriminator_without_polymorphism`
- `discriminator_mapping_unresolved`
- `success_response_without_schema`
- `unsupported_auth_scheme`
- `unknown_auth`
- `auth_env_missing`
- `relative_server_url`

### Review Required

- `broad_object_schema`
- `read_only_request_fields`
- `write_only_response_fields`
- `conditional_schema_present`
- `dependent_schema_present`
- `deprecated_schema_fields` when emitted as warning

### Metadata Review

- `missing_provider_region`
- `missing_parameter_descriptions`
- `additional_properties_present`
- `nullable_fields_present`
- `nested_polymorphic_schema`
- `large_object_schema`
- `schema_keywords_present`
- `string_constraints_present`
- `numeric_constraints_present`
- `array_constraints_present`
- `const_schema_present`
- `pattern_schema_present`
- `unsupported_schema_keywords_present`
- `discriminator_present`
- `discriminator_mapping_present`
- `discriminator_branch_without_tag`
- `response_schema_present`
- `response_example_present`
- `response_without_schema`
- `error_response_schema_present`
- `default_response_present`
- `multiple_response_content_types`
- `response_polymorphic_schema`
- `auth_alternatives_present`
- `combined_auth_required`
- `query_api_key_auth`
- `cookie_api_key_auth`
- `metadata_only_oauth`
- `multiple_servers_present`
- `ambiguous_server_profiles`
- `server_variables_present`
- `path_server_override`
- `operation_server_override`
- `mixed_auth_summary`

### Readiness

- `proxy_identity_ready`

Unknown finding ids should default to `review_required` if severity is warning/error and `metadata_review` if severity is info.

## Score Breakdown Shape

新增：

```json
{
  "scoring_profile": "api2agent.diagnostics.score_profile.v0",
  "score_breakdown": {
    "base": 100,
    "penalty": 18,
    "score": 82,
    "impact_counts": {
      "blocking": 0,
      "action_required": 1,
      "review_required": 0,
      "metadata_review": 4,
      "readiness": 1
    },
    "penalties": {
      "blocking": 0,
      "action_required": 10,
      "review_required": 0,
      "metadata_review": 8,
      "readiness": 0
    },
    "finding_impacts": {
      "large_toolset": "action_required",
      "schema_keywords_present": "metadata_review"
    }
  }
}
```

这个结构应保持 compact，适合 generated `diagnostics.json`。

## Calibration Expectations

Implementation 后：

- `small_reference_basic` should remain high score
- `large_rest_synthetic` should still warn because `tool_count > 50`
- `write_heavy_unsafe` should still show meaningful penalty for no read/write-only behavior
- `auth_rich_security` 不应仅因为保存大量 auth metadata findings 就接近 0 分
- `server_rich_choices` 不应仅因为显示 server metadata 就接近 0 分
- `schema_rich_keywords` 应改善，但仍应对 conditional/dependent request-body caveats 给出 warning

建议目标：

```text
metadata-rich expected cases should score >= 60 unless they also have blocking/action_required risks.
```

## Implementation Plan

1. 在 `api2agent/diagnostics.py` 中添加 score profile constants。
2. 增加 helper，将每个 finding 映射到 impact 和 penalty。
3. 用 findings-based score computation 替换 `_score(summary)`。
4. 保持 `_status(summary)` 不变。
5. 在 diagnostics output 中添加 `score_breakdown` 和 `scoring_profile`。
6. 只有必要时才调整 formatting，保持 `diagnostics_summary_line` stable。
7. 为 old high-risk packages、metadata-rich packages、readiness findings、unknown finding fallback 和 score breakdown shape 增加 tests。
8. 重跑 real-spec calibration harness，并记录 before/after scores。

## Tests

新增或更新 tests：

- duplicate tool names still produce low score/fail
- missing base URL still produces low score/fail
- write-only packages still warn with meaningful penalty
- metadata-rich security combinations score higher than old blunt formula
- server-rich packages score higher than old blunt formula
- schema keyword visibility findings are capped as metadata penalties
- `proxy_identity_ready` has zero penalty
- `score_breakdown` includes impact counts、penalties 和 finding impact mapping
- diagnostics contract remains backward compatible for existing fields

## Dogfood

运行：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Compare before/after：

- `auth_rich_security`
- `server_rich_choices`
- `schema_rich_keywords`
- `write_heavy_unsafe`
- `large_rest_synthetic`

Implementation report 应包含 score delta。

## Success Metrics

Implementation 成功标准：

- full Python test suite passes
- diagnostics remain backward compatible
- score breakdown explains penalties
- metadata-rich calibration cases 不再仅因为保留 useful metadata 而显得灾难性不健康
- true risk cases still warn/fail visibly
- calibration harness output 更适合选择下一项 hardening work

## Acceptance Criteria For This Design

- current scoring weakness 已记录
- compatibility strategy 已定义
- impact classes 和 initial mapping 已定义
- score formula and metadata cap 已定义
- score breakdown shape 已定义
- calibration expectations 已定义
- implementation plan、tests 和 dogfood 已命名
- non-goals preserve API-first compiler boundaries
