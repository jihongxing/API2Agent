# Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Design v0

Date: 2026-06-01

Status: complete

## Decision

The next OpenAPI hardening implementation slice should be:

```text
Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Implementation v0
```

This slice should add bounded, high-signal JSON Schema/OpenAPI keyword awareness to Agent-facing summaries, examples, inspect output, and diagnostics while preserving raw schema compatibility and deterministic offline generation.

It must not become a full JSON Schema validator, OpenAPI 3.1 dialect engine, runtime schema validator/coercer, generated SDK type system, UI form renderer, workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation.

## Why This Slice Now

The compiler now has the main OpenAPI hardening surfaces in place:

- examples/defaults propagation
- security requirement combinations
- server metadata handling
- request/response schema shaping
- discriminator-aware polymorphic summaries and examples
- response shape documentation
- inspect and diagnostics visibility

The remaining high-friction schema gap is keyword-level constraint visibility. Real OpenAPI specs often encode important Agent instructions in schema keywords:

- `format: email`, `uri`, `uuid`, `date`, `date-time`
- `pattern`
- `minLength`, `maxLength`
- `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`
- `minItems`, `maxItems`, `uniqueItems`
- `const`
- `deprecated`
- `dependentRequired`, `if` / `then` / `else`, `not`, `patternProperties`

Today many of these are preserved in raw schemas but not surfaced in generated summaries, examples, or diagnostics. Agents can miss constraints that would prevent failed first calls.

## Current Baseline

Already present:

- parser preserves unknown schema keys in normalized dictionaries
- `enum`, `default`, and `example` influence generated examples
- `const` is used only indirectly for discriminator branch tag selection
- nullable, readOnly/writeOnly, map, array, object, required/optional, `oneOf` / `anyOf`, discriminator, and response summaries are visible
- diagnostics report broad schema shape issues and discriminator/response documentation issues
- generated OpenAI tool schemas preserve raw shaped schema dictionaries

Important gaps:

- `format` is not displayed or used for examples
- string length and regex constraints are invisible
- numeric bounds are invisible
- array cardinality and uniqueness are invisible
- `const` is not summarized as a field constraint
- `deprecated` fields are not marked
- conditional/dependent schemas are not diagnosed
- unsupported high-complexity keywords are not called out
- Agent-facing summaries cannot distinguish a generic string from an email/uuid/date string

## Goals

- make common schema constraints visible in README and inspect summaries
- improve deterministic examples for common formats without validation
- preserve raw schema compatibility
- keep generated OpenAI tool schemas compatible with existing shaping
- diagnose unsupported or complex JSON Schema keywords that may confuse Agents
- avoid generating invalid-looking examples when simple keyword facts are available
- keep summaries bounded and readable
- keep generation deterministic and offline

## Non-Goals

Do not implement:

- full JSON Schema validation
- complete OpenAPI 3.1 dialect support
- runtime request or response validation
- runtime coercion
- LLM-based schema simplification
- generated SDK types or tagged unions
- UI form rendering
- content negotiation
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Keyword Tiers

### Tier 1: Display And Simple Example Hints

Implement readable summaries and deterministic example hints for:

- `format`
- `pattern`
- `minLength`
- `maxLength`
- `minimum`
- `maximum`
- `exclusiveMinimum`
- `exclusiveMaximum`
- `minItems`
- `maxItems`
- `uniqueItems`
- `const`
- `deprecated`

These are common, compact, and directly useful for Agent prompting.

### Tier 2: Diagnostics-Only In v0

Preserve and diagnose, but do not attempt semantic display or example generation for:

- `multipleOf`
- `minProperties`
- `maxProperties`
- `patternProperties`
- `propertyNames`
- `dependentRequired`
- `dependentSchemas`
- `if`
- `then`
- `else`
- `not`
- `contains`
- `minContains`
- `maxContains`
- `unevaluatedProperties`
- `unevaluatedItems`

These can affect validation deeply and should not be half-implemented as if the compiler were a validator.

## Compatibility Strategy

Keep existing raw schema fields as the source of truth:

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

Do not add required IR fields. Prefer helper functions that derive keyword facts from raw schema dictionaries:

```text
schema_keyword_markers(schema) -> list[str]
schema_keyword_hint_counts(schema) -> dict[str, int]
schema_paths_with_keyword(schema, keyword) -> list[str]
```

Generated `capability.json` remains backward compatible because existing schema dictionaries stay intact.

## Summary Formatting Rules

Keep compact summaries readable:

```text
email:string format=email maxLength=254
id:string format=uuid
age:integer min=0 max=150
code:string pattern=^[A-Z]{3}-\d{4}$
tags:array[string] minItems=1 maxItems=5 uniqueItems
status:string const=active
old_field:string deprecated?
```

Rules:

- use short aliases such as `min`, `max`, `minLength`, `maxLength`
- show `exclusiveMinimum` / `exclusiveMaximum` as `exclusiveMin` / `exclusiveMax`
- truncate long `pattern` values
- show `deprecated` as a marker
- do not show every keyword when output becomes too long
- preserve existing nullable/readOnly/writeOnly/required/optional markers
- preserve existing `oneOf` / `anyOf` / discriminator summaries

## Example Generation Rules

Use keyword hints only when no explicit example, examples map, default, enum, or const is already available.

Suggested deterministic examples:

| Keyword | Example behavior |
| --- | --- |
| `const` | use const value |
| `format: email` | `user@example.com` |
| `format: uri` / `url` | `https://example.com` |
| `format: uuid` | `00000000-0000-4000-8000-000000000000` |
| `format: date` | `2026-01-01` |
| `format: date-time` | `2026-01-01T00:00:00Z` |
| `format: hostname` | `example.com` |
| numeric `minimum` / `maximum` | choose a simple in-range value when possible |
| `minLength` | pad the generic string to the minimum length when small |
| `minItems` | emit up to a small bounded number of item examples |

Do not synthesize regex-matching strings from arbitrary `pattern` values in v0. Patterns should be displayed and diagnosed, not interpreted.

## README And Inspect Effects

README and `api2agent inspect` should:

- show common string formats
- show bounded string and numeric constraints
- show array min/max/unique constraints
- show const values
- mark deprecated fields or parameters
- keep object summaries bounded
- keep response/request direction shaping intact
- keep discriminator and response summaries intact

## OpenAI Tool Schema Effects

Generated OpenAI tool schemas should:

- preserve raw keyword metadata after request-direction shaping
- keep `readOnly` request filtering and `writeOnly` request preservation
- keep discriminator metadata
- avoid flattening or rewriting keyword constraints into descriptions
- avoid dropping constraints that downstream tool consumers may understand

## Diagnostics

Add deterministic findings:

- `schema_keywords_present`
- `string_constraints_present`
- `numeric_constraints_present`
- `array_constraints_present`
- `const_schema_present`
- `deprecated_schema_fields`
- `pattern_schema_present`
- `unsupported_schema_keywords_present`
- `conditional_schema_present`
- `dependent_schema_present`

Severity guidance:

- informational for visible Tier 1 keywords
- informational for `deprecated` fields unless they are required request inputs
- warning for required deprecated request inputs
- informational for Tier 2 unsupported keywords
- warning for conditional/dependent schemas in request bodies because examples may not capture full validity semantics

Diagnostics remain advisory and should not block generation except through existing package quality score semantics.

## Implementation Plan

1. Add keyword detection helpers to `api2agent/schema_shaping.py` or a small sibling helper module.
2. Extend compact schema summaries with bounded Tier 1 keyword markers.
3. Extend example generation with deterministic format/const/simple-bound hints.
4. Preserve OpenAI tool schema compatibility through existing shaped schema paths.
5. Add schema hint counts for keyword categories.
6. Add diagnostics for Tier 1/Tier 2 keyword presence and risky combinations.
7. Add an OpenAPI fixture covering string, numeric, array, const, deprecated, and conditional/dependent schemas.
8. Add parser, generator, diagnostics, and CLI regression tests.
9. Dogfood generated README, inspect, diagnose, and manual examples locally.

## Tests

Add fixtures for:

- `format: email`, `uri`, `uuid`, `date`, `date-time`
- `pattern`
- `minLength` and `maxLength`
- numeric minimum/maximum and exclusive bounds
- array minItems/maxItems/uniqueItems
- `const`
- deprecated fields and parameters
- required deprecated request field
- conditional schemas (`if` / `then` / `else`)
- dependent schemas or dependent required
- patternProperties

Regression tests should cover:

- parser preserves raw keyword metadata
- README summaries show keyword markers
- generated examples use const and common format examples
- generated examples prefer explicit examples/defaults/enums over keyword hints
- inspect shows keyword hint counts and summaries
- diagnostics report Tier 1 and Tier 2 keyword findings
- OpenAI tool schemas preserve keyword metadata after request shaping
- old capability JSON without keyword-specific metadata remains valid

## Dogfood

Run local dogfood against:

- a new JSON Schema keyword fixture
- generated README review
- `api2agent inspect`
- `api2agent diagnose`
- generated manual write examples

No network dependency is required.

## Success Metrics

The implementation is successful when:

- common schema constraints are visible in generated docs
- common format examples are more realistic
- complex unsupported keyword semantics are diagnosed rather than silently ignored
- generated tool schemas preserve source keyword metadata
- existing schema shaping, discriminator, and response documentation behavior remains compatible
- full Python test suite passes

## Acceptance Criteria For This Design

- current keyword coverage baseline and gaps are documented
- Tier 1 and Tier 2 keyword scopes are defined
- compatibility strategy is defined
- summary formatting rules are defined
- example generation rules are defined
- README, inspect, OpenAI tool schema, and diagnostics effects are defined
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
