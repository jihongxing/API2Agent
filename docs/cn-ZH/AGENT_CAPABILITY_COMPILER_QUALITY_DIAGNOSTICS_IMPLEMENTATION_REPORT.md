# Agent Capability Compiler Quality Diagnostics Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent capability compiler quality diagnostics 已实现。

Generated packages 现在会包含一个 additive diagnostics artifact：

```text
diagnostics.json
```

Compiler 也提供：

- pure IR diagnostics engine
- generation-time diagnostics summary output
- `api2agent diagnose <package_dir>`
- `api2agent diagnose <package_dir> --json`
- generated README 中的 compact diagnostics status
- `api2agent inspect` 中的 compact diagnostics status

本 slice 未增加 workflow engine、marketplace、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## Files

Implementation：

- `api2agent/diagnostics.py`
- `api2agent/generators/package.py`
- `api2agent/generators/readme.py`
- `api2agent/cli.py`

Tests：

- `tests/test_diagnostics.py`
- `tests/test_generators.py`

## Contract

Generated packages 现在会写入：

```text
diagnostics.json
```

Contract version：

```text
api2agent.capability_diagnostics.v0
```

该 artifact 包含：

- `status`: `pass`、`warn` 或 `fail`
- `score`: simple `0..100` developer-facing heuristic
- `summary`: error/warning/info counts
- `metrics`: tool count、safety counts、required parameter count、auth count、tool base URL count
- `generation_context`: 可选 source/filter context
- `findings`: deterministic finding objects，包含 id、severity、category、message、location、recommendation 和 evidence

## Implemented Findings

Agent usability：

- `large_toolset`
- `no_read_tools`
- `generic_capability_name`
- `generic_tool_name`
- `duplicate_tool_names`
- `weak_tool_description`

Safety：

- `unknown_safety`
- `write_tools_present`
- `write_only_package`

Auth and credentials：

- `unknown_auth`
- `auth_env_missing`
- `mixed_auth_summary`

Schema and parameters：

- `many_required_parameters`
- `required_body_without_schema`
- `broad_object_schema`
- `missing_parameter_descriptions`

Execution and observability：

- `missing_base_url`
- `missing_provider_region`
- `proxy_identity_ready`

## CLI Behavior

Generation 会打印 compact summary：

```text
Generated capability package: tmp\diagnostics-dogfood\basic
Diagnostics: pass score=94 errors=0 warnings=0 info=3
```

`diagnose` 默认打印 human-readable findings：

```text
api2agent diagnose tmp\diagnostics-dogfood\write
```

使用下面命令输出完整 contract：

```text
api2agent diagnose tmp\diagnostics-dogfood\basic --json
```

`inspect` 保持与旧 packages 兼容；只有存在 `diagnostics.json` 时才显示 diagnostics summary。

## Dogfood Evidence

Small OpenAPI fixture：

```text
Diagnostics: pass score=94 errors=0 warnings=0 info=3
```

Observed findings：

- `missing_provider_region`
- `missing_parameter_descriptions`
- `proxy_identity_ready`

Write-method curl package：

```text
Diagnostics: warn score=56 errors=0 warnings=4 info=2
```

Observed findings：

- `no_read_tools`
- `write_only_package`
- `missing_provider_region`
- `write_tools_present`
- `weak_tool_description`
- `proxy_identity_ready`

## Compatibility

实现是 additive：

- existing generated execution files 保持兼容
- `diagnostics.json` 是新增文件，但旧 packages 不需要它
- `api2agent diagnose` 会在 artifact 缺失时重新计算 diagnostics
- `api2agent inspect` 在 `diagnostics.json` 缺失时仍可工作
- v0 中 warnings 不会阻塞 generation

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

## 推荐下一项任务

```text
Agent Capability Compiler Quality Diagnostics Closeout + Phase Review v0
```

Closeout 应判断 diagnostics slice 是否可以关闭，并决定下一项 compiler expansion 进入 OpenAPI real-world hardening、curl instant onboarding，还是针对更大真实 specs 扩展 diagnostics dogfood。
