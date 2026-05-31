# Agent Capability Compiler Expansion Design v0

Date: 2026-06-01

Status: complete

## Decision

The first Agent capability compiler expansion slice should be:

```text
Agent Capability Compiler Quality Diagnostics v0
```

This slice adds a deterministic diagnostics layer for generated capabilities. It should inspect the compiler's existing `Capability` IR and generated `capability.json`, then report whether the package is likely to be Agent-usable before a developer wires it into an Agent or proxy path.

This is the right first expansion because it improves both OpenAPI and curl onboarding without adding a new runtime, hosted dependency, workflow engine, marketplace surface, vault, billing system, or public Control Plane API.

## Product Goal

Reduce the time from API input to a useful Agent capability.

The compiler should not only produce files. It should tell the developer:

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

Expected v0 behavior after implementation:

- package files are generated as today
- `diagnostics.json` is written into the package directory
- CLI prints a short quality summary after existing generation warnings
- no generation is blocked unless the package has no matched tools, as today

### Diagnose Existing Package

```text
api2agent diagnose generated/github
api2agent diagnose generated/github --json
```

Expected v0 behavior:

- reads `capability.json`
- emits human-readable findings by default
- emits the full diagnostics contract with `--json`
- exits `0` unless a future `--fail-on` option is set

### Inspect

```text
api2agent inspect generated/github
```

Expected v0 behavior:

- continues showing the existing package summary
- may include a compact diagnostics status if `diagnostics.json` exists
- does not replace detailed `diagnose`

## Accepted Inputs

### Required

- `api2agent.ir.models.Capability`
- generated `capability.json`

### Optional Generation Context

The diagnostics engine may accept generation context when available:

- source kind: `openapi` or `curl`
- original operation/tool count before filters
- selected filters
- generated package path

The v0 diagnostics must still work when only `capability.json` is available.

## Diagnostics Contract

Write:

```text
diagnostics.json
```

Contract shape:

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

Status rules:

- `fail`: one or more `error` findings
- `warn`: no errors, one or more `warning` findings
- `pass`: no errors or warnings

The score is a developer-facing heuristic from `0` to `100`. It is not a protocol guarantee and must not be used for security decisions.

## Initial Finding Set

### Agent Usability

- `large_toolset`: generated tool count is above the Agent-usable threshold
- `no_read_tools`: package has only write/delete/unknown tools
- `generic_capability_name`: capability name is too generic, such as `api`, `www`, `default`, or `openapi`
- `generic_tool_name`: tool name is too generic, such as `get`, `post`, `list`, `create`, or `execute`
- `duplicate_tool_names`: duplicate generated tool names after normalization
- `weak_tool_description`: tool description is empty or only repeats method/path

### Safety

- `unknown_safety`: one or more tools have unknown safety classification
- `write_tools_present`: write/delete tools exist and require explicit manual testing
- `write_only_package`: package has no safe default read path

### Auth And Credentials

- `unknown_auth`: capability or tool auth is unknown
- `auth_env_missing`: auth is required but no env var name is available
- `mixed_auth_summary`: package uses endpoint-level auth and should show per-tool auth clearly

### Schema And Parameters

- `many_required_parameters`: a tool has many required parameters
- `required_body_without_schema`: required body lacks an object schema
- `broad_object_schema`: body schema accepts an unconstrained object
- `missing_parameter_descriptions`: required parameters have no descriptions

### Execution And Observability

- `missing_base_url`: capability has no base URL and no tool-level base URLs
- `missing_provider_region`: provider region is absent; this is informational only
- `proxy_identity_ready`: capability has stable capability/provider/tool identity for proxy usage

## Scoring Heuristic

Start at `100`, then subtract:

- `35` for each error
- `10` for each warning
- `2` for each info finding, capped at `10`

Clamp to `0..100`.

V0 should keep score simple and explainable. The findings are more important than the number.

## Generated Artifact Changes

Implementation should add:

- `diagnostics.json` in generated package directories
- optional diagnostics section in generated `README.md`
- optional diagnostics summary in `api2agent inspect`

Compatibility rule:

- existing generated package files and execution behavior must remain compatible
- `diagnostics.json` is additive
- old packages without `diagnostics.json` must still work

## CLI Changes

Add:

```text
api2agent diagnose <package_dir> [--json]
```

Optional later flags:

```text
--fail-on warning|error
--max-tools <n>
```

Do not block generation by default in v0. Diagnostics should guide, not surprise-break existing workflows.

## Tests

Implementation should cover:

- generic capability names produce `generic_capability_name`
- generic tool names produce `generic_tool_name`
- large generated packages produce `large_toolset`
- unknown safety produces `unknown_safety`
- write-only packages produce `write_only_package`
- auth without env produces `auth_env_missing`
- required body without schema produces `required_body_without_schema`
- generated packages write `diagnostics.json`
- `api2agent diagnose --json` emits the contract
- existing generated packages without `diagnostics.json` still inspect and run

## Dogfood

Run diagnostics against:

- a small OpenAPI fixture
- a mixed-auth OpenAPI fixture
- a large-spec or synthetic large-package fixture
- a root-path curl package
- a write-method curl package

Expected dogfood evidence:

- small read package: `pass` or low-warning `warn`
- mixed auth package: includes auth summary findings
- large package: warns about tool count and filtering
- root-path curl: no generic `get` regression if current naming is good
- write package: warns about manual write testing

## Success Metrics

The next implementation is successful when:

- developers can see why a generated package is or is not Agent-ready
- quality findings are deterministic in tests
- diagnostics are available for both OpenAPI and curl packages
- existing generation and execution flows remain backward compatible
- no hosted Control Plane, workflow runtime, marketplace, vault, or billing dependency is introduced

## Non-Goals

Do not implement:

- real API execution inside diagnostics
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

- first compiler expansion slice is selected
- target workflow is defined
- diagnostics contract is defined
- initial finding set is defined
- generated artifact changes are additive
- CLI changes are scoped
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
