# Agent Capability Compiler OpenAPI Response Shape Documentation Design v0

Date: 2026-06-01

Status: complete

## Decision

The next OpenAPI hardening implementation slice should be:

```text
Agent Capability Compiler OpenAPI Response Shape Documentation Implementation v0
```

This slice should make OpenAPI response shapes visible and useful in generated Agent capability packages while preserving deterministic offline generation and raw schema compatibility.

It should remain documentation-first. It must not add runtime response validation, SDK type generation, LLM response transformation, workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation.

## Why This Slice Now

The compiler now has stronger request-facing behavior:

- examples/defaults are preserved
- security requirement combinations are documented
- server metadata is visible
- request schema shaping filters read-only fields and preserves write-only fields
- discriminator metadata improves polymorphic request examples and summaries

The remaining asymmetry is response documentation. Generated README and inspect output tell Agents how to call a tool, but they do not yet explain enough about what the API may return.

Real OpenAPI specs often include:

- multiple success status codes
- structured error bodies
- `default` responses
- content-type variants
- response examples
- nullable and polymorphic response payloads
- write-only fields that should not be implied as returned values

Agents need compact, deterministic response guidance to plan calls, inspect failures, and decide whether a provider fits a task.

## Current Baseline

Already present:

- OpenAPI parser extracts `ResponseShape.status_code`, `description`, and application/json `schema`
- `Response.schema_` preserves normalized schema dictionaries
- schema shaping supports response direction summaries
- diagnostics report `write_only_response_fields`
- diagnostics include response schemas in schema hint counts
- `api2agent inspect` includes response schemas in aggregate schema hint counts
- generated runner returns raw HTTP `status_code`, `ok`, `body`, and error metadata

Important gaps:

- generated README does not list response status codes
- generated README does not show response schema summaries
- `api2agent inspect` does not show per-response details
- response content type is not preserved beyond implicit application/json behavior
- response examples and examples maps are not preserved
- success responses and error responses are not grouped or explained
- `default` response semantics are not surfaced
- no diagnostic flags missing response schemas for documented status codes
- no diagnostic calls out APIs with only error schemas or no success schema
- polymorphic response payloads are only indirectly visible through aggregate hint counts

## Goals

- show response status codes in generated README and inspect output
- distinguish success, redirect, client error, server error, and `default` responses
- show compact response schema summaries using existing schema shaping helpers
- show response content type when known
- preserve response examples/default examples when available
- make structured error bodies visible without changing runner behavior
- diagnose missing or ambiguous response documentation
- keep old generated `capability.json` files valid
- keep generation deterministic and offline

## Non-Goals

Do not implement:

- runtime response validation
- runtime response coercion
- LLM-based response transformation
- output normalization beyond existing capability mapping work
- generated SDK classes or response types
- UI response viewers or forms
- full OpenAPI 3.1 JSON Schema dialect support
- content negotiation runtime behavior
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed Compatibility Strategy

Keep the existing response schema source of truth:

```text
Response.schema_
```

Add only optional response metadata if needed:

```text
ResponseShape.content_type: str | None = None
ResponseShape.example: Any | None = None
ResponseShape.examples: list[Any] = []
```

These fields must be additive, derived from OpenAPI response `content`, and safe for old package JSON. Existing packages that only have `status_code`, `description`, and `schema` remain valid.

For v0, response documentation should use helper functions rather than broad IR churn:

```text
response_category(status_code) -> success | redirect | client_error | server_error | default | unknown
format_response_summary(response) -> compact string
response_doc_findings(tool, response) -> diagnostics
```

## Extraction Rules

For each OpenAPI response:

1. preserve `status_code` as a string, including `default`
2. preserve `description` when present
3. prefer `application/json` content when available
4. otherwise select the first content entry deterministically
5. preserve selected content type
6. extract selected content schema when present
7. preserve `example` and `examples` from the selected content object
8. do not merge multiple content types in v0
9. do not validate whether examples match schemas
10. preserve raw schema compatibility through existing schema normalization

If multiple content types exist, the selected one should be documented and a diagnostic can mention that variants were present.

## Response Category Rules

Classify response status codes as:

```text
2xx -> success
3xx -> redirect
4xx -> client_error
5xx -> server_error
default -> default
other -> unknown
```

README and inspect should use these categories for readability, but the generated runner behavior remains unchanged.

## Summary Formatting Rules

README response lines should be compact and bounded:

```text
  - responses:
    - 200 success application/json: object {id:string, name:string?} - OK
    - 400 client_error application/json: object {error:string, code:string?} - Bad request
    - default default application/json: object {message:string} - Error
```

When no schema is present:

```text
    - 204 success: no documented body - No Content
```

When content type is known but schema is absent:

```text
    - 202 success application/json: undocumented schema - Accepted
```

Summaries should use existing schema shaping behavior:

- response direction for response payloads
- nullable display
- map and array summaries
- bounded `oneOf` / `anyOf`
- discriminator-aware polymorphic summaries
- write-only response filtering or marking

## README Effects

Generated README should:

- show a response section under each tool when responses are present
- show status code, category, content type, schema summary, and description
- show source examples in a bounded inline or indented form when short
- avoid implying write-only fields are returned
- identify `default` responses as catch-all documented responses
- keep tool listings readable for large specs by bounding response count per tool

Suggested bound:

- display up to 5 responses per tool
- include an overflow marker when more responses exist
- prefer source order

## Inspect Effects

`api2agent inspect` should:

- show per-tool response summaries beside request details
- continue aggregate schema hint counts
- include response status category counts in a compact form
- preserve machine readability if JSON inspect output is added later

Example:

```text
responses: 200 success application/json object {id:string}; 404 client_error application/json object {error:string}
```

## Diagnostics

Add deterministic findings:

- `response_schema_present`
- `response_example_present`
- `response_without_schema`
- `success_response_without_schema`
- `error_response_schema_present`
- `default_response_present`
- `multiple_response_content_types`
- `response_polymorphic_schema`

Severity guidance:

- informational for present schemas, examples, default responses, and structured error bodies
- warning for success responses without schemas when a body is likely
- informational for `204`/`304` without schemas
- informational or warning for multiple content types depending on whether the selected type is explicit
- informational for polymorphic response payloads unless combined with missing discriminator metadata already covered by discriminator diagnostics

Diagnostics should remain advisory and should not block generation except through existing package quality score semantics.

## Generated Runner Behavior

Generated runner behavior should not change in this slice.

The runner should continue returning:

```text
ok
status_code
body
error
```

Response documentation is for Agent planning and debugging. Runtime validation, coercion, and normalized outputs remain separate product decisions.

## Implementation Plan

1. Extend `ResponseShape` with optional `content_type`, `example`, and `examples` fields.
2. Update OpenAPI response extraction to select and preserve deterministic content metadata.
3. Add response category and response summary helpers.
4. Add README response lines under each tool.
5. Add inspect response detail output.
6. Add diagnostics for missing schemas, examples, default responses, content variants, and response polymorphism.
7. Add fixtures covering success, no-content, error, default, examples, multiple content types, and polymorphic response schemas.
8. Add parser, README/generator, diagnostics, and CLI regression tests.
9. Dogfood generated README, inspect, and diagnose output locally.

## Tests

Add fixtures for:

- `200` JSON success response with schema
- `201` JSON success response with example
- `204` no-body response
- `400` structured error response
- `404` structured error response
- `default` error response
- response with multiple content types
- response with nullable fields
- response with `oneOf` / `anyOf`
- response with discriminator metadata
- response with write-only property

Regression tests should cover:

- old capability JSON without response metadata remains valid
- parser preserves response status, description, schema, selected content type, and examples
- README lists response status categories and schema summaries
- README does not imply write-only response fields are returned
- inspect shows per-tool response details
- diagnostics report missing success response schemas
- diagnostics report structured error response schemas
- diagnostics report default responses and multiple content types
- full Python suite remains green

## Dogfood

Run local dogfood against:

- a new response-shape fixture
- generated README review
- `api2agent inspect`
- `api2agent diagnose`
- generated package execution against a local fixture server only if needed for existing runner compatibility

No network dependency is required.

## Success Metrics

The implementation is successful when:

- generated packages tell Agents what successful responses look like
- structured error bodies are visible before a call fails
- response examples are preserved when available
- `default` and no-body responses are understandable
- response docs reuse existing schema shaping and discriminator improvements
- diagnostics identify sparse or ambiguous response docs
- existing generated runner behavior remains compatible
- full Python test suite passes

## Acceptance Criteria For This Design

- current response documentation baseline and gaps are documented
- additive compatibility strategy is defined
- response extraction rules are defined
- response category and summary formatting rules are defined
- README, inspect, diagnostics, parser, and runner effects are defined
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
