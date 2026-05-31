# Agent Capability Compiler OpenAPI Security Requirement Combinations Design v0

Date: 2026-06-01

Status: complete

## Decision

The next OpenAPI hardening implementation slice should be:

```text
Agent Capability Compiler OpenAPI Security Requirement Combinations Implementation v0
```

This slice should preserve OpenAPI security requirement semantics instead of flattening them to the first recognized scheme.

It should remain API-first and must not add OAuth browser flows, hosted credential vaults, workflow runtime, marketplace/provider onboarding, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation.

## Why This Slice Now

Examples/defaults propagation made generated first calls more usable. The next real-world OpenAPI blocker is auth correctness.

Many specs use:

- OR alternatives: `security: [{ bearerAuth: [] }, { apiKeyAuth: [] }]`
- AND requirements: `security: [{ apiKeyHeader: [], apiKeyQuery: [] }]`
- public operation overrides: `security: []`
- API keys in `query` or `cookie`
- OAuth/OpenID scopes as descriptive metadata

The current parser chooses the first recognized scheme from the first usable requirement. That is deterministic, but it loses whether auth is optional, alternative, combined, or unsupported.

## Current Baseline

Already present:

- document-level `security`
- operation-level `security` override
- bearer HTTP auth mapped to `AuthConfig(type="bearer", header="Authorization")`
- header API key mapped to `AuthConfig(type="api_key", header=<header name>)`
- public operation override via `security: []`
- generated runner env-backed bearer/header injection
- proxy credential intent for bearer/header API key
- README and `auth.env.example` for env names
- diagnostics findings for unknown auth and missing env names
- mixed-auth summary when tools have auth overrides

Important gaps:

- OR alternatives are flattened to one selected scheme
- AND requirements with multiple schemes are flattened to one selected scheme
- query API keys are treated as unknown
- cookie API keys are treated as unknown
- OAuth/OpenID scopes are not preserved as metadata
- diagnostics cannot explain why a spec has optional/alternative/combined auth
- README cannot summarize auth alternatives or combined credentials
- generated runner cannot inject multiple auth credentials for one operation

## OpenAPI Security Semantics

OpenAPI `security` is an array of Security Requirement Objects:

- the outer array is OR
- each object is AND across scheme names
- an empty object `{}` means anonymous access is one allowed alternative
- an empty array `[]` means no auth is required for that scope
- operation-level `security` overrides document-level `security`
- absent operation-level `security` inherits document-level `security`

This design should preserve those semantics in generated package metadata even when the runner can only execute a subset.

## Goals

- preserve OR/AND security requirement structure in the IR
- keep existing single `auth` behavior compatible for old consumers
- support header API key, query API key, cookie API key, and bearer token execution where deterministic
- support combined AND credentials for generated runner and proxy intent when all schemes are env-backed and supported
- preserve OAuth/OpenID scopes as metadata only
- improve README, `auth.env.example`, inspect, and diagnostics auth summaries
- keep generation deterministic and offline

## Non-Goals

Do not implement:

- OAuth authorization-code/device/browser flows
- token refresh
- hosted credential vault writes
- production gateway permission source
- user/project permission issuance
- workflow composition
- marketplace/provider onboarding
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed IR Strategy

Keep current `Capability.auth` and `Tool.auth` as the backward-compatible primary executable auth surface.

Add new metadata that preserves full OpenAPI security structure:

```text
AuthConfig.location: "header" | "query" | "cookie" | "authorization" | "unknown" | null
AuthConfig.name: original header/query/cookie parameter name, when applicable
AuthConfig.scheme_name: OpenAPI security scheme key
AuthConfig.scopes: list[str]
AuthConfig.source: "openapi" | "curl" | "manual" | null
AuthConfig.unsupported_reason: string | null

SecurityRequirement.alternatives:
  - each alternative is one AND group
  - each group contains one or more AuthConfig-like scheme records
  - an empty group represents anonymous access

Capability.security_requirements
Tool.security_requirements
```

`auth` remains the primary selected execution plan:

- `none` when no auth is required
- a single supported scheme when the selected requirement has one scheme
- a combined supported requirement when implementation adds multi-credential runner support
- `unknown` when the only requirements are unsupported

The generated `capability.json` remains additive: old packages do not need `security_requirements`, and old consumers can continue reading `auth`.

## Primary Auth Selection

Select the primary executable auth deterministically:

1. if security is absent, inherit parent scope
2. if security is `[]`, select `none`
3. if any alternative is anonymous `{}`, select `none` and preserve other alternatives in metadata
4. prefer the first fully supported alternative in source order
5. a fully supported alternative may contain:
   - bearer HTTP token
   - header API key
   - query API key
   - cookie API key
6. if no fully supported alternative exists, preserve all alternatives and select `unknown`

This keeps behavior predictable while making the lost semantics visible.

## Scheme Mapping

### Bearer

OpenAPI:

```yaml
type: http
scheme: bearer
```

Execution mapping:

- location: `authorization`
- name/header: `Authorization`
- env: `<CAPABILITY>_API_TOKEN`
- injection: `Authorization: Bearer <token>`

### Header API Key

OpenAPI:

```yaml
type: apiKey
in: header
name: X-API-Key
```

Execution mapping:

- location: `header`
- name/header: `X-API-Key`
- env: `<CAPABILITY>_API_KEY`
- injection: `X-API-Key: <token>`

### Query API Key

OpenAPI:

```yaml
type: apiKey
in: query
name: api_key
```

Execution mapping:

- location: `query`
- name: `api_key`
- env: `<CAPABILITY>_API_KEY`
- injection: query parameter `api_key=<token>`

### Cookie API Key

OpenAPI:

```yaml
type: apiKey
in: cookie
name: session
```

Execution mapping:

- location: `cookie`
- name: `session`
- env: `<CAPABILITY>_API_KEY`
- injection: `Cookie: session=<token>`

Cookie support should be conservative and mark generated README guidance clearly because cookie auth may require additional cookie attributes that OpenAPI does not describe.

### OAuth2 / OpenID Connect

Execution mapping:

- preserve scheme name, type, flows, scopes, and description as metadata
- do not generate OAuth flows
- do not claim direct runner execution support
- diagnostics should report metadata-only OAuth auth

## Generated Runner Behavior

The runner should support:

- no auth
- bearer header injection
- header API key injection
- query API key injection
- cookie API key injection
- AND groups when every required scheme is supported and has an env name

For OR alternatives, the runner should execute the selected primary alternative only. README and diagnostics should make the selection visible.

If a selected AND group has missing env vars, the runner should report all missing auth env names together.

If only unsupported alternatives exist, the runner should fail with `unsupported_auth` instead of silently calling without auth.

## Proxy Credential Intent

Proxy payloads should keep the existing single `credential` field for old behavior.

Additive future shape:

```text
credentials: [
  {
    credential_id,
    owner_type,
    owner_id,
    provider_id,
    auth_type,
    injection_mode,
    injection_name,
    source,
    secret_ref
  }
]
```

For single-scheme auth, both old `credential` and new `credentials[0]` may be emitted during a compatibility window.

For AND groups, emit `credentials` with all required supported credentials. If the local proxy does not yet support multi-credential intent, direct runner support can ship first and proxy behavior should be documented as a remaining gap.

## Generated Artifact Effects

README:

- summarize package default auth
- summarize per-tool overrides
- show selected primary alternative
- show auth alternatives when OR exists
- show combined credentials when AND exists
- show OAuth/OpenID as metadata-only

`auth.env.example`:

- include all env vars needed by selected executable alternatives
- include comments for metadata-only unsupported schemes
- avoid duplicate env names

`inspect`:

- show compact auth summary
- show when auth is optional, alternative, combined, or unsupported

Diagnostics:

- `auth_alternatives_present`
- `combined_auth_required`
- `unsupported_auth_scheme`
- `metadata_only_oauth`
- `query_api_key_auth`
- `cookie_api_key_auth`
- `auth_env_missing` should include all missing env vars for a selected combined requirement

## Implementation Plan

1. Add additive IR metadata for auth scheme location/name/scheme/scopes and security requirement alternatives.
2. Extend OpenAPI security scheme extraction for header/query/cookie API keys and OAuth/OpenID metadata.
3. Parse document and operation security into preserved OR/AND requirement metadata.
4. Keep `Capability.auth` / `Tool.auth` populated with the selected primary executable plan.
5. Extend runner auth injection for query and cookie API keys.
6. Extend runner auth handling for selected AND groups when all schemes are supported.
7. Extend proxy credential intent only as far as the local proxy can safely support; document any remaining multi-credential proxy gap.
8. Update README, `auth.env.example`, inspect, and diagnostics summaries.
9. Add fixtures and regression tests.
10. Dogfood with local loopback targets for header/query/cookie and combined auth.

## Tests

Add fixtures for:

- document-level bearer auth inherited by operations
- operation-level `security: []` public override
- OR auth alternatives with bearer or header API key
- AND auth requiring header API key plus query API key
- query API key only
- cookie API key only
- OAuth2 scopes metadata-only
- unsupported scheme only
- mixed public/authenticated operations

Regression tests should cover:

- parser preserves OR/AND requirement metadata
- primary auth selection is deterministic
- generated runner injects query API key
- generated runner injects cookie API key
- generated runner injects all supported credentials for an AND group
- generated runner reports all missing auth env vars for combined auth
- README and `auth.env.example` summarize alternatives and combined auth
- diagnostics report auth combinations without blocking generation
- old capability JSON without new security metadata remains valid

## Dogfood

Use local loopback HTTP targets, not external APIs, for deterministic auth assertions:

- bearer request includes `Authorization`
- header API key request includes configured header
- query API key request includes configured query parameter
- cookie API key request includes `Cookie`
- combined auth request includes all required credentials
- public override sends no auth

Also rerun mixed-auth existing fixture tests to ensure current endpoint-level behavior remains compatible.

## Success Metrics

The implementation is successful when:

- OR/AND security requirements are visible in generated package metadata
- generated direct runner can execute supported single and combined auth requirements
- query and cookie API keys are no longer classified as unknown
- OAuth/OpenID scopes are preserved but not executed as OAuth flows
- README, inspect, and diagnostics explain auth shape clearly
- old generated package compatibility is preserved
- full Python test suite passes

## Acceptance Criteria For This Design

- OpenAPI security OR/AND semantics are documented
- current parser baseline and flattening gaps are documented
- additive IR strategy is defined
- primary auth selection order is deterministic
- scheme mappings are defined for bearer, header API key, query API key, cookie API key, and OAuth/OpenID metadata
- generated runner/proxy artifact effects are defined
- diagnostics, README, inspect, and `auth.env.example` effects are defined
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
