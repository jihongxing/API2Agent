# Agent Capability Compiler OpenAPI Server Handling Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI server handling is implemented for the Agent capability compiler.

Generated packages now preserve document/path/operation server metadata while keeping the existing `base_url` and `tool.base_url` execution behavior compatible.

The implementation supports:

- all document-level server choices as generated metadata
- server variable default substitution plus preserved variable metadata
- path-level server overrides
- operation-level server overrides
- selected server provenance with `server_source`
- relative server URL detection
- deterministic profile hints such as `production`, `staging`, `admin`, `regional`, and `relative`
- README server choices and override guidance
- inspect server summaries
- diagnostics for multi-server, relative URL, variables, and server overrides

No network probing, LLM server selection, hosted profile management, workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation was added.

## Files

Implementation:

- `api2agent/ir/models.py`
- `api2agent/parsers/openapi.py`
- `api2agent/generators/readme.py`
- `api2agent/diagnostics.py`
- `api2agent/cli.py`

Tests and fixtures:

- `tests/fixtures/openapi/server_choices.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

## Contract

The IR additions are additive:

- `ServerVariable`
- `ServerConfig`
- `Capability.servers`
- `Tool.servers`
- `Tool.server_source`

Existing generated package consumers can keep reading:

```text
Capability.base_url
Tool.base_url
```

New consumers can inspect:

```text
servers
server_source
```

Each server entry includes:

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

Server selection remains compatible and deterministic:

1. operation-level first server wins for that operation
2. path-level first server wins when operation-level server is absent
3. document-level first server wins otherwise
4. server variables use their default values in `resolved_url`
5. selected document-level server still populates `Capability.base_url`
6. selected path/operation server still populates `Tool.base_url` when it differs from capability default

All document server choices are preserved in `Capability.servers`. Tool selected server choices are preserved in `Tool.servers`.

## Generated Artifact Effects

README now lists known OpenAPI servers:

```text
Known OpenAPI servers:
- `https://api.example.com/v1` (document hints=production) - Production API
- `https://staging.example.com/v1` (document hints=staging) - Staging API
- `/api/v3` (document relative hints=relative) - Relative Petstore-style API
```

Tool summaries now show path/operation server provenance:

```text
get_admin ... [server: path]
get_regional ... [server: operation]
```

`api2agent inspect` now shows:

```text
Servers: 3 hints=production,relative,staging
```

Diagnostics now report:

- `multiple_servers_present`
- `relative_server_url`
- `server_variables_present`
- `path_server_override`
- `operation_server_override`
- `ambiguous_server_profiles`

Generated runner override precedence remains unchanged:

```text
API2AGENT_TOOL_BASE_URL_<TOOL_NAME>
-> API2AGENT_BASE_URL
-> tool.base_url
-> capability.base_url
```

## Dogfood Evidence

Generated package:

```text
python -m api2agent.cli generate tests\fixtures\openapi\server_choices.yaml --output tmp\openapi-server-handling --force
```

Observed:

```text
Generated capability package: tmp\openapi-server-handling
Diagnostics: warn score=50 errors=0 warnings=4 info=9
```

`inspect` showed:

```text
Servers: 3 hints=production,relative,staging
get_admin ... base=https://admin.example.com server=path
get_regional ... base=https://us.example.com server=operation
```

Loopback runner dogfood passed:

```text
API2AGENT_BASE_URL=http://127.0.0.1:18767/base
api2agent test tmp\openapi-server-handling --tool get_public --params '{}'
```

Observed:

```text
/base/public
```

Tool-specific override also passed:

```text
API2AGENT_TOOL_BASE_URL_GET_ADMIN=http://127.0.0.1:18767/admin-base
api2agent test tmp\openapi-server-handling --tool get_admin --params '{}'
```

Observed:

```text
/admin-base/admin
```

## Compatibility

Compatibility is preserved:

- existing `Capability.base_url` behavior remains unchanged
- existing `Tool.base_url` behavior remains unchanged
- generated runner override precedence remains unchanged
- old capability JSON without server metadata remains valid
- server metadata is advisory and does not auto-switch runtime targets

## Validation

Passed:

```text
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\generators\readme.py api2agent\diagnostics.py api2agent\cli.py
```

Passed:

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py::test_inspect_command_prints_server_summary tests\test_runner_generation.py::test_execute_tool_uses_tool_level_base_url tests\test_runner_generation.py::test_execute_tool_uses_global_base_url_override tests\test_runner_generation.py::test_execute_tool_uses_tool_base_url_override_before_global
```

Result:

```text
35 passed
```

Passed:

```text
pytest
```

Result:

```text
189 passed
```

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Server Handling Closeout + Phase Review v0
```

The closeout should decide whether this server handling slice can close and whether the next OpenAPI hardening target should be schema shaping or filtering diagnostics.
