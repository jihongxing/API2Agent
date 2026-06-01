# Agent Capability Compiler OpenAPI Generic Example Reduction Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Generic Example Reduction implementation slice 可以关闭。

Generated sample params 现在会在 source examples、defaults、enums、consts、formats 和 schema constraints 之后，使用 deterministic name-aware fallbacks。结果是 README snippets、smoke tests、manual write tests 和 calibration artifacts 的 first-call quality 更好，同时保持 raw OpenAPI package contracts 和 runtime behavior 不变。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Design v0
```

现在最大的 compiler 风险是 corpus breadth。默认 calibration set 在 generic examples 上已经 clean，diagnostics score 已校准，summary 也足够可读；但它仍然主要依赖 fixtures 加 synthetic large spec。下一项设计应定义如何加入 committed cached real public OpenAPI spec 或 curated local real-spec corpus，同时不引入 network dependency、provider execution、hosted runtime work 或 licensing/legal ambiguity。

## 现在已完成

### Design

已完成：

- defined deterministic name-aware fallback rules
- preserved explicit source/schema priority
- defined object property name threading
- defined conservative numeric and boolean name hints
- defined calibration generic example metrics
- defined tests、dogfood expectations、compatibility strategy 和 non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_DESIGN.md`

### Implementation

已完成：

- `example_value` 增加 optional `name` context
- `example_for_parameter` 支持 parameter name-aware examples
- request bodies 的 object properties 支持 property-name-aware examples
- secret-safe placeholders，例如 `REPLACE_ME`
- semantic deterministic fallbacks，例如 `user_123`、`Demo`、`active`、`USD` 和 `cursor_123`
- conservative numeric fallbacks，例如 `limit=10`、`page=1` 和 `offset=0`
- calibration `generic_example_count`
- calibration `generic_first_call_params`
- source/schema priority、generated packages 和 calibration metrics 的 regression coverage
- dogfood run with 4 pass、2 warn、0 fail 和 1 skipped

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| name-aware example fallback is implemented | passed |
| source examples/defaults/enums/consts still win | passed |
| schema formats and constraints still win over name rules | passed |
| object properties receive property-name context | passed |
| secret-like names use safe placeholders | passed |
| numeric name hints stay conservative | passed |
| generic first-call params decrease in calibration output | passed |
| default generated calibration cases report zero generic examples | passed |
| generated README/smoke/manual examples remain deterministic | passed |
| calibration artifact records generic example metrics | passed |
| targeted and full Python test suites pass | passed |
| 未新增 LLM generation、provider execution、runtime validation、hosted service、workflow、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation | passed |

## Validation

已通过：

```text
python -m py_compile api2agent\generators\examples.py scripts\api2agent_openapi_real_spec_calibration.py
```

已通过：

```text
python -m pytest tests\test_examples.py tests\test_generators.py tests\test_openapi_real_spec_calibration.py tests\test_cli.py tests\test_diagnostics.py -q
```

结果：

```text
82 passed
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
217 passed
```

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

原始的具体 gap 已关闭：`small_reference_basic.first_call_params.params.user_id` 现在是 `user_123`，不再是 `"example"`。Format-aware behavior 仍保持完好，证据是 `schema_rich_keywords.first_call_params.params.user_id` 仍然是 UUID-shaped value。默认生成的 calibration cases 现在都报告 `generic_example_count = 0`，且 `generic_first_call_params` 为空。

Fallback 仍然刻意保持 fake、deterministic 和 local。它改善 reviewability 和 first-call ergonomics，但不声称 provider validity，也不发现真实 IDs/secrets。

## Remaining Risks

### Corpus Breadth Is Still The Largest Gap

Calibration corpus 稳定且有用，但仍主要是 fixtures 加 synthetic large spec。Cached real public spec 现在是发现剩余 compiler gaps 的最高信号方式。

### Name Rules Are Bounded Heuristics

Fallback rules 覆盖常见 API names，但它们不是 semantic understanding。未知名称按设计仍回退到 type-level defaults。

### Example Quality Is Advisory

Generated examples 帮助 README、tests 和 calibration first-call params。Runtime validation 和 provider-specific validity 仍然 out of scope。

### Write-Heavy Packages Still Need Human Review

`write_heavy_unsafe` 仍保持 warning，因为 write/delete-only generated packages 无论 examples 是否更好，都需要 explicit operator review。

### Large Package Filtering Remains Important

`large_rest_synthetic` 仍保持 warning，因为超过 50 个 tools 的 package 仍应在 Agent 使用前被收窄。

## Phase Review

Agent Capability Compiler 完成度估计：

```text
98%
```

Compiler 现在已经关闭核心 OpenAPI hardening chain：diagnostics、examples/defaults、security combinations、server handling、schema shaping、discriminator handling、response documentation、bounded JSON Schema keyword coverage、real-spec calibration、score calibration、summary noise reduction 和 generic example reduction。

剩余 2% 不是某个已知实现 bug，而是 confidence work：更广的 real-spec calibration、最后的 corpus-backed review，以及决定 Agent Capability Compiler 是否可以退出这次 re-entry phase 的最终 consolidation pass。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Design v0
```

该设计应定义 source criteria、licensing/cache policy、artifact location、calibration manifest changes、redaction rules、expected metrics 和 pass/warn thresholds，用于加入一个或多个 cached real specs，同时保持 harness offline and deterministic。
