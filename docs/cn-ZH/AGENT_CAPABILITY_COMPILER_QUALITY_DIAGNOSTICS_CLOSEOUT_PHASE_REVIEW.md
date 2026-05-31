# Agent Capability Compiler Quality Diagnostics Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler Quality Diagnostics implementation slice 可以关闭。

Compiler 现在可以在 generated OpenAPI 和 curl capability packages 接入 Agent 或 proxy execution 之前，给开发者 deterministic quality signal。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Real-World Hardening Design v0
```

下一项设计应把 diagnostics 作为 measurement layer，同时改进真实 OpenAPI specs 的处理。它必须保持 API-first，不得增加 workflow execution、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## 现在已完成

### Design

已完成：

- 选择 quality diagnostics 作为第一项 compiler expansion slice
- target generate/diagnose/inspect workflows
- additive `diagnostics.json` contract
- initial finding set
- scoring heuristic
- tests and dogfood requirements
- 保持 API-first boundaries 的 non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`

### Implementation

已完成：

- `api2agent.diagnostics` pure IR diagnostics engine
- generated package `diagnostics.json`
- generation-time diagnostics summary
- generated README diagnostics section
- `api2agent inspect` diagnostics summary
- `api2agent diagnose <package_dir>`
- `api2agent diagnose <package_dir> --json`
- 对没有 `diagnostics.json` 的旧 packages 重新计算 diagnostics
- deterministic tests 覆盖 usability、safety、auth、schema、execution 和 observability findings

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| generated packages include additive `diagnostics.json` | passed |
| diagnostics can be recomputed from `capability.json` | passed |
| CLI exposes human-readable diagnostics | passed |
| CLI exposes JSON diagnostics contract | passed |
| generation prints compact diagnostics summary | passed |
| generated README includes diagnostics summary | passed |
| inspect remains compatible with old packages | passed |
| diagnostics do not block generation by default | passed |
| findings cover Agent usability risks | passed |
| findings cover safety risks | passed |
| findings cover auth/credential risks | passed |
| findings cover schema/input risks | passed |
| findings cover execution/observability risks | passed |
| tests cover deterministic findings and CLI behavior | passed |
| 未增加 workflow、marketplace、vault、billing、hosted public CRUD、gateway permission source 或 automatic propagation | passed |

## Validation

已通过：

```text
python -m py_compile api2agent\diagnostics.py api2agent\cli.py api2agent\generators\package.py api2agent\generators\readme.py
```

已通过：

```text
pytest tests\test_diagnostics.py tests\test_generators.py tests\test_cli.py
```

结果：

```text
52 passed
```

已通过：

```text
pytest
```

结果：

```text
177 passed
```

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Quality diagnostics 现在给 API2Agent 一个可复用的 compiler expansion feedback layer：

- developers 会得到具体 findings，而不是 silent package generation
- large 或 vague packages 可以在 Agent wiring 前被标记
- write-only packages 会在 unsafe testing 前被提示
- auth/schema/observability issues 变成 deterministic testable outputs
- generated package compatibility 保持不变

这为下一阶段 compiler expansion 打好了基础。

## Remaining Risks

### Findings Need Calibration Against More Real Specs

当前 dogfood 覆盖 fixtures 和 local curl examples。更大的真实 OpenAPI specs 可能暴露 noisy findings、缺失 finding categories 或 score calibration issues。

### Diagnostics Are Advisory

Warnings 默认不阻塞 generation。这对 v0 是正确的，但未来 CI-style enforcement 可能需要 `--fail-on warning|error`。

### Schema Quality Is Still Shallow

Diagnostics 可以标记 broad 或 missing schemas，但还没有改进 nested schema shaping、enum/example propagation 或 Agent-facing input simplification。

### OpenAPI Complexity Remains The Next Big Compiler Gap

Multiple servers、security combinations、nested request bodies、examples/defaults 和 filtering diagnostics 仍需要更深设计。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Real-World Hardening Design v0
```

该设计应定义 diagnostics、OpenAPI parsing、package generation、tests 和 dogfood 如何协同改善 real-world OpenAPI onboarding，同时不把 API2Agent 扩展成 workflow runtime 或 hosted product scope。
