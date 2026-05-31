# Agent Capability Compiler OpenAPI Server Handling Design v0

Date: 2026-06-01

Status: complete

## Decision

The next OpenAPI hardening implementation slice should be:

```text
Agent Capability Compiler OpenAPI Server Handling Implementation v0
```

This slice should preserve multiple OpenAPI server choices as generated metadata, improve environment/profile hints, make document/path/operation server selection visible, and handle relative server URLs safely.

It should remain API-first and must not add workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation.

## Why This Slice Now

The compiler now handles examples/defaults and security requirement combinations. The next common real-spec onboarding gap is server layout.

Real OpenAPI specs often include:

- multiple document-level servers for production, staging, sandbox, regional, or versioned APIs
- path-level servers for admin or alternate subdomains
- operation-level servers for special routes
- server variables for version, region, tenant, or environment
- relative server URLs such as `/api/v3`
- ambiguous first-server choices that may be unsafe for smoke tests

Current generation picks the first server after substituting variable defaults. That is useful but loses alternatives and does not explain server provenance to users or diagnostics.

## Current Baseline

Already present:

- document-level first server URL extraction
- server variable default substitution
- path-level server override
- operation-level server override
- tool-level `base_url` when path/operation server differs from the document server
- generated runner `API2AGENT_BASE_URL`
- generated runner `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>`
- invalid override fail-fast
- base path preservation when joining override URL and path
- inspect shows capability base URL and tool-level base override
- diagnostics detects missing base URL

Important gaps:

- non-selected server choices are discarded
- server descriptions are discarded
- server variable metadata is discarded after default substitution
- relative server URLs are not explained clearly
- generated README does not list server choices or selected provenance
- diagnostics cannot explain multi-server ambiguity
- generated packages cannot expose staging/prod/sandbox/regional hints
- operation-level server summaries are minimal
- runtime override semantics do not point users to known server profiles

## Goals

- preserve all document/path/operation server choices in generated package metadata
- keep existing `base_url` / `tool.base_url` behavior compatible
- record selected server provenance: document, path, operation, or override at runtime
- preserve server variables with defaults and enums
- infer lightweight profile hints such as `production`, `staging`, `sandbox`, `regional`, `admin`, and `relative`
- make relative server URLs safe and explicit
- improve generated README, inspect, and diagnostics server summaries
- keep runner runtime override behavior unchanged and compatible
- keep generation deterministic and offline

## Non-Goals

Do not implement:

- network probing during generation
- automatic production/staging selection by LLM
- hosted server profile management
- dynamic tenant discovery
- DNS or TLS validation
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed IR Strategy

Keep existing fields:

```text
Capability.base_url
Tool.base_url
```

Add optional metadata:

```text
ServerVariable:
  default: str | None
  enum: list[str]
  description: str | None

ServerConfig:
  url: str
  resolved_url: str
  description: str | None
  variables: dict[str, ServerVariable]
  source: "document" | "path" | "operation"
  path: str | None
  operation_id: str | None
  profile_hints: list[str]
  is_relative: bool

Capability.servers: list[ServerConfig]
Tool.servers: list[ServerConfig]
Tool.server_source: "document" | "path" | "operation" | None
```

Generated `capability.json` remains backward compatible because these fields are additive. Old consumers can continue using `base_url` and `tool.base_url`.

## Server Selection Rules

Selection should remain deterministic:

1. operation-level first server wins for that operation
2. path-level first server wins when operation-level server is absent
3. document-level first server wins when neither operation nor path server exists
4. server variables use their `default` value for `resolved_url`
5. if no server exists, `base_url` remains empty and diagnostics reports `missing_base_url`
6. relative server URLs are preserved and marked `is_relative=true`

The selected resolved URL continues to populate:

- `Capability.base_url` for the selected document-level first server
- `Tool.base_url` when selected path/operation URL differs from capability base URL

## Relative Server URL Policy

Relative server URLs should not be silently treated as complete provider origins.

For v0:

- preserve the relative URL in server metadata
- mark `is_relative=true`
- keep the existing joined behavior only when enough base context exists
- diagnostics should warn with `relative_server_url`
- README should say the user should set `API2AGENT_BASE_URL` to the real origin
- runner should continue fail-fast validation for invalid runtime overrides

Do not invent an origin during generation.

## Profile Hints

Profile hints are deterministic string heuristics from URL and description text.

Examples:

- `production`: `prod`, `production`, `api.example.com`
- `staging`: `staging`, `stage`, `test`
- `sandbox`: `sandbox`
- `regional`: variables named `region`, host labels like `{region}`, or regional descriptions
- `admin`: `admin` in host/path/description
- `relative`: relative URL

Hints are advisory metadata only. They do not change selected runtime behavior in v0.

## Generated Artifact Effects

README:

- show selected default base URL
- list known server choices with source and profile hints
- show path/operation server overrides in each tool summary when present
- explain `API2AGENT_BASE_URL` and tool-specific override in terms of known server choices
- warn clearly for relative server URLs

`api2agent inspect`:

- show default base URL as today
- show server count and top profile hints
- show tool server source for path/operation overrides

Diagnostics:

- `multiple_servers_present`
- `relative_server_url`
- `server_variables_present`
- `operation_server_override`
- `path_server_override`
- `ambiguous_server_profiles`

Generated runner:

- keep current override precedence:

```text
API2AGENT_TOOL_BASE_URL_<TOOL_NAME>
-> API2AGENT_BASE_URL
-> tool.base_url
-> capability.base_url
```

- do not auto-switch profiles in v0
- optionally include server metadata in generated `CAPABILITY` for future profile-aware clients

## Implementation Plan

1. Add additive `ServerVariable` and `ServerConfig` IR models.
2. Add `Capability.servers`, `Tool.servers`, and `Tool.server_source`.
3. Replace first-server-only extraction with normalized server list extraction.
4. Preserve raw `url`, resolved URL, description, variables, source, path, operation id, profile hints, and relative flag.
5. Keep existing selected `base_url` / `tool.base_url` behavior compatible.
6. Update README server section.
7. Update inspect server summaries.
8. Add diagnostics for multi-server and relative/profile cases.
9. Add fixtures and regression tests.
10. Dogfood with local fixtures for multiple document servers, path/operation overrides, variables, and relative servers.

## Tests

Add fixtures for:

- multiple document-level servers with descriptions
- server variables with default and enum
- path-level server override
- operation-level server override
- relative document server URL
- relative path/operation server URL
- regional variable server URL
- no server URL

Regression tests should cover:

- parser preserves all server choices
- selected base URL remains compatible with current behavior
- path/operation selected server still populates `tool.base_url`
- server variables are preserved and default-substituted
- relative server URLs are marked and diagnosed
- README lists server choices and override guidance
- inspect shows server summaries
- runner override precedence remains unchanged
- old capability JSON without server metadata remains valid

## Dogfood

Run local dogfood against:

- existing `servers.yaml`
- a new multi-server fixture
- a relative-server fixture based on Swagger Petstore-style `/api/v3`
- generated runner with default base URL
- generated runner with `API2AGENT_BASE_URL`
- generated runner with `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>`

No network dependency is required.

## Success Metrics

The implementation is successful when:

- generated package metadata exposes all relevant OpenAPI servers
- users can see why a default server was selected
- relative server URLs are explicit and actionable
- staging/sandbox/regional/admin hints are visible but do not change runtime behavior
- existing base URL override tests still pass
- full Python test suite passes

## Acceptance Criteria For This Design

- current server handling baseline and gaps are documented
- additive IR strategy is defined
- deterministic server selection rules are defined
- relative server URL policy is defined
- profile hints are defined as advisory metadata
- generated README, inspect, diagnostics, and runner effects are defined
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
