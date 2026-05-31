# Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent Capability Compiler 已实现 OpenAPI real-spec calibration harness v0。

仓库现在有一个 local、deterministic calibration script，会从 curated OpenAPI corpus 生成 capability packages、提取 package quality metrics、分类 pass/warn/fail/skipped outcomes、写入 machine-readable artifact，并打印 concise review summary。

本实现支持：

- Python-defined calibration manifest with purpose-labeled corpus slots
- existing fixture coverage for small、schema-rich、auth-rich、server-rich 和 write-heavy cases
- local synthetic large OpenAPI spec，用于无网络 large-surface calibration
- optional cached real-spec cases，不存在时 cleanly skipped
- package metrics for tool counts、safety counts、required inputs、schema hints、response categories、diagnostics、artifact sizes、generation latency、inspect excerpts、sample tool details 和 first-call params
- 使用 documented warn/fail thresholds 的 status classification
- `.dogfood/openapi-real-spec-calibration/result.json`
- regression tests for manifest coverage、path containment、status classification、optional skips、artifact contract 和 synthetic large-surface warning behavior

本 slice 未增加 real provider execution、network-dependent main-suite tests、runtime validation、OpenAPI 3.1 dialect enforcement、LLM schema interpretation、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source、workflow runtime 或 automatic snapshot propagation。

## Files

Implementation：

- `scripts/api2agent_openapi_real_spec_calibration.py`

Tests：

- `tests/test_openapi_real_spec_calibration.py`

Design reference：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_DESIGN.md`

## Harness Contract

Script：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Artifact：

```text
.dogfood/openapi-real-spec-calibration/result.json
```

Contract version：

```text
api2agent.openapi_real_spec_calibration.v0
```

Top-level artifact fields：

```text
contract_version
generated_at
cases
summary
recommendations
```

Generated package directories 是 local dogfood outputs，位于：

```text
.dogfood/openapi-real-spec-calibration/generated/
```

## Corpus

Default cases：

- `small_reference_basic`
- `schema_rich_keywords`
- `auth_rich_security`
- `server_rich_choices`
- `write_heavy_unsafe`
- `large_rest_synthetic`
- `optional_cached_real_spec`

Optional cached real-spec case 在 local file 不存在时会 skipped，因此 harness 默认保持 offline and deterministic。

## Dogfood Evidence

运行：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

观察到：

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

Artifact 已写入：

```text
.dogfood/openapi-real-spec-calibration/result.json
```

## Output Review Answers

Noisiest diagnostics：

```text
schema_rich_keywords
```

Largest package：

```text
large_rest_synthetic
```

Hardest summaries to read：

```text
schema_rich_keywords
```

Generated examples that remain generic：

```text
small_reference_basic still uses generic required user_id example because the source fixture has no example/default.
```

Diagnostics that should become more precise：

```text
auth_rich_security and server_rich_choices have low scores because calibration intentionally includes metadata-rich warning cases. Future work can separate expected metadata warnings from user-actionable failures.
```

Next evidence-driven hardening gap：

```text
diagnostics score calibration and summary-noise review across real/cached specs.
```

## Validation

已通过：

```text
python -m py_compile scripts\api2agent_openapi_real_spec_calibration.py
```

已通过：

```text
pytest tests\test_openapi_real_spec_calibration.py tests\test_generators.py tests\test_cli.py
```

结果：

```text
61 passed
```

已通过：

```text
pytest
```

结果：

```text
210 passed
```

## Compatibility

Compatibility 已保留：

- generated package contracts unchanged
- calibration 复用 existing parser、generator、diagnostics、schema hint、response category 和 inspect-summary helpers
- 未新增 production CLI command 或 runtime behavior
- generated dogfood outputs 仍位于 `.dogfood`
- optional real-spec inputs absent 时不会让 main harness fail

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Closeout + Phase Review v0
```

Closeout 应判断这个 local calibration harness 是否足够 close，并判断下一项 compiler hardening target 是 diagnostics score calibration、summary-noise reduction、generic-example reduction，还是 cached real-spec corpus expansion。
