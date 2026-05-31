# Agent Capability Compiler OpenAPI Summary Noise Reduction Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Summary Noise Reduction implementation slice 可以关闭。

Default human-facing package output 现在更 compact，同时没有降低 raw data fidelity。`inspect` 会 fold dense aggregate summaries、clip long detail previews，并选择 representative response summaries。`diagnose` 会在 text output 中 group repeated findings，同时保留 full JSON。Generated README 现在包含带 diagnostics 和 key caveats 的 Package Overview。Calibration harness 会记录 summary-density metrics，方便后续发现 regressions。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Design v0
```

下一个 evidence-driven gap 是 generic first-call examples。Calibration harness 仍显示 `small_reference_basic` 使用 `user_id: "example"`，原因是 source fixture 缺少 examples/defaults。现在 score 和 summary readability 的噪声都降低了，提高 deterministic first-call params 是最高杠杆的 compiler hardening target。

## 现在已完成

### Design

已完成：

- defined summary noise taxonomy
- defined bounded summary budgets
- defined risk-first rendering order
- defined repeated finding folding
- defined README、inspect、diagnostics text 和 calibration harness effects
- defined summary-density metrics
- defined tests、dogfood expectations、compatibility strategy 和 non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_DESIGN.md`

### Implementation

已完成：

- compact inspect aggregate rendering
- high-signal schema hint prioritization
- representative inspect response previews
- long detail line clipping
- grouped diagnostics text output
- README Package Overview and key caveats
- calibration summary-density metrics
- CLI、diagnostics、README generation 和 calibration harness 的 regression tests
- dogfood run with 4 pass、2 warn、0 fail 和 1 skipped

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| raw package contracts remain unchanged | passed |
| raw diagnostics JSON remains full-fidelity | passed |
| `api2agent inspect --json` remains full-fidelity | passed |
| `api2agent diagnose --json` remains full-fidelity | passed |
| default inspect output folds dense aggregate summaries | passed |
| default inspect output clips long detail previews | passed |
| default inspect output selects representative response previews | passed |
| default diagnostics text groups repeated finding ids | passed |
| README includes Package Overview and key caveats | passed |
| calibration artifact includes summary-density metrics | passed |
| real-spec calibration remains 4 pass、2 warn、0 fail、1 skipped | passed |
| full Python test suite passes | passed |
| 未新增 production runtime、provider execution、hosted service、workflow、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation | passed |

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

Local dogfood 已通过：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

观察到：

```text
OpenAPI real-spec calibration: 4 pass, 2 warn, 0 fail, 1 skipped
```

已通过：

```text
python -m pytest -q
```

结果：

```text
213 passed
```

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

v0 summary budgets 对当前 corpus 已足够。最明显的 schema-rich long-line issue 已受控，repeated diagnostics 已在 text output 中 group，README 也会先展示 package-level overview 再进入 detailed tool notes。剩余的 repeated diagnostic group recommendations 应保持 advisory，因为它们对后续 fixture 和 real-spec review 有用，但不是 implementation failures。

## Remaining Risks

### Full Text Output Still Has Opinionated Budgets

Defaults 有意保持 compact，但未来用户可能需要正式的 `--verbose` 或 `--detail full` mode，用于 non-JSON full text output。

### README Tool Sections Can Still Be Large

README 为 compatibility and review 继续保留 tool-level details。Large packages 仍应依靠 filtering guidance，而不是全面压缩 README。

### Repeated Diagnostic Groups Remain Advisory

Calibration harness 会报告 repeated finding groups，帮助 reviewers 发现 noisy packages。在 corpus 更大之前，这些不应变成 strict failures。

### Generic First-Call Params Remain

当 source specs 缺少 examples/defaults 时，harness 仍会显示 generic examples for required fields。这比剩余 summary noise 更直接影响 first-call quality。

### Corpus Is Still Mostly Fixtures

当前 offline corpus 稳定，但更广泛信心仍需要 cached real public spec 或 curated corpus expansion。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Generic Example Reduction Design v0
```

该设计应使用 calibration `first_call_params`、existing schema keyword hints、parameter names、formats、enums、defaults 和 examples，减少 `"example"` 这类 generic values，同时不引入 LLM generation、runtime validation、provider calls 或 new non-API inputs。
