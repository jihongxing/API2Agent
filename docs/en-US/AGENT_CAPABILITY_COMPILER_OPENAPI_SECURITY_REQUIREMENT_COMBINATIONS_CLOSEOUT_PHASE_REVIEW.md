# Agent Capability Compiler OpenAPI Security Requirement Combinations Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler OpenAPI Security Requirement Combinations implementation slice can close.

The compiler now preserves OpenAPI auth semantics well enough for real-world specs that use public overrides, OR alternatives, AND credential groups, query API keys, cookie API keys, and OAuth/OpenID metadata.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Server Handling Design v0
```

The next design should improve server selection and environment/profile hints for specs with multiple document/path/operation servers while preserving runtime base URL override compatibility.

## What Is Now Complete

### Design

Completed:

- documented OpenAPI security OR/AND semantics
- documented current flattening gaps
- defined additive IR metadata for auth schemes and security requirement alternatives
- defined deterministic primary auth selection
- defined bearer/header/query/cookie/OAuth scheme mappings
- defined generated runner, proxy, README, inspect, diagnostics, tests, and dogfood effects
- preserved API-first non-goals

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_DESIGN.md`

### Implementation

Completed:

- additive `AuthConfig` metadata for location, name, scheme name, scopes, source, unsupported reason, and combined credentials
- additive `SecurityAlternative` / `SecurityRequirements` IR models
- `Capability.security_requirements`
- `Tool.security_requirements`
- OpenAPI parser support for OR/AND security requirements
- query and cookie API key parser support
- OAuth/OpenID metadata-only preservation
- generated runner injection for query, cookie, and supported combined auth
- generated runner `unsupported_auth` behavior for selected unsupported auth
- proxy payload additive `credentials` alongside legacy `credential`
- README and `auth.env.example` auth summaries
- inspect auth formatting compatibility for bearer plus location-aware new auth shapes
- diagnostics for alternatives, combined auth, query/cookie API keys, metadata-only OAuth, and unsupported schemes
- regression fixture and tests

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| OpenAPI OR alternatives are preserved in generated metadata | passed |
| OpenAPI AND groups are preserved in generated metadata | passed |
| primary auth selection is deterministic | passed |
| operation-level `security: []` public override works | passed |
| existing bearer/header API key behavior remains compatible | passed |
| query API key direct runner execution works | passed |
| cookie API key direct runner execution works | passed |
| supported combined auth direct runner execution works | passed |
| missing combined auth env vars are reported together | passed |
| OAuth/OpenID is preserved as metadata-only | passed |
| proxy credential intent remains backward compatible | passed |
| diagnostics explain auth alternatives and combined auth | passed |
| README and `auth.env.example` expose new auth shapes | passed |
| old generated package compatibility is preserved | passed |
| no OAuth flow, vault, workflow, marketplace, billing, hosted public CRUD, gateway permission source, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\parsers\curl.py api2agent\generators\package.py api2agent\generators\readme.py api2agent\generators\runner.py api2agent\diagnostics.py api2agent\cli.py
```

Passed:

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_runner_generation.py tests\test_diagnostics.py
```

Result:

```text
46 passed
```

Passed:

```text
pytest
```

Result:

```text
185 passed
```

Passed loopback dogfood for:

- query API key auth
- cookie API key auth
- combined header + query API key auth

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

The compiler now handles a major real-world OpenAPI auth gap without widening API2Agent into hosted credential management or OAuth runtime behavior.

This gives generated packages better auth correctness while preserving the old simple `auth` surface for existing consumers.

## Remaining Risks

### Multi-Credential Proxy Execution Needs Deeper Product Semantics

Generated proxy payloads now expose additive `credentials`, but production-grade multi-credential resolution still needs Control Plane and credential policy semantics before hosted usage.

### OAuth Is Metadata-Only

This is intentional. OAuth flows, refresh, consent, and hosted token lifecycle remain out of scope. Generated packages should not imply OAuth automation.

### API Key Env Naming Is Still Coarse

Multiple API key schemes in one spec may share the same generated env name. This is acceptable for v0 compatibility, but future implementation may need per-scheme env naming when distinct secrets are required.

### Real Specs May Combine Auth With Complex Server Layouts

Auth correctness is improved, but many real specs also depend on multiple servers, staging/prod URLs, regional URLs, and operation-level server choices. Server handling is now the next obvious onboarding gap.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Server Handling Design v0
```

That design should define how document/path/operation servers, server variables, multiple server choices, environment/profile hints, and runtime base URL overrides should appear in IR, README, diagnostics, and generated runner behavior.
