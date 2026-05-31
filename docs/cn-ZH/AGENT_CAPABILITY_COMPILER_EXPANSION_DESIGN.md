# Agent Capability Compiler Expansion Design v0

日期：2026-06-01

状态：complete

## 决策

第一项 Agent capability compiler expansion slice 应该是：

```text
Agent Capability Compiler Quality Diagnostics v0
```

这个 slice 会为 generated capabilities 增加 deterministic diagnostics layer。它检查现有 compiler 的 `Capability` IR 和 generated `capability.json`，在开发者把 package 接入 Agent 或 proxy path 之前，报告该 package 是否足够 Agent-usable。

这是合适的第一项扩展，因为它同时改善 OpenAPI 和 curl onboarding，又不增加新 runtime、hosted dependency、workflow engine、marketplace surface、vault、billing system 或 public Control Plane API。

## 产品目标

降低从 API input 到 useful Agent capability 的时间。

Compiler 不应该只是产出文件，还应该告诉开发者：

```text
what was generated
  -> what looks Agent-ready
  -> what is risky or vague
  -> what to fix next
```

## Target User Workflow

### Generate

```text
api2agent generate openapi.yaml --output generated/github --include-path /repos
```

实现后的 v0 预期行为：

- package files 与今天一样生成
- `diagnostics.json` 写入 package directory
- CLI 在现有 generation warnings 之后打印简短 quality summary
- 除了当前“没有 matched tools”的情况，generation 默认不阻塞

### Diagnose Existing Package

```text
api2agent diagnose generated/github
api2agent diagnose generated/github --json
```

v0 预期行为：

- 读取 `capability.json`
- 默认输出 human-readable findings
- `--json` 输出完整 diagnostics contract
- 除非未来设置 `--fail-on`，否则 exit `0`

### Inspect

```text
api2agent inspect generated/github
```

v0 预期行为：

- 继续显示现有 package summary
- 如果存在 `diagnostics.json`，可以显示 compact diagnostics status
- 不替代详细 `diagnose`

## Accepted Inputs

### Required

- `api2agent.ir.models.Capability`
- generated `capability.json`

### Optional Generation Context

有可用 generation context 时，diagnostics engine 可以接收：

- source kind: `openapi` or `curl`
- filters 前的 original operation/tool count
- selected filters
- generated package path

v0 diagnostics 必须在只有 `capability.json` 的情况下仍能工作。

## Diagnostics Contract

写入：

```text
diagnostics.json
```

Contract shape：

```json
{
  "contract_version": "api2agent.capability_diagnostics.v0",
  "status": "pass",
  "score": 92,
  "summary": {
    "errors": 0,
    "warnings": 1,
    "info": 2
  },
  "metrics": {
    "tool_count": 3,
    "read_tools": 3,
    "write_tools": 0,
    "delete_tools": 0,
    "unknown_safety_tools": 0,
    "required_parameter_count": 2,
    "tools_with_auth": 1,
    "tools_with_tool_base_url": 0
  },
  "findings": [
    {
      "id": "large_toolset",
      "severity": "warning",
      "category": "agent_usability",
      "message": "Package has many tools and may need filtering before Agent use.",
      "location": {
        "kind": "capability",
        "name": "github_api"
      },
      "recommendation": "Regenerate with --include-tag, --include-path, --include-operation, or --max-tools.",
      "evidence": {
        "tool_count": 1186,
        "threshold": 50
      }
    }
  ]
}
```

Status rules：

- `fail`: 一个或多个 `error` findings
- `warn`: 没有 errors，但有一个或多个 `warning` findings
- `pass`: 没有 errors 或 warnings

Score 是面向 developer 的 `0` 到 `100` heuristic。它不是 protocol guarantee，不能用于 security decisions。

## Initial Finding Set

### Agent Usability

- `large_toolset`: generated tool count 超过 Agent-usable threshold
- `no_read_tools`: package 只有 write/delete/unknown tools
- `generic_capability_name`: capability name 太泛，例如 `api`、`www`、`default` 或 `openapi`
- `generic_tool_name`: tool name 太泛，例如 `get`、`post`、`list`、`create` 或 `execute`
- `duplicate_tool_names`: normalization 后出现 duplicate generated tool names
- `weak_tool_description`: tool description 为空或只重复 method/path

### Safety

- `unknown_safety`: 一个或多个 tools 的 safety classification 是 unknown
- `write_tools_present`: 存在 write/delete tools，需要 explicit manual testing
- `write_only_package`: package 没有 safe default read path

### Auth And Credentials

- `unknown_auth`: capability 或 tool auth 是 unknown
- `auth_env_missing`: 需要 auth，但没有 env var name
- `mixed_auth_summary`: package 使用 endpoint-level auth，需要清晰展示 per-tool auth

### Schema And Parameters

- `many_required_parameters`: 某个 tool 有很多 required parameters
- `required_body_without_schema`: required body 缺少 object schema
- `broad_object_schema`: body schema 接受 unconstrained object
- `missing_parameter_descriptions`: required parameters 没有 descriptions

### Execution And Observability

- `missing_base_url`: capability 没有 base URL，tools 也没有 tool-level base URLs
- `missing_provider_region`: provider region 缺失；这只是 informational
- `proxy_identity_ready`: capability 拥有 stable capability/provider/tool identity，可用于 proxy usage

## Scoring Heuristic

从 `100` 开始扣分：

- 每个 error 扣 `35`
- 每个 warning 扣 `10`
- 每个 info 扣 `2`，最多扣 `10`

最终 clamp 到 `0..100`。

v0 应保持 score 简单、可解释。Findings 比数字更重要。

## Generated Artifact Changes

Implementation 应增加：

- generated package directories 中的 `diagnostics.json`
- generated `README.md` 中可选 diagnostics section
- `api2agent inspect` 中可选 diagnostics summary

Compatibility rule：

- existing generated package files 和 execution behavior 必须保持兼容
- `diagnostics.json` 是 additive
- 没有 `diagnostics.json` 的旧 packages 必须仍可工作

## CLI Changes

新增：

```text
api2agent diagnose <package_dir> [--json]
```

以后可选 flags：

```text
--fail-on warning|error
--max-tools <n>
```

v0 默认不阻塞 generation。Diagnostics 应指导用户，而不是意外 break 现有 workflows。

## Tests

Implementation 应覆盖：

- generic capability names 产生 `generic_capability_name`
- generic tool names 产生 `generic_tool_name`
- large generated packages 产生 `large_toolset`
- unknown safety 产生 `unknown_safety`
- write-only packages 产生 `write_only_package`
- auth without env 产生 `auth_env_missing`
- required body without schema 产生 `required_body_without_schema`
- generated packages 写入 `diagnostics.json`
- `api2agent diagnose --json` 输出 contract
- 没有 `diagnostics.json` 的 existing generated packages 仍可 inspect 和 run

## Dogfood

对这些输入运行 diagnostics：

- small OpenAPI fixture
- mixed-auth OpenAPI fixture
- large-spec 或 synthetic large-package fixture
- root-path curl package
- write-method curl package

Expected dogfood evidence：

- small read package: `pass` 或 low-warning `warn`
- mixed auth package: 包含 auth summary findings
- large package: 提示 tool count 和 filtering
- root-path curl: 如果当前 naming 表现良好，不应回归到 generic `get`
- write package: 提示 manual write testing

## Success Metrics

下一项 implementation 成功条件：

- developers 能看到 generated package 为什么是或不是 Agent-ready
- quality findings 在 tests 中 deterministic
- diagnostics 同时适用于 OpenAPI 和 curl packages
- existing generation 和 execution flows 保持 backward compatible
- 不引入 hosted Control Plane、workflow runtime、marketplace、vault 或 billing dependency

## Non-Goals

不要实现：

- diagnostics 中的真实 API execution
- LLM-based package review
- workflow composition
- non-API runtime adapters
- provider marketplace submission
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- production gateway permission source
- automatic snapshot publish/reload

## Acceptance Criteria For This Design

- first compiler expansion slice 已选择
- target workflow 已定义
- diagnostics contract 已定义
- initial finding set 已定义
- generated artifact changes 是 additive
- CLI changes 有边界
- tests 和 dogfood 已命名
- non-goals 保持 API-first compiler boundaries
