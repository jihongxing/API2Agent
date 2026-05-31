# Agent Capability Compiler OpenAPI Server Handling Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent capability compiler 已实现 OpenAPI server handling。

Generated packages 现在会保留 document/path/operation server metadata，同时保持已有 `base_url` 和 `tool.base_url` execution behavior compatible。

本实现支持：

- all document-level server choices as generated metadata
- server variable default substitution plus preserved variable metadata
- path-level server overrides
- operation-level server overrides
- selected server provenance with `server_source`
- relative server URL detection
- deterministic profile hints，例如 `production`、`staging`、`admin`、`regional` 和 `relative`
- README server choices and override guidance
- inspect server summaries
- diagnostics for multi-server、relative URL、variables 和 server overrides

本 slice 未增加 network probing、LLM server selection、hosted profile management、workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## Files

Implementation：

- `api2agent/ir/models.py`
- `api2agent/parsers/openapi.py`
- `api2agent/generators/readme.py`
- `api2agent/diagnostics.py`
- `api2agent/cli.py`

Tests and fixtures：

- `tests/fixtures/openapi/server_choices.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

## Contract

IR additions 是 additive：

- `ServerVariable`
- `ServerConfig`
- `Capability.servers`
- `Tool.servers`
- `Tool.server_source`

已有 generated package consumers 可以继续读取：

```text
Capability.base_url
Tool.base_url
```

新 consumers 可以 inspect：

```text
servers
server_source
```

每个 server entry 包含：

- raw `url`
- `resolved_url`
- `description`
- `variables`
- `source`
- `path`
- `operation_id`
- `profile_hints`
- `is_relative`

## Parser Behavior

Server selection 保持 compatible and deterministic：

1. operation-level first server wins for that operation
2. path-level first server wins when operation-level server is absent
3. document-level first server wins otherwise
4. server variables 使用 default values 生成 `resolved_url`
5. selected document-level server 继续填充 `Capability.base_url`
6. selected path/operation server 与 capability default 不同时，继续填充 `Tool.base_url`

所有 document server choices 都保留在 `Capability.servers`。Tool selected server choices 保留在 `Tool.servers`。

## Generated Artifact Effects

README 现在列出 known OpenAPI servers：

```text
Known OpenAPI servers:
- `https://api.example.com/v1` (document hints=production) - Production API
- `https://staging.example.com/v1` (document hints=staging) - Staging API
- `/api/v3` (document relative hints=relative) - Relative Petstore-style API
```

Tool summaries 现在显示 path/operation server provenance：

```text
get_admin ... [server: path]
get_regional ... [server: operation]
```

`api2agent inspect` 现在显示：

```text
Servers: 3 hints=production,relative,staging
```

Diagnostics 现在报告：

- `multiple_servers_present`
- `relative_server_url`
- `server_variables_present`
- `path_server_override`
- `operation_server_override`
- `ambiguous_server_profiles`

Generated runner override precedence 保持不变：

```text
API2AGENT_TOOL_BASE_URL_<TOOL_NAME>
-> API2AGENT_BASE_URL
-> tool.base_url
-> capability.base_url
```

## Dogfood Evidence

已生成 package：

```text
python -m api2agent.cli generate tests\fixtures\openapi\server_choices.yaml --output tmp\openapi-server-handling --force
```

观察到：

```text
Generated capability package: tmp\openapi-server-handling
Diagnostics: warn score=50 errors=0 warnings=4 info=9
```

`inspect` 显示：

```text
Servers: 3 hints=production,relative,staging
get_admin ... base=https://admin.example.com server=path
get_regional ... base=https://us.example.com server=operation
```

Loopback runner dogfood 已通过：

```text
API2AGENT_BASE_URL=http://127.0.0.1:18767/base
api2agent test tmp\openapi-server-handling --tool get_public --params '{}'
```

观察到：

```text
/base/public
```

Tool-specific override 也已通过：

```text
API2AGENT_TOOL_BASE_URL_GET_ADMIN=http://127.0.0.1:18767/admin-base
api2agent test tmp\openapi-server-handling --tool get_admin --params '{}'
```

观察到：

```text
/admin-base/admin
```

## Compatibility

Compatibility 已保留：

- existing `Capability.base_url` behavior remains unchanged
- existing `Tool.base_url` behavior remains unchanged
- generated runner override precedence remains unchanged
- old capability JSON without server metadata remains valid
- server metadata 是 advisory，不会自动切换 runtime targets

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

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Server Handling Closeout + Phase Review v0
```

Closeout 应判断这个 server handling slice 是否可以关闭，并决定下一项 OpenAPI hardening target 进入 schema shaping 还是 filtering diagnostics。
