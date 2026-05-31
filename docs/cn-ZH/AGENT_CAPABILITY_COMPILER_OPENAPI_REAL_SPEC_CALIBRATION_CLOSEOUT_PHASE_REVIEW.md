# Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Real-Spec Calibration Harness implementation slice 可以关闭。

Compiler 现在有了一个 repeatable、offline evidence loop，可以比较 small、schema-rich、auth-rich、server-rich、write-heavy 和 large-surface OpenAPI packages。Harness 会输出 machine-readable artifact 和 concise review output，同时不改变 generated package contracts 或 production runtime behavior。

推荐下一项任务：

```text
Agent Capability Compiler Diagnostics Score Calibration Design v0
```

Calibration run 显示：metadata-rich packages 即使 warnings 是 expected and reviewable，也可能得到很低的 diagnostics score。下一项设计应区分 user-actionable risk 和 expected metadata richness，让 compiler 支持更多真实 specs 后 diagnostics 仍然有用。

## 现在已完成

### Design

已完成：

- documented why real-spec calibration follows keyword coverage
- defined purpose-labeled corpus slots
- defined metric contract and result artifact
- defined pass/warn/fail/skipped status behavior
- defined harness、manifest、artifact、tests、dogfood 和 non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_DESIGN.md`

### Implementation

已完成：

- `scripts/api2agent_openapi_real_spec_calibration.py`
- local default manifest with stable fixtures
- local synthetic large OpenAPI spec generation
- optional cached real-spec skip behavior
- package generation and metric extraction
- inspect-style excerpts and sample tool details
- first-call params capture
- status classification and recommendations
- `.dogfood/openapi-real-spec-calibration/result.json`
- regression tests for manifest coverage、path containment、status classification、optional skips、artifact contract 和 large-surface warnings
- dogfood run with 1 pass、5 warn、0 fail 和 1 skipped

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| calibration can run locally without network access | passed |
| result artifact is machine-readable | passed |
| default corpus includes small、schema-rich、auth-rich、server-rich、write-heavy 和 large-surface cases | passed |
| optional cached real-spec inputs skip cleanly when absent | passed |
| package metrics are comparable across cases | passed |
| oversized packages are visible | passed |
| diagnostics-heavy cases are visible | passed |
| inspect excerpts and sample tool details are captured | passed |
| first-call params are captured for a representative tool | passed |
| generated output paths are contained under the dogfood calibration directory | passed |
| full Python test suite passes | passed |
| 未新增 production runtime、provider execution、hosted service、workflow、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation | passed |

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

Local dogfood 已通过：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

观察到：

```text
OpenAPI real-spec calibration: 1 pass, 5 warn, 0 fail, 1 skipped
```

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Harness 给 compiler 带来了一个可用的 measurement loop。它刻意保持 local and report-oriented：不执行 providers，不强制 runtime validation，也不新增 production CLI/runtime behavior。它已经足够让未来 hardening decisions 变成 evidence-driven。

第一个有用信号已经出现：score calibration 需要处理。`auth_rich_security`、`server_rich_choices` 和 `schema_rich_keywords` 是有价值的 calibration cases，但它们的 diagnostics score 偏低，因为 expected metadata warnings 目前和 user-actionable risks 一样被计入 penalty。

## Remaining Risks

### Corpus Still Uses Mostly Fixtures

Default corpus 稳定且 offline，但还没有 committed cached real public spec。Optional case 让后续可以加入 cached real spec，同时不让 harness 依赖网络。

### Score Semantics Are Too Blunt

Diagnostics score 目前 uniform 地惩罚 warning 和 info volume。Metadata-rich but well-explained packages 可能分数过低。

### Summary Noise Needs Better Measurement

Harness 会捕获 excerpts，但还不会计算 summary-density score，也不会定位具体造成 readability issues 的 fields。

### Generic Examples Remain Visible

Harness 现在能暴露 generic first-call params，但减少它们需要单独的 examples/defaults calibration pass。

### Calibration Is Report-Oriented

Harness 还不是 CI gate。这是有意选择，直到 score semantics 和 corpus composition 稳定。

## 推荐下一项任务

```text
Agent Capability Compiler Diagnostics Score Calibration Design v0
```

该设计应使用 calibration harness output 区分 expected metadata-rich findings 和 user-actionable risks，细化 score penalties，并定义 tests，确保 diagnostics 有用但不会隐藏真实 failures。
