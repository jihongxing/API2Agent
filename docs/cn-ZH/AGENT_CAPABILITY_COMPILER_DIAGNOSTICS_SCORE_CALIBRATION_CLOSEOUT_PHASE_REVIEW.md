# Agent Capability Compiler Diagnostics Score Calibration Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler Diagnostics Score Calibration implementation slice 可以关闭。

Diagnostics scoring 现在能区分 expected metadata visibility 和 user-actionable risk，同时保持 existing diagnostics status semantics。校准后的 profile 让 real-spec harness output 更可信：metadata-rich schema/auth/server cases 不再因为 compiler 更透明就看起来像 broken package，而 write-heavy 和 large-surface cases 仍保持 visible warnings。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Design v0
```

Score calibration 已经修复 false-low score signal。下一个 evidence-driven gap 是 readability density：generated README、inspect output 和 diagnostic excerpts 现在暴露了大量有用 metadata，但 complex OpenAPI specs 仍需要更好的 grouping 和 prioritization，让 humans 和 Agents 能更快扫描 generated package。

## 现在已完成

### Design

已完成：

- documented the scoring weakness found by real-spec calibration
- defined compatibility strategy for additive diagnostics fields
- defined impact classes and initial finding mappings
- defined metadata penalty capping
- defined `scoring_profile` 和 `score_breakdown`
- defined tests and dogfood expectations
- parser behavior、runtime validation、provider execution、hosted diagnostics、workflow、marketplace、vault、billing、public CRUD、gateway permission source 和 automatic propagation 均保持 out of scope

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_DESIGN.md`

### Implementation

已完成：

- `api2agent/diagnostics.py` 中的 impact-based scoring
- `api2agent.diagnostics.score_profile.v0`
- top-level `scoring_profile`
- top-level `score_breakdown`
- metadata review penalty cap
- repeated action-finding penalty cap
- zero-penalty readiness findings
- severity-based `status` compatibility
- score breakdown shape、metadata-rich fixture scores、blocking findings 和 write-heavy unsafe packages 的 regression tests
- dogfood run 将 OpenAPI real-spec calibration 从 1 pass / 5 warn 改善为 4 pass / 2 warn

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| existing diagnostics JSON fields remain present | passed |
| `status` remains severity-based | passed |
| `score` is recalibrated from finding impact/actionability | passed |
| `scoring_profile` is exposed | passed |
| `score_breakdown` explains base, penalties, score, impact counts, and finding impacts | passed |
| readiness findings do not reduce score | passed |
| metadata-rich schema/auth/server cases score above the calibration threshold | passed |
| write-heavy unsafe package remains below the calibration score threshold | passed |
| blocking diagnostics still produce fail status and low score | passed |
| real-spec calibration harness output improves without hiding large-surface warnings | passed |
| full Python test suite passes | passed |
| 未新增 production runtime、provider execution、hosted service、workflow、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation | passed |

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
212 passed
```

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Calibrated score profile 对 v0 已足够，因为它保持 compatibility，提供 machine-readable score explanation，并让 calibration output 与 package 的实际 usability risk 更一致。同时 true risk cases 仍然可见：write-only packages、large toolsets、missing base URLs、duplicate tool names，以及 required bodies without schemas 都仍会产生强信号。

最重要的产品变化是：diagnostics 现在可以保持透明，而不会让 valid metadata-rich packages 看起来不可用。

## Remaining Risks

### Action Penalty Cap Needs More Real Specs

Repeated action-finding cap 是基于当前 fixture corpus 校准的。加入 committed cached real public spec 后需要重新检查。

### Score Is Still Heuristic

Score 是 deterministic and explainable，但不是 runtime success predictor。它应继续作为 advisory package readiness signal。

### Summary Noise Is Now More Visible

False-low scores 降低后，下一个 user-facing friction 是 generated summaries、inspect output、README sections 和 diagnostics excerpts 中 metadata 的信息密度。

### Generic Examples Still Need Separate Work

Calibration harness 仍会在 source specs 缺少 examples/defaults 时暴露 generic first-call params。减少这个问题需要单独的 examples/defaults 或 sample synthesis pass。

### Corpus Is Still Mostly Local Fixtures

Offline corpus 稳定，但要获得更广泛信心，还需要 checked-in cached real public spec 或 curated local corpus expansion。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Design v0
```

该设计应使用 calibration harness 和 diagnostics score breakdown，决定 generated README、inspect output 和 diagnostic excerpts 如何 group、prioritize 和 suppress repetitive metadata，同时不隐藏 safety、auth、server、response 或 schema caveats。
