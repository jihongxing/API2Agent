# Agent Capability Compiler Diagnostics Score Calibration Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent Capability Compiler 已实现 Diagnostics Score Calibration v0。

Diagnostics contract 保持兼容：existing `status`、`score`、`summary`、`metrics`、`generation_context` 和 `findings` 字段继续保留。评分现在基于明确的 impact profile，而不是只看 severity counts；每份 diagnostics payload 也会包含 `scoring_profile` 和 machine-readable `score_breakdown`。

本实现支持：

- `api2agent.diagnostics.score_profile.v0`
- `blocking`、`action_required`、`review_required`、`metadata_review` 和 `readiness` impact classes
- metadata penalty cap，避免 schema/auth/server-rich packages 因 useful visibility findings 被过度扣分
- per-finding action penalty cap，避免重复的 per-operation warnings 主导 package score
- `proxy_identity_ready` 等 zero-penalty readiness findings
- severity-based `status` compatibility：errors 仍然 fail，warnings 仍然 warn
- score breakdown shape、metadata-rich fixtures、blocking findings 和 unsafe write-heavy packages 的 regression coverage

本 slice 未新增 parser behavior、OpenAPI schema semantics、runtime validation、provider execution、hosted diagnostics service、workflow runtime、marketplace/provider onboarding、vault、billing、public CRUD、production gateway permission source 或 automatic propagation。

## Files

Implementation：

- `api2agent/diagnostics.py`

Tests：

- `tests/test_diagnostics.py`

Design reference：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_DESIGN.md`

## Diagnostics Contract

新增 top-level fields：

```text
scoring_profile
score_breakdown
```

Score profile：

```text
api2agent.diagnostics.score_profile.v0
```

`score_breakdown` 包含：

```text
base
penalty
score
impact_counts
penalties
finding_impacts
```

现在 `score` 来自 `score_breakdown["score"]`。`status` 仍然来自 severity summary counts。

## Calibration Evidence

本 slice 之前，local real-spec calibration harness 输出：

```text
OpenAPI real-spec calibration: 1 pass, 5 warn, 0 fail, 1 skipped
- small_reference_basic: pass tools=1 score=82
- schema_rich_keywords: warn tools=2 score=50 - diagnostics_score < 60
- auth_rich_security: warn tools=5 score=0 - diagnostics_score < 60
- server_rich_choices: warn tools=3 score=20 - diagnostics_score < 60
- write_heavy_unsafe: warn tools=2 score=40 - diagnostics_score < 60; no read tools when write/delete tools exist
- large_rest_synthetic: warn tools=60 score=80 - tool_count > 50
- optional_cached_real_spec: skipped tools=0 score=None - optional source_path is not present
```

本 slice 之后：

```text
OpenAPI real-spec calibration: 4 pass, 2 warn, 0 fail, 1 skipped
- small_reference_basic: pass tools=1 score=87
- schema_rich_keywords: pass tools=2 score=70
- auth_rich_security: pass tools=5 score=62
- server_rich_choices: pass tools=3 score=62
- write_heavy_unsafe: warn tools=2 score=56 - diagnostics_score < 60; no read tools when write/delete tools exist
- large_rest_synthetic: warn tools=60 score=82 - tool_count > 50
- optional_cached_real_spec: skipped tools=0 score=None - optional source_path is not present
```

现在信号更清晰：

- metadata-rich schema/auth/server fixtures 不再只是因为 expected review metadata 而低于 score threshold
- write-heavy unsafe packages 仍然 warn，并保持低于 score threshold
- large surfaces 仍然通过 calibration harness 的 `tool_count > 50` 保持 warn

## Validation

已通过：

```text
python -m py_compile api2agent\diagnostics.py scripts\api2agent_openapi_real_spec_calibration.py
```

已通过：

```text
python -m pytest tests\test_diagnostics.py tests\test_openapi_real_spec_calibration.py -q
```

结果：

```text
21 passed
```

已通过：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

已通过：

```text
python -m pytest -q
```

结果：

```text
212 passed
```

## Compatibility

Compatibility 已保留：

- diagnostics contract version 仍为 `api2agent.capability_diagnostics.v0`
- existing top-level diagnostics fields 继续存在
- `status` semantics 仍然基于 severity
- generated packages 仍会写入 `diagnostics.json`
- CLI 和 README diagnostics summaries 继续读取同一个 `score` 字段
- 新增字段对 existing consumers 是 optional

## 推荐下一项任务

```text
Agent Capability Compiler Diagnostics Score Calibration Closeout + Phase Review v0
```

Closeout 应判断 calibrated score profile 是否可以 close、action penalty cap 对更大的 cached real specs 是否足够，以及下一项 compiler hardening target 应该是 summary-noise reduction、generic-example reduction、cached real-spec corpus expansion，还是另一个 evidence-driven gap。
