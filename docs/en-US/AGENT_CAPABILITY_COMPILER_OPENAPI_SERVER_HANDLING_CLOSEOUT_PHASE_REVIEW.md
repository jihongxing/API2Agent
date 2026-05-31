# Agent Capability Compiler OpenAPI Server Handling Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Server Handling implementation slice can close.

The compiler now preserves enough server metadata for generated packages to explain default targets, path/operation overrides, relative server URLs, variables, and environment/profile hints without changing runtime override compatibility.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Schema Shaping Design v0
```

The next design should focus on improving Agent-facing input schemas for nullable fields, read/write-only properties, additional properties, arrays, and nested `oneOf` / `anyOf` readability.

## What Is Now Complete

### Design

Completed:

- documented current server handling baseline and gaps
- defined additive server metadata IR
- defined deterministic server selection rules
- defined relative server URL policy
- defined profile hints as advisory metadata
- defined generated README, inspect, diagnostics, runner, tests, and dogfood effects
- preserved API-first non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_DESIGN.md`

### Implementation

Completed:

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
- diagnostics for multiple servers, relative URLs, variables, and server overrides
- regression fixture and tests
- loopback dogfood for base URL override precedence

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_IMPLEMENTATION_REPORT.md`

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
| no network probing, LLM server selection, hosted profile management, workflow, marketplace, vault, billing, hosted public CRUD, gateway permission source, or automatic propagation is added | passed |

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

Passed loopback dogfood for:

- package-wide `API2AGENT_BASE_URL`
- tool-specific `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>`
- server metadata in README, inspect, diagnostics, and `capability.json`

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The compiler now surfaces server layout clearly enough for local package users to understand and override runtime targets without source edits. It also keeps the existing runner behavior stable.

This closes the main base URL/server metadata gap identified during real OpenAPI hardening.

## Remaining Risks

### Profile Hints Are Heuristics

Profile hints are deterministic and useful, but they are not semantic proof. Users still need to choose the correct target for production, staging, sandbox, or regional execution.

### Relative Server URLs Still Need Runtime Origin

The compiler now makes relative URLs visible and diagnosed, but it does not invent origins. Users must provide `API2AGENT_BASE_URL` for real execution.

### Server Metadata Does Not Auto-Switch Execution

This is intentional. Automatic profile switching would need explicit product semantics, not just parser behavior.

### Schema Complexity Is Now The Bigger Agent Usability Gap

With examples/defaults, auth combinations, and server handling improved, the next real-world OpenAPI gap is schema shaping: nullable fields, read/write-only properties, additional properties, arrays, and nested `oneOf` / `anyOf`.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Schema Shaping Design v0
```

That design should define how OpenAPI schema features are normalized into clearer Agent-facing inputs while preserving generated package compatibility and offline deterministic generation.
