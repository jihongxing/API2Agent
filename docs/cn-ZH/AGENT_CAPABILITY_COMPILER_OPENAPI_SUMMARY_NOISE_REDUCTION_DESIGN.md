# Agent Capability Compiler OpenAPI Summary Noise Reduction Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 Agent Capability Compiler implementation slice 应为：

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Implementation v0
```

这个 slice 应通过 bounded summary budgets、repeated-finding folding 和 risk-first prioritization，让 metadata-rich OpenAPI packages 生成的 README 和 `api2agent inspect` output 更易扫描。实现应保留 raw capability data、diagnostics data 和 full JSON output，同时让默认 human-facing summaries 足够紧凑，适合反复使用。

## 为什么现在做这个 Slice

Real-spec calibration harness 和 diagnostics score calibration 改变了证据图：

- metadata-rich schema/auth/server cases 现在已高于 false-low threshold
- write-heavy 和 large-surface packages 仍保持 visible warnings
- 下一个 user-facing friction 不再是 numeric score，而是 summary density

当前 output 能力更强，但也更 noisy：

- `inspect` 会输出 aggregate schema hint counts、response categories、diagnostics，然后按 visible tool 展开 parameters/body/responses
- README 会为每个 tool 输出 auth、parameters、body 和 response summaries
- schema-rich response summaries 可能把 large object shapes 展开成很长的一行
- `success_response_without_schema` 这类 repeated warnings 可能主导 diagnostics detail
- large packages 已有 tool list truncation，但 compact packages with rich schemas 仍可能难以扫描

Compiler 现在应该保留 metadata，但用更清晰的阅读顺序呈现。

## Current Baseline

已有能力：

- `api2agent inspect --json` exposes full raw capability JSON
- `api2agent diagnose --json` exposes full raw diagnostics JSON
- default inspect output summarizes auth、servers、safety counts、top tags、path prefixes、schema hints、response categories、diagnostics 和 tool details
- README 包含 auth、provider region、base URL override、tools、smoke test、runner 和 proxy sections
- response shape documentation、schema keyword summaries、discriminator summaries、server metadata 和 diagnostics 都已可见
- large tool lists 可以通过 `--limit` / `--all` 截断或展开

重要缺口：

- default human output 没有 shared summary budget
- rendered summaries 不区分 high-risk caveats 和 expected metadata notes
- repeated per-operation findings 没有在 text output 中 folded
- schema hint counts 会作为一条 dense line 输出
- long schema summaries 会让单条 response/body line 难读
- README 在 per-tool detail 之前没有 compact package-level tool overview
- calibration harness 会捕获 excerpts，但还不测量 summary density 或 repeated output patterns

## Goals

- 让 default README 和 inspect output 更 scan-friendly
- 通过 existing JSON outputs 和 generated artifacts 保留 full data
- 优先呈现 safety、auth、server、required input 和 response caveats
- fold repeated diagnostics 和 repeated response/schema notes
- bound line length and per-tool detail volume
- 保持 deterministic offline generation
- 不隐藏重要风险
- 增加 tests 锁定 compact summaries，避免过度绑定完整文案
- 扩展 calibration evidence，用于跟踪 summary density regressions

## Non-Goals

不实现：

- parser behavior changes
- new OpenAPI schema semantics
- runtime request or response validation
- LLM-based summarization
- generated SDK types
- UI/browser report rendering
- provider execution
- hosted diagnostics service
- workflow runtime
- marketplace/provider onboarding
- vault、billing、public CRUD、production gateway permission source 或 automatic propagation

## Noise Taxonomy

### Repeated Diagnostic Noise

示例：

- `weak_tool_description` repeated once per operation
- `success_response_without_schema` repeated once per operation
- repeated metadata findings for response schemas or keyword visibility

Default text output 应按 finding id group，并展示 count 加一个 representative recommendation。Full diagnostics JSON 不变。

### Dense Aggregate Noise

示例：

- schema hint counts with many keys
- response categories plus schema hints plus top tags all emitted as long lines

Default output 应优先显示 highest-signal keys，超过小预算时使用 `+N more`。

### Long Shape Noise

示例：

- response object summaries with many properties
- request body summaries combining keyword markers、nullable markers、read/write markers 和 object fields

Default output 应保留 compact preview，并指向 full JSON 或 verbose mode 查看完整细节。

### Repeated Tool-Detail Noise

示例：

- many tools with the same response caveat
- many tools with no required params and no response schema

Default output 应为每个 visible tool 显示 representative details，并在 package-level aggregate repeated caveats。

## Output Model

引入小型 rendering profile：

```text
api2agent.summary_profile.v0
```

这个 profile 只用于 human-facing text，不改变 `capability.json`、`diagnostics.json`、runner behavior、generated MCP schemas 或 parser output。

建议 helper shape：

```text
summarize_package_for_text(capability_json, diagnostics, profile) -> SummaryView
format_summary_view(view, target="inspect" | "readme") -> list[str]
```

v0 可以先作为 `api2agent.cli` 和 `api2agent.generators.readme` 中的 local helpers；如果 duplication 真实出现，再移到 shared module。

## Rendering Rules

### Risk First

Default output order：

1. package identity and execution basics
2. diagnostics status/score
3. blocking/action-required caveats
4. auth/server/runtime targeting notes
5. tool count and safety distribution
6. schema/response metadata summary
7. compact tool list

### Bounded Aggregate Lists

对 schema hints、top tags、path prefixes、response categories 和 repeated findings：

- 默认最多显示 5 keys
- 按 signal priority、count、name 排序
- omitted 时追加 `+N more`
- full values 继续保留在 JSON output

### Bounded Tool Details

对 default inspect output 中每个 visible tool：

- 保留 method/path/safety/required one-line summary
- 最多显示 3 detail lines
- 优先显示 required path/query/header params 和 required request body
- 只有有用时显示 response category/schema preview
- excess responses folded as `responses: 2 shown, 4 total`
- 保留 `--all` 用于展开 tool count

Implementation 可以增加 `--verbose` 或 `--detail full` option 打印旧的 full detail format；但 v0 无论如何都应保留 `--json` 作为 compatibility escape hatch。

### README Structure

README 应在 detailed tool notes 之前增加 package-level compact overview：

```text
## Package Overview

- Tools: 5
- Safety: read=5
- Diagnostics: warn score=62
- Key caveats: success_response_without_schema(5), weak_tool_description(5)
```

Tool detail 继续保留，但 repeated response/schema caveats 应尽量在 package level grouped。

### Diagnostics Text Formatting

`api2agent diagnose` text output 应 group repeated finding ids：

```text
- [warning] success_response_without_schema x5: Success response has no documented schema.
  recommendation: Add a success response schema so generated docs can show Agents what a successful call returns.
```

JSON output 仍保持 one finding per occurrence。

## Summary Budgets

建议 v0 budgets：

| Surface | Budget |
| --- | --- |
| inspect header before tools | 10 lines |
| aggregate list keys | 5 |
| visible tools default | existing `--limit` |
| per-tool detail lines | 3 |
| response summaries per tool | 2 |
| README package overview caveats | 5 |
| README per-tool response summaries | 2 |
| schema summary preview length | reuse existing schema summarizer bounds, add final line clipping only if needed |

这些是 defaults，不是 public protocol guarantees。

## Calibration Harness Effects

扩展 local calibration artifact，加入 summary-density metrics：

```text
inspect_line_count
sample_tool_detail_line_count
max_inspect_line_chars
readme_tool_section_lines
repeated_finding_groups
```

v0 中 status classification 应保持 conservative。出现以下情况时增加 recommendations：

- inspect excerpt has very long lines
- sample tool details exceed the default detail budget
- README size grows unexpectedly
- repeated finding groups dominate diagnostics

## Test Plan

新增或更新 tests：

- inspect output folds long schema hint lists
- inspect output caps per-tool response details while preserving required inputs
- inspect has a verbose/full escape hatch or JSON compatibility path
- README includes package overview before tool detail
- README groups repeated caveats
- diagnostics text groups repeated finding ids
- calibration harness captures summary-density metrics
- large package truncation behavior still works
- schema/auth/server/response/discriminator/keyword fixtures still expose high-signal caveats

优先 assert stable markers and counts，不绑定完整段落。

## Dogfood Plan

运行：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Implementation 后预期：

- no calibration case should fail solely from summary rendering changes
- `schema_rich_keywords` inspect excerpt should avoid very long schema hint lines
- repeated diagnostics in `auth_rich_security` should group clearly in text output
- `large_rest_synthetic` should still warn for `tool_count > 50`
- `write_heavy_unsafe` should still warn for write/delete-only behavior

## Compatibility Strategy

通过保留以下内容维持 compatibility：

- raw `capability.json`
- raw `diagnostics.json`
- `api2agent inspect --json`
- `api2agent diagnose --json`
- generated runner behavior
- generated MCP tool schemas
- existing diagnostics contract fields

Text output 是 human-facing，可以变得更 compact；但 tests 应保护重要 labels，避免读取 broad markers 的 scripts 不必要地 broken。

## Acceptance Criteria

- summary noise reduction design is implemented without changing raw package contracts
- default inspect output is shorter and still exposes safety/auth/server/schema/response risks
- default diagnostics text groups repeated finding ids
- README has a compact package overview
- repeated response/schema caveats are folded or grouped
- JSON outputs remain full-fidelity
- calibration artifact includes summary-density metrics
- targeted and full test suites pass
- 未新增 production runtime、provider execution、hosted service、workflow、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Implementation v0
```
