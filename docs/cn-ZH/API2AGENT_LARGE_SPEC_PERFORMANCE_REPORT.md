# API2Agent Large Spec Performance 报告 v0

日期：2026-05-31

状态：已完成

## 总结

API2Agent 现在对 large OpenAPI specs 有了更强的 scale control 和 developer guidance。

这个 slice 面向 GitHub REST 这类单个 OpenAPI document 可能生成 1000+ tools 的 API。目标不是隐藏风险，而是让 package 可理解、在需要时可收窄、并且不改 generated source 也能测试指定 tool。

范围保持克制：

- API-first only
- 只涉及 OpenAPI generation、inspection 和 generated-package test usability
- 不做 workflow engine
- 不做 marketplace 或 billing
- 不改 hosted control-plane

## 改动

### Parse-time Filtering

OpenAPI filters 现在会在 parsing 阶段应用：

- `--include-tag`
- `--include-path`
- `--include-operation`
- `--max-tools`

这避免先构建所有 tools 再过滤，对 large specs 很重要。像 `--max-tools 5` 这种 bounded generation 也不再为了决定是否 warning 而额外做一次完整 operation count。

### Large Package Inspect Summary

`api2agent inspect` 现在会在列出 tools 前输出紧凑 summary：

```text
Tool count: 1200
Safety: read=1200
Top tags: group-0(100), group-1(100)
Top path prefixes: /groups(1200)
Large package hint: regenerate with --include-tag, --include-path, --include-operation, or --max-tools before wiring this into an Agent.
```

Tool list 默认仍然截断，也可以继续用 `--all` 展开。

### Targeted Tool Test

`api2agent test` 现在可以运行指定 generated tool：

```bash
api2agent test ./package --tool get_repo --params '{"owner":"octocat","repo":"Hello-World"}'
```

这提升了 large-package usability，因为开发者不必依赖 `smoke_test.py` 里默认选中的 read-only tool。

安全边界保持不变：

- selected write/delete tools 需要 `--allow-write`
- 默认 `api2agent test` 仍然 read-only
- `api2agent test --allow-write` 继续运行 guarded manual write path

### Generated README Guidance

Generated package READMEs 现在会说明如何使用 `api2agent test --tool ... --params ...` 做 targeted read checks。

## Dogfood

复现命令：

```bash
python scripts/api2agent_large_spec_performance_dogfood.py
```

产物：

```text
.dogfood/large-spec-performance/result.json
```

Dogfood flow：

```text
synthetic 1200-operation OpenAPI spec
  -> unfiltered generation
  -> large package warning
  -> inspect summary with limit=3
  -> bounded generation with --max-tools 5
  -> bounded generation with --include-tag group-7 --max-tools 5
  -> targeted api2agent test --tool get_group7_item0
  -> one local provider GET
```

Dogfood checks：

- unfiltered generation 成功生成 1200 tools
- unfiltered generation 对过大的 tool count 给出 warning
- inspect 输出 tool count、summary、truncation 和 large-package hint
- `--max-tools 5` 生成 5 个 tools 且不再输出 large-package warning
- `--include-tag group-7 --max-tools 5` 生成 5 个 tools
- targeted `api2agent test --tool` 只调用一次选中的 read tool
- API-first 和 no-workflow-engine 约束保持明确

## 结果

Dogfood 已通过。

关键观测值：

```json
{
  "unfiltered_tool_count_1200": true,
  "unfiltered_generation_warns_large_package": true,
  "inspect_prints_tool_count": true,
  "inspect_truncates_tools": true,
  "max_tools_limited_to_5": true,
  "tag_filtered_limited_to_5": true,
  "selected_tool_test_success": true,
  "selected_tool_called_provider_once": true
}
```

## 为什么重要

Large specs 是 API2Agent 真实 onboarding 问题：

- 会压垮 Agent tool selection
- package inspection 会变得很吵
- smoke testing 会显得任意
- 在开发者选择有用 capability slice 之前就增加 generation cost

这个 slice 让 large APIs 更可用，同时保持当前产品目标：

- 更多真实执行数据
- 更低 API/provider onboarding cost
- 更快、更可控的 generated-package iteration

## 剩余缺口

本报告当时剩余的 Tooling Re-entry 项是 curl naming residual review。该 review 现在已完成；详见 `docs/cn-ZH/API2AGENT_CURL_NAMING_RESIDUAL_REVIEW.md`。

该阶段收口现在已完成。下一项任务：

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```
