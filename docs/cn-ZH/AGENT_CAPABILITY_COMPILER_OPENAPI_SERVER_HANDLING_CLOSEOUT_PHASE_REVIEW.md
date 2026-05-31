# Agent Capability Compiler OpenAPI Server Handling Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Server Handling implementation slice 可以关闭。

Compiler 现在保留了足够的 server metadata，让 generated packages 能解释 default targets、path/operation overrides、relative server URLs、variables 和 environment/profile hints，同时不改变 runtime override compatibility。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Schema Shaping Design v0
```

下一项设计应聚焦改善 Agent-facing input schemas，包括 nullable fields、read/write-only properties、additional properties、arrays 和 nested `oneOf` / `anyOf` readability。

## 现在已完成

### Design

已完成：

- documented current server handling baseline and gaps
- defined additive server metadata IR
- defined deterministic server selection rules
- defined relative server URL policy
- defined profile hints as advisory metadata
- defined generated README、inspect、diagnostics、runner、tests 和 dogfood effects
- preserved API-first non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_DESIGN.md`

### Implementation

已完成：

- additive `ServerVariable`
- additive `ServerConfig`
- `Capability.servers`
- `Tool.servers`
- `Tool.server_source`
- preservation of document-level server choices
- preservation of server variable metadata with default-substituted `resolved_url`
- path-level and operation-level server provenance
- relative server URL detection
- deterministic profile hints
- README server choices and relative URL guidance
- `api2agent inspect` server summaries
- diagnostics for multiple servers、relative URLs、variables 和 server overrides
- regression fixture and tests
- loopback dogfood for base URL override precedence

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| all document server choices are preserved | passed |
| server variables are preserved | passed |
| selected `resolved_url` uses server variable defaults | passed |
| existing `Capability.base_url` behavior remains compatible | passed |
| existing `Tool.base_url` behavior remains compatible | passed |
| path server provenance is visible | passed |
| operation server provenance is visible | passed |
| relative server URLs are marked and diagnosed | passed |
| profile hints are visible and advisory | passed |
| README lists server choices and override guidance | passed |
| inspect shows server summaries | passed |
| diagnostics report server ambiguity and overrides | passed |
| runner override precedence remains unchanged | passed |
| old capability JSON remains compatible | passed |
| 未增加 network probing、LLM server selection、hosted profile management、workflow、marketplace、vault、billing、hosted public CRUD、gateway permission source 或 automatic propagation | passed |

## Validation

已通过：

```text
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\generators\readme.py api2agent\diagnostics.py api2agent\cli.py
```

已通过：

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py::test_inspect_command_prints_server_summary tests\test_runner_generation.py::test_execute_tool_uses_tool_level_base_url tests\test_runner_generation.py::test_execute_tool_uses_global_base_url_override tests\test_runner_generation.py::test_execute_tool_uses_tool_base_url_override_before_global
```

结果：

```text
35 passed
```

已通过：

```text
pytest
```

结果：

```text
189 passed
```

Loopback dogfood 已通过：

- package-wide `API2AGENT_BASE_URL`
- tool-specific `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>`
- README、inspect、diagnostics 和 `capability.json` 中的 server metadata

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Compiler 现在能足够清晰地暴露 server layout，让 local package users 不改 source 也能理解并覆盖 runtime targets，同时保持 existing runner behavior stable。

这关闭了 real OpenAPI hardening 中主要 base URL/server metadata gap。

## Remaining Risks

### Profile Hints Are Heuristics

Profile hints 是 deterministic and useful，但不是 semantic proof。Users 仍需要自行选择 production、staging、sandbox 或 regional execution 的正确 target。

### Relative Server URLs Still Need Runtime Origin

Compiler 现在会显示并诊断 relative URLs，但不会发明 origins。真实执行时 users 必须提供 `API2AGENT_BASE_URL`。

### Server Metadata Does Not Auto-Switch Execution

这是刻意选择。Automatic profile switching 需要 explicit product semantics，而不是单纯 parser behavior。

### Schema Complexity Is Now The Bigger Agent Usability Gap

Examples/defaults、auth combinations 和 server handling 改进后，下一个真实 OpenAPI gap 是 schema shaping：nullable fields、read/write-only properties、additional properties、arrays 和 nested `oneOf` / `anyOf`。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Schema Shaping Design v0
```

该设计应定义 OpenAPI schema features 如何规范化为更清晰的 Agent-facing inputs，同时保留 generated package compatibility 和 offline deterministic generation。
