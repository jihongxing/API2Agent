# Agent Capability Compiler OpenAPI Security Requirement Combinations Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI security requirement combinations are implemented for the Agent capability compiler.

Generated packages now preserve OpenAPI OR/AND security requirement structure as additive metadata while keeping the existing `auth` field as the primary executable compatibility surface.

The implementation supports:

- document-level auth inheritance
- operation-level public override with `security: []`
- OR auth alternatives preserved in metadata
- AND auth requirements preserved and executable when every scheme is supported
- bearer auth
- header API key auth
- query API key auth
- cookie API key auth
- OAuth/OpenID metadata-only preservation
- README, `auth.env.example`, inspect, proxy intent, runner, and diagnostics updates

No OAuth browser flow, token refresh, credential vault, workflow runtime, marketplace/provider onboarding, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation was added.

## Files

Implementation:

- `api2agent/ir/models.py`
- `api2agent/parsers/openapi.py`
- `api2agent/parsers/curl.py`
- `api2agent/generators/runner.py`
- `api2agent/generators/package.py`
- `api2agent/generators/readme.py`
- `api2agent/diagnostics.py`
- `api2agent/cli.py`

Tests and fixtures:

- `tests/fixtures/openapi/security_combinations.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_runner_generation.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`

## Contract

The IR additions are additive:

- `AuthConfig.location`
- `AuthConfig.name`
- `AuthConfig.scheme_name`
- `AuthConfig.scopes`
- `AuthConfig.source`
- `AuthConfig.unsupported_reason`
- `AuthConfig.credentials`
- `SecurityAlternative`
- `SecurityRequirements`
- `Capability.security_requirements`
- `Tool.security_requirements`

Existing generated package consumers can keep reading:

```text
Capability.auth
Tool.auth
```

New consumers can inspect:

```text
security_requirements.alternatives
```

Each alternative represents one OpenAPI OR branch. Each alternative's schemes represent the AND group for that branch. An empty alternatives list represents `security: []`.

## Parser Behavior

Supported executable schemes:

- bearer HTTP auth -> `Authorization: Bearer <token>`
- header API key -> configured header
- query API key -> configured query parameter
- cookie API key -> `Cookie: name=<token>`

Metadata-only schemes:

- OAuth2
- OpenID Connect
- unsupported or missing referenced schemes

Primary auth selection is deterministic:

1. inherit parent when operation security is absent
2. `security: []` selects `none`
3. anonymous `{}` alternative selects `none`
4. first fully supported alternative in source order is selected
5. combined alternatives are selected when every scheme is supported
6. otherwise `unknown` is selected and unsupported metadata is preserved

## Generated Runner Behavior

Direct runner execution now supports:

- bearer header injection
- header API key injection
- query API key injection
- cookie API key injection
- combined AND injection for supported schemes
- reporting all missing env vars for combined auth
- `unsupported_auth` for selected unsupported metadata-only auth

Proxy mode now emits additive `credentials` alongside the legacy `credential` field when auth credential intent exists.

## Generated Artifact Effects

`auth.env.example` now includes env vars from combined credentials without duplicates.

README auth labels now include location/name details:

```text
auth: api_key via query:api_key env=SECURITY_COMBINATIONS_API_API_KEY
auth: api_key via cookie:session env=SECURITY_COMBINATIONS_API_API_KEY
auth: combined api_key via header:X-API-Key env=SECURITY_COMBINATIONS_API_API_KEY + api_key via query:api_key env=SECURITY_COMBINATIONS_API_API_KEY
```

`api2agent inspect` preserves the old bearer display while adding location-aware formatting for new auth shapes.

Diagnostics now report:

- `auth_alternatives_present`
- `combined_auth_required`
- `query_api_key_auth`
- `cookie_api_key_auth`
- `metadata_only_oauth`
- `unsupported_auth_scheme`

## Dogfood Evidence

Generated package:

```text
python -m api2agent.cli generate tests\fixtures\openapi\security_combinations.yaml --output tmp\openapi-security-combinations --force
```

Observed:

```text
Generated capability package: tmp\openapi-security-combinations
Diagnostics: warn score=30 errors=0 warnings=6 info=9
```

Loopback direct runner dogfood passed:

```text
api2agent test tmp\openapi-security-combinations --tool get_query_auth --params '{}'
api2agent test tmp\openapi-security-combinations --tool get_cookie_auth --params '{}'
api2agent test tmp\openapi-security-combinations --tool get_combined_auth --params '{}'
```

Observed results:

```text
/query?api_key=combo-secret
Cookie: session=combo-secret
/combined?api_key=combo-secret with X-API-Key: combo-secret
```

## Compatibility

Compatibility is preserved:

- old packages without `security_requirements` still validate
- existing bearer/header API key auth behavior remains compatible
- existing `credential` proxy payload field remains present
- query/cookie/combined auth is additive
- OAuth/OpenID is metadata-only and does not trigger new OAuth runtime behavior

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

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Security Requirement Combinations Closeout + Phase Review v0
```

The closeout should decide whether this auth hardening slice can close and whether the next OpenAPI hardening target should be server handling, schema shaping, or filtering diagnostics.
