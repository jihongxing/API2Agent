# Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion implementation slice 可以关闭。

Compiler 现在已经在默认 calibration corpus 中拥有一个 committed offline cached real-spec case，并带有 source metadata、checksum verification、redaction/cache policy evidence、path containment checks、additive calibration result fields、regression tests 和 dogfood evidence。这对 v0 已足够。更多 cached public specs 应留到最终 Agent Capability Compiler consolidation review 之后再决定，避免项目在关闭 compiler re-entry phase 前漂移成 corpus collection。

推荐下一项任务：

```text
Agent Capability Compiler Final Re-entry Closeout + Consolidation Review v0
```

最终 review 应判断 Agent Capability Compiler 是否可以以 99%+ 完成度退出当前 re-entry phase、剩余风险是什么，以及项目应回到暂停的 hosted Control Plane backlog，还是处理最后一个 compiler gap。

## 现在已完成

### Design

已完成：

- defined cached real-spec source criteria
- defined license/cache metadata requirements
- defined redaction policy
- defined artifact layout
- defined manifest changes
- defined calibration metrics and status thresholds
- defined implementation、tests、dogfood expectations 和 non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_DESIGN.md`

### Implementation

已完成：

- `CalibrationCase` 支持 cached source metadata
- required cached cases 的 metadata validation
- SHA-256 checksum verification
- cached source and metadata path containment checks
- calibration `result.json` 中的 additive cached-source fields
- committed Apache-2.0 Swagger Petstore excerpt and metadata
- optional user-provided cached spec compatibility
- metadata success、checksum mismatch、missing metadata、path containment、optional skips 和 manifest inclusion 的 regression coverage
- dogfood run with 5 pass、2 warn、0 fail 和 1 skipped

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| cached real-spec corpus policy is implemented | passed |
| at least one committed cached real/public-spec case has source metadata | passed |
| normal calibration remains offline and deterministic | passed |
| required cached cases validate checksum, metadata, and path containment | passed |
| optional cached cases still skip cleanly when absent | passed |
| result artifact includes safe source/cache metadata | passed |
| calibration recommendations include cached real-spec issues when present | passed |
| targeted and full test suites pass | passed |
| 未新增 LLM generation、provider execution、network-dependent tests、hosted service、workflow、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation | passed |

## Validation

已通过：

```text
python -m py_compile scripts\api2agent_openapi_real_spec_calibration.py
```

已通过：

```text
python -m pytest tests\test_openapi_real_spec_calibration.py tests\test_generators.py tests\test_cli.py tests\test_diagnostics.py -q
```

结果：

```text
82 passed
```

已通过：

```text
python -m pytest -q
```

结果：

```text
221 passed
```

Local dogfood 已通过：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

观察到：

```text
OpenAPI real-spec calibration: 5 pass, 2 warn, 0 fail, 1 skipped
```

已通过：

```text
git diff --cached --check
```

## Closeout Judgment

这个 implementation slice 已完成。

一个 required cached real-spec case 对 v0 已足够，因为它在不改变项目边界的前提下增加了真实 public OpenAPI shape。Cached Petstore case 覆盖 mixed read/write/delete tools、request bodies、server metadata、`allOf` response schema shaping、default responses 和 real-world operation naming。它以 `tool_count=4`、`diagnostics_score=82` 和 `generic_example_count=0` 通过 calibration。

未来继续加入更多 cached specs 会有价值，但现在继续加会让最终 compiler phase 变成 corpus harvesting。正确下一步是 consolidation：复盘整个 compiler chain，判断剩余风险是否可接受，并做明确 handoff decision。

## Remaining Risks

### Corpus Is Broader, But Still Small

Corpus 现在包含一个 committed real public spec，但 required cached case 仍只有一个。这足以支撑 v0 confidence expansion，但不是 comprehensive public API benchmark。

### Cached Spec Is A Curated Excerpt

Petstore cache 是有意 reduced and redacted 的。它是真实 public material，但不证明 very large production specs 上的行为。

### Repeated Finding Groups Remain Advisory

Cached Petstore case 会把 repeated diagnostic groups 加入 recommendation list。这是有用的 review signal，不是 failure。

### Write/Delete Presence Still Needs Human Review

Cached case 包含 write/delete tools，但同时也有 read tools，因此通过。Operators 在执行 write/delete tools 前仍需 explicit review。

### Final Consolidation Is Still Needed

Compiler 已累积很多 hardening slices。最终 re-entry closeout 应确认 docs、tests、calibration signals 和 next-project direction 已对齐。

## Phase Review

Agent Capability Compiler 完成度估计：

```text
99%
```

剩余 1% 是 final consolidation，而不是已知实现洞。Compiler 现在已有 core OpenAPI semantics、diagnostics、examples、summaries、calibration，以及一个进入默认 evidence loop 的 cached real public spec。

## 推荐下一项任务

```text
Agent Capability Compiler Final Re-entry Closeout + Consolidation Review v0
```

该 review 应总结完整 Agent Capability Compiler re-entry、列出 residual risks、判断 compiler 是否可以 pause，并命名下一条 project lane。
