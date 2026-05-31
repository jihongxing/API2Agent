# Agent Capability Compiler OpenAPI Real-Spec Calibration Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 Agent Capability Compiler implementation slice 应为：

```text
Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Implementation v0
```

这个 slice 应为一小组 curated real OpenAPI specs 创建 repeatable local calibration harness。Harness 应衡量 generated package 在 summaries、examples、diagnostics、package size、filtering guidance 和 first-call ergonomics 上的可用性，但不增加 runtime validation、hosted services、provider onboarding、workflow execution、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation。

## 为什么现在做这个 Slice

Compiler 已完成主要 OpenAPI hardening run：

- examples/defaults propagation
- security requirement combinations
- server handling
- schema shaping
- discriminator handling
- response shape documentation
- bounded JSON Schema keyword coverage
- diagnostics and inspect visibility

下一项风险已经不再是某个明显缺失功能，而是 calibration：真实 specs 可能暴露 summary density、noisy diagnostics、missing filter guidance、awkward examples、oversized packages，或单独 fixtures 看不出的 schema/auth/server 组合问题。

Baseline audit 已经展示了这个模式：

- GitHub REST 成功生成，但 unfiltered package 有 1186 tools。
- Swagger Petstore 暴露 relative server URL 和 auth-boundary issues。
- curl 和 simple OpenAPI packages 能工作，但 large real specs 需要更好的 guidance。

Compiler 现在需要稳定的 real-spec evidence loop，然后再选择下一项 semantic feature。

## Goals

- 定义 local、repeatable real-spec calibration harness
- 默认保持 calibration deterministic and offline
- 在 curated corpus 上衡量 generated package quality
- 用 machine-readable artifact 记录 package-level 和 tool-level metrics
- 让 summary readability、example quality、diagnostics noise 和 package size regressions 可见
- 用证据识别下一项 OpenAPI hardening gap，而不是靠直觉
- 保留 API-first compiler boundary

## Non-Goals

不实现：

- 默认 calibration 中的 real provider execution
- main suite 中的 network-dependent tests
- runtime request 或 response validation
- OpenAPI 3.1 dialect enforcement
- LLM-based schema interpretation
- provider marketplace onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- production gateway permission source
- workflow runtime
- automatic snapshot publish/reload

## Calibration Corpus

使用一组 small curated corpus，并带明确 purpose labels。实现应先支持 local paths，之后再支持 optional user-provided paths。

推荐 corpus slots：

| Slot | Purpose | Examples Of Signals |
| --- | --- | --- |
| `small_reference` | compact baseline spec | README clarity、examples、response summaries |
| `large_rest` | large endpoint surface | tool count、filter guidance、inspect truncation、generation time |
| `auth_rich` | security combinations | auth alternatives、combined auth、endpoint overrides |
| `server_rich` | servers and variables | relative servers、variables、environment/profile hints |
| `schema_rich` | schema complexity | nullable/readOnly/writeOnly、discriminators、keyword markers、response docs |
| `write_heavy` | safety and manual paths | read/write split、manual write examples、diagnostics |

Initial sources 可以复用 existing fixtures 作为稳定 regression，也可以使用 prior dogfood 中已有 local cached copies 的 known public specs。Harness 不应要求 network access 才能 pass。

## Calibration Metrics

Harness 应输出一个 JSON artifact：

```text
.dogfood/openapi-real-spec-calibration/result.json
```

推荐 top-level fields：

```text
contract_version
generated_at
cases
summary
recommendations
```

Per case：

```text
case_id
purpose
source_path
filters
generated
tool_count
read_tools
write_tools
delete_tools
unknown_safety_tools
required_parameter_count
schema_hint_counts
response_category_counts
diagnostics_status
diagnostics_score
diagnostics_summary
finding_counts
readme_bytes
capability_bytes
generation_ms
inspect_excerpt
sample_tool_details
```

Artifact 应足够 deterministic 以便 review；timestamps 可以保留 informational。

## Scoring And Gates

Calibration 初期应偏 report-oriented，而不是 hard release gate。

推荐 status：

- `pass`：generated package exists，diagnostics usable，且没有 calibration-specific severe issue
- `warn`：package generated，但暴露 high tool count、warning-heavy diagnostics、missing base URL、too many required inputs 或 noisy summaries
- `fail`：generation fails、output missing required artifacts、diagnostics JSON cannot load，或 inspect cannot render

推荐 warning thresholds：

- `tool_count > 50`
- `diagnostics_status == "fail"`
- `diagnostics_score < 60`
- `readme_bytes > 200_000`
- `generation_ms > 30_000`
- no read tools when write/delete tools exist
- schema hint categories present but no readable inspect detail

Thresholds 应作为 calibration defaults 记录，而不是 product promises。

## Harness Behavior

Implementation 应增加 script，而不是新 production runtime：

```text
scripts/api2agent_openapi_real_spec_calibration.py
```

Behavior：

1. load small manifest of calibration cases
2. direct 调用 `parse_openapi_file` 和 `generate_package`
3. per case 可选 include-tag/include-path/include-operation/max-tools filters
4. load generated `capability.json` 和 `diagnostics.json`
5. 尽量复用现有 helpers 计算 metrics
6. run inspect-style summarization，不调用 external services
7. 写入 `.dogfood/openapi-real-spec-calibration/result.json`
8. 打印 concise summary table

Script 应把 temporary outputs 放在 `.dogfood/openapi-real-spec-calibration/generated/` 下。

## Manifest Strategy

先用 script 中的 Python-defined manifest，或者如果仓库已有合适 pattern，则用小型 JSON/YAML manifest。

每个 case 应定义：

```text
case_id
purpose
source_path
filters
expected_status
notes
```

First implementation 可以用 existing local fixtures 填充大多数 slots；如果没有 local copy，large real-spec cached paths 可以保持 optional。Optional cases 应 marked skipped，而不是让 harness fail。

## Generated Artifact Review

Harness 应捕获 short excerpts，而不是完整 README copies：

- first 5 inspect lines
- first 5 tool detail lines
- schema hints summary
- response categories summary
- top diagnostics finding ids
- selected read tool 的 first-call params（如果存在）

这样 calibration artifacts 可 review，也避免提交 bulky generated packages。

## Tests

新增 regression coverage：

- manifest case loading
- metrics extraction from generated packages
- skipped optional case behavior
- pass/warn/fail status classification
- result artifact contract fields
- no network dependency
- generated output path containment under `.dogfood/openapi-real-spec-calibration`

使用 existing fixtures：

- `basic.yaml`
- `schema_keywords.yaml`
- `security_combinations.yaml`
- `server_choices.yaml`
- `unsafe.yaml`
- test 中生成 synthetic large spec，或复用 existing large-spec tests

## Dogfood

运行：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Expected dogfood output：

- JSON artifact at `.dogfood/openapi-real-spec-calibration/result.json`
- concise console summary with case statuses
- at least one small baseline case
- at least one schema-rich case
- at least one auth-rich case
- at least one server-rich case
- one large-surface case, synthetic or cached real spec

## Output Review Questions

Implementation report 应回答：

1. Which case produced the noisiest diagnostics?
2. Which case produced the largest package?
3. Which summaries were hardest to read?
4. Which generated examples remained generic?
5. Which diagnostics should become more precise?
6. Which real-spec gap should become the next hardening task?

## Success Metrics

Implementation 成功标准：

- calibration 可以在本地无网络运行
- results machine-readable，且足够 concise 以便 review
- generated package metrics 可以跨 cases 比较
- oversized packages 和 diagnostics-heavy cases 可见
- optional real-spec inputs 可以 cleanly skipped
- full Python test suite passes

## Acceptance Criteria For This Design

- calibration-after-keyword-coverage rationale 已记录
- corpus slots 已定义
- metric contract 已定义
- status thresholds 已定义
- harness behavior 已定义
- manifest and artifact strategy 已定义
- tests and dogfood 已命名
- non-goals preserve API-first compiler boundaries
