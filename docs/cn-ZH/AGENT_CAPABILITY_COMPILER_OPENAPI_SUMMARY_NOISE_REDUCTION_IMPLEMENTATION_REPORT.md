# Agent Capability Compiler OpenAPI Summary Noise Reduction Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent Capability Compiler 已实现 OpenAPI summary noise reduction v0。

实现保持 raw package 和 diagnostics contracts 不变，同时让默认 human-facing output 更容易扫描。`inspect` 现在会 fold dense aggregate lists、clip 很长的 detail previews，并限制 response previews。`diagnose` text output 会 group repeated findings。Generated README 增加 compact Package Overview，包含 tool count、safety distribution、diagnostics status/score 和 key caveats。Real-spec calibration harness 现在会记录 summary-density metrics。

已实现：

- inspect schema hints 和 response categories 的 bounded aggregate rendering
- inspect tool details 中的 response preview selection and folding
- long inspect detail previews 的 line clipping
- diagnostics text output 的 repeated finding grouping
- README `Package Overview`
- README key caveat grouping
- calibration summary-density metrics
- long inspect lines 和 repeated finding groups 的 calibration recommendations
- compact inspect output、grouped diagnostics text、README overview 和 calibration metrics 的 regression coverage

本 slice 未新增 parser behavior、OpenAPI schema semantics、runtime validation、LLM summarization、provider execution、hosted diagnostics、workflow runtime、marketplace/provider onboarding、vault、billing、public CRUD、production gateway permission source 或 automatic propagation。

## Files

Implementation：

- `api2agent/cli.py`
- `api2agent/diagnostics.py`
- `api2agent/generators/readme.py`
- `scripts/api2agent_openapi_real_spec_calibration.py`

Tests：

- `tests/test_cli.py`
- `tests/test_diagnostics.py`
- `tests/test_generators.py`
- `tests/test_openapi_real_spec_calibration.py`

Design reference：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_DESIGN.md`

## Behavior Changes

### Inspect

Default `api2agent inspect` output 现在会：

- limit aggregate count lists 并追加 `+N more`
- prioritize high-signal schema hint keys
- select representative response summaries，而不是输出每个 response
- clip long detail lines 到 bounded preview length
- 通过 `--json` 保留 full raw capability output

### Diagnostics Text

Default `api2agent diagnose` text output 现在会 group repeated finding ids：

```text
- [warning] success_response_without_schema x5: Success response has no documented schema.
```

Diagnostics JSON 仍然保持 one finding per occurrence。

### README

Generated README 现在包含：

```text
## Package Overview

- Tools: 5
- Safety: read=5
- Diagnostics: warn score=62
- Key caveats: success_response_without_schema(5), weak_tool_description(5)
```

Tool-level README details 继续保留，方便 compatibility and review。

### Calibration Harness

Calibration artifact 现在包含：

```text
inspect_line_count
sample_tool_detail_line_count
max_inspect_line_chars
readme_tool_section_lines
repeated_finding_groups
```

这些 metrics 让后续 hardening work 可以跟踪 summary-density regressions，而不把 harness 变成 strict CI gate。

## Dogfood Evidence

运行：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

观察到：

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

Implementation 后的 summary-density review：

```text
small_reference_basic max_inspect_line_chars=41
schema_rich_keywords max_inspect_line_chars=180
auth_rich_security max_inspect_line_chars=41
server_rich_choices max_inspect_line_chars=41
write_heavy_unsafe max_inspect_line_chars=41
large_rest_synthetic max_inspect_line_chars=85
```

Compact schema hint formatting 和 detail clipping 后，之前 schema-rich long-line recommendation 已消失。剩余 recommendations 都是预期信号：large-surface filtering、write-heavy low score，以及需要 review 的 repeated diagnostic groups。

## Validation

已通过：

```text
python -m py_compile api2agent\diagnostics.py api2agent\cli.py api2agent\generators\readme.py scripts\api2agent_openapi_real_spec_calibration.py
```

已通过：

```text
python -m pytest tests\test_diagnostics.py tests\test_cli.py tests\test_generators.py tests\test_openapi_real_spec_calibration.py -q
```

结果：

```text
78 passed
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
213 passed
```

## Compatibility

Compatibility 已保留：

- raw `capability.json` unchanged
- raw `diagnostics.json` remains full-fidelity
- `api2agent inspect --json` 仍打印 full capability JSON
- `api2agent diagnose --json` 仍打印 full diagnostics JSON
- generated runner behavior unchanged
- generated MCP tool schemas unchanged
- diagnostics contract fields remain present

Default text output 有意变得更 compact。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Closeout + Phase Review v0
```

Closeout 应判断 v0 summary budgets 是否足够、repeated diagnostic group recommendations 是否继续保持 advisory，以及下一项 compiler hardening target 是 generic-example reduction、cached real-spec corpus expansion，还是另一个 summary-quality slice。
