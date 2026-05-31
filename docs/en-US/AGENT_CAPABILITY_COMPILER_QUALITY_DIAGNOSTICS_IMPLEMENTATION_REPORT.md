# Agent Capability Compiler Quality Diagnostics Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

Agent capability compiler quality diagnostics are implemented.

Generated packages now include an additive diagnostics artifact:

```text
diagnostics.json
```

The compiler also exposes:

- a pure IR diagnostics engine
- generation-time diagnostics summary output
- `api2agent diagnose <package_dir>`
- `api2agent diagnose <package_dir> --json`
- compact diagnostics status in generated README files
- compact diagnostics status in `api2agent inspect`

No workflow engine, marketplace, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation was added.

## Files

Implementation:

- `api2agent/diagnostics.py`
- `api2agent/generators/package.py`
- `api2agent/generators/readme.py`
- `api2agent/cli.py`

Tests:

- `tests/test_diagnostics.py`
- `tests/test_generators.py`

## Contract

Generated packages now write:

```text
diagnostics.json
```

Contract version:

```text
api2agent.capability_diagnostics.v0
```

The artifact includes:

- `status`: `pass`, `warn`, or `fail`
- `score`: simple `0..100` developer-facing heuristic
- `summary`: error/warning/info counts
- `metrics`: tool count, safety counts, required parameter count, auth count, tool base URL count
- `generation_context`: optional source/filter context when available
- `findings`: deterministic finding objects with id, severity, category, message, location, recommendation, and evidence

## Implemented Findings

Agent usability:

- `large_toolset`
- `no_read_tools`
- `generic_capability_name`
- `generic_tool_name`
- `duplicate_tool_names`
- `weak_tool_description`

Safety:

- `unknown_safety`
- `write_tools_present`
- `write_only_package`

Auth and credentials:

- `unknown_auth`
- `auth_env_missing`
- `mixed_auth_summary`

Schema and parameters:

- `many_required_parameters`
- `required_body_without_schema`
- `broad_object_schema`
- `missing_parameter_descriptions`

Execution and observability:

- `missing_base_url`
- `missing_provider_region`
- `proxy_identity_ready`

## CLI Behavior

Generation prints a compact summary:

```text
Generated capability package: tmp\diagnostics-dogfood\basic
Diagnostics: pass score=94 errors=0 warnings=0 info=3
```

`diagnose` prints human-readable findings by default:

```text
api2agent diagnose tmp\diagnostics-dogfood\write
```

It emits the full contract with:

```text
api2agent diagnose tmp\diagnostics-dogfood\basic --json
```

`inspect` remains compatible with old packages and shows the diagnostics summary only when `diagnostics.json` exists.

## Dogfood Evidence

Small OpenAPI fixture:

```text
Diagnostics: pass score=94 errors=0 warnings=0 info=3
```

Observed findings:

- `missing_provider_region`
- `missing_parameter_descriptions`
- `proxy_identity_ready`

Write-method curl package:

```text
Diagnostics: warn score=56 errors=0 warnings=4 info=2
```

Observed findings:

- `no_read_tools`
- `write_only_package`
- `missing_provider_region`
- `write_tools_present`
- `weak_tool_description`
- `proxy_identity_ready`

## Compatibility

The implementation is additive:

- existing generated execution files remain compatible
- `diagnostics.json` is new but not required for old packages
- `api2agent diagnose` recomputes diagnostics when the artifact is absent
- `api2agent inspect` still works when `diagnostics.json` is absent
- generation is not blocked by warnings in v0

## Validation

Passed:

```text
python -m py_compile api2agent\diagnostics.py api2agent\cli.py api2agent\generators\package.py api2agent\generators\readme.py
```

Passed:

```text
pytest tests\test_diagnostics.py tests\test_generators.py tests\test_cli.py
```

Result:

```text
52 passed
```

Passed:

```text
pytest
```

Result:

```text
177 passed
```

## Next Recommended Task

```text
Agent Capability Compiler Quality Diagnostics Closeout + Phase Review v0
```

The closeout should decide whether the diagnostics slice can close and whether the next compiler expansion should move to OpenAPI real-world hardening, curl instant onboarding, or diagnostics dogfood expansion against larger real specs.
