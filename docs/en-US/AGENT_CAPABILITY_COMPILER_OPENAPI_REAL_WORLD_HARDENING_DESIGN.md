# Agent Capability Compiler OpenAPI Real-World Hardening Design v0

Date: 2026-06-01

Status: complete

## Decision

Start OpenAPI real-world hardening with:

```text
Agent Capability Compiler OpenAPI Examples + Defaults Propagation v0
```

This is the first implementation slice because it directly reduces the gap between generated package and first successful Agent/API call. Real OpenAPI specs often contain usable examples, defaults, enums, and request-body examples, but the compiler does not yet consistently preserve them into generated test params, README examples, and diagnostics evidence.

The broader OpenAPI hardening track remains API-first and does not introduce workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation.

## Why This Slice First

Quality diagnostics now tells users when generated packages are risky, vague, or missing useful metadata. The next compiler improvement should turn source OpenAPI metadata into better generated artifacts.

Examples/defaults are high leverage because they affect:

- generated README first-call commands
- `api2agent test . --tool ... --params ...`
- smoke/manual write test usefulness
- diagnostics findings for required parameters
- onboarding time for real APIs with required path/query/header/body inputs

## Current Parser Baseline

Already present:

- OpenAPI file parsing
- local `$ref` resolution
- `allOf` object merge
- `oneOf` / `anyOf` preservation
- document/path/operation server URL handling
- server variable default substitution
- document and endpoint-level auth inference
- path/query/header parameter extraction
- JSON and first available request body content extraction
- response schema extraction
- tag/path/operation/max-tools filtering during parse

Important gaps:

- parameter-level `example` and `examples` are not promoted into generated params
- request body media examples are not promoted into generated params
- schema `example`, `examples`, `default`, and `enum` intent is not consistently surfaced
- nested object examples are not used to improve body params
- diagnostics cannot yet distinguish "required but no example/default" from "required and source provided good sample data"
- filtering diagnostics do not yet explain why a real spec still produced too many Agent tools

## Goals

- preserve useful OpenAPI examples/defaults in the IR without breaking existing generated package contracts
- improve generated README and test params for required path/query/header/body inputs
- reduce generic `"example"` placeholder usage when source examples exist
- feed diagnostics with better evidence about whether required inputs have usable sample values
- keep all changes deterministic and offline

## Non-Goals

Do not implement:

- real API execution during generation
- LLM-based schema interpretation
- workflow composition
- non-API adapters
- provider marketplace submission
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- production gateway permission source
- automatic snapshot publish/reload

## First Implementation Slice

Recommended next task:

```text
Agent Capability Compiler OpenAPI Examples + Defaults Propagation v0
```

### Source Fields To Preserve

For parameters:

- `parameter.example`
- `parameter.examples`
- `parameter.schema.default`
- `parameter.schema.example`
- `parameter.schema.examples`
- first `parameter.schema.enum` value as a fallback

For request bodies:

- `requestBody.content[content-type].example`
- `requestBody.content[content-type].examples`
- `requestBody.content[content-type].schema.default`
- `requestBody.content[content-type].schema.example`
- `requestBody.content[content-type].schema.examples`
- object property defaults/examples
- first enum value for required scalar properties as a fallback

### IR Strategy

Keep the existing `Capability` / `Tool` shape backward compatible.

Recommended additive model changes:

- add `example: Any | None` to `Parameter`
- add `examples: list[Any]` to `Parameter`
- add `example: Any | None` to `RequestBody`
- add `examples: list[Any]` to `RequestBody`

Existing generated `capability.json` readers should keep working because these fields are additive.

### Example Selection Order

Parameter example value:

1. explicit `parameter.example`
2. first value from `parameter.examples`
3. `schema.default`
4. `schema.example`
5. first value from `schema.examples`
6. first scalar from `schema.enum`
7. existing type-based fallback

Request body example value:

1. media `example`
2. first value from media `examples`
3. schema `default`
4. schema `example`
5. first value from schema `examples`
6. object built from required properties using property defaults/examples/enums
7. existing type-based fallback

### Generated Artifact Effects

Generated README:

- first-call params should use preserved examples/defaults
- parameter/body details should show default/example when useful

Generated smoke/manual tests:

- should use better example params for selected tool calls
- should not execute write/delete tests without explicit opt-in

Diagnostics:

- required parameters with example/default should not trigger noisy missing-example findings in later diagnostics expansion
- required parameters without source sample data can remain informational findings

## Later OpenAPI Hardening Tracks

### Security Requirement Combinations

Design later:

- multiple security requirements
- OR vs AND requirement semantics
- query apiKey auth
- cookie apiKey auth
- OAuth scopes as metadata only
- per-tool auth summaries in diagnostics and README

### Server Handling

Design later:

- multiple server choices in generated metadata
- environment/profile hinting for staging/prod/regional servers
- clearer operation-level server summaries
- safer handling of relative server URLs

### Schema Shaping

Design later:

- `nullable`
- `readOnly` / `writeOnly`
- `additionalProperties`
- `array` examples
- nested `oneOf` / `anyOf` readability
- required-vs-optional object shaping for Agent-facing inputs

### Filtering Diagnostics

Design later:

- explain unmatched filters
- summarize top tags/path prefixes before generation
- recommend filters for oversized packages
- persist generation context into diagnostics

## Tests

Implementation should add fixtures and tests for:

- parameter `example`
- parameter `examples`
- schema `default`
- schema `example`
- schema `enum`
- request body media `example`
- request body media `examples`
- nested object property examples/defaults
- generated README first-call params use source examples
- generated smoke/manual tests preserve safe write behavior
- old capability JSON without example fields remains valid

## Dogfood

Run local dogfood against:

- existing `basic.yaml`
- an examples/defaults fixture
- a mixed-auth fixture to ensure auth behavior is unchanged
- a curl-derived package to ensure curl generation is unaffected

If a safe real OpenAPI fixture is available locally, run:

```text
api2agent generate real-openapi.yaml --include-path <safe-read-path> --output tmp/openapi-hardening
api2agent diagnose tmp/openapi-hardening
api2agent test tmp/openapi-hardening --tool <safe-read-tool> --params '<generated-example-params>'
```

No network dependency is required for the implementation tests.

## Success Metrics

The implementation is successful when:

- generated first-call examples use source OpenAPI examples/defaults where present
- required parameter/body examples become less generic
- existing parser behavior for refs, servers, auth, filters, and safety remains compatible
- diagnostics and README become more useful without becoming noisy
- full Python test suite passes

## Acceptance Criteria For This Design

- first OpenAPI hardening implementation slice is selected
- current parser baseline and gaps are documented
- example/default source fields are specified
- additive IR changes are specified
- example selection order is deterministic
- generated artifact effects are specified
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
