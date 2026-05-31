# Agent Capability Compiler OpenAPI Schema Shaping Design v0

Date: 2026-06-01

Status: complete

## Decision

The next OpenAPI hardening implementation slice should be:

```text
Agent Capability Compiler OpenAPI Schema Shaping Implementation v0
```

This slice should improve how OpenAPI request and response schemas are normalized, displayed, and turned into Agent-facing input examples without becoming a full JSON Schema compiler.

It should remain API-first and must not add workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation.

## Why This Slice Now

The compiler now preserves examples/defaults, security requirement combinations, and server metadata. The next real-spec onboarding gap is schema clarity.

Real OpenAPI specs often include:

- OpenAPI 3.0 `nullable: true`
- OpenAPI 3.1 `type: ["string", "null"]`
- `readOnly` server-generated fields in request body schemas
- `writeOnly` secrets in response schemas
- dictionary objects through `additionalProperties`
- arrays with nested object or polymorphic item schemas
- nested `oneOf` / `anyOf` branches
- large objects where required and optional fields are hard to distinguish

Current generation keeps many raw schema details, but the generated README, tool schemas, examples, diagnostics, and inspect output do not yet make these shapes clear enough for reliable Agent use.

## Current Baseline

Already present:

- local `$ref` resolution
- recursive schema normalization
- `allOf` object merge
- `oneOf` and `anyOf` preservation
- parameter, request body, and response schemas use normalized schema dictionaries
- README schema summaries for object, array, `oneOf`, `anyOf`, scalar type, and default
- generated examples prefer explicit examples, defaults, and enums
- required-only request body examples for object schemas
- diagnostics for broad object schemas and required bodies without schemas

Important gaps:

- OpenAPI 3.0 `nullable` is not displayed as nullable input/output information
- OpenAPI 3.1 type arrays are not summarized consistently
- request examples and tool schemas may include `readOnly` server-generated fields
- response summaries may expose `writeOnly` fields without context
- dictionary objects are shown as broad objects instead of map semantics
- array item details are shallow in README and examples
- nested `oneOf` / `anyOf` can become hard to read
- required versus optional object properties are not visible in compact schema summaries
- diagnostics do not call out schema complexity patterns that commonly confuse Agents

## Goals

- make Agent-facing request input schemas clearer and less likely to ask for server-generated fields
- preserve backward compatibility for existing generated `capability.json`
- keep raw schema dictionaries additive and compatible where possible
- normalize nullable forms into readable metadata without losing OpenAPI 3.0 or 3.1 intent
- treat `readOnly` and `writeOnly` according to request/response direction
- show dictionary/map semantics from `additionalProperties`
- improve array item display and generated examples
- improve nested `oneOf` / `anyOf` readability in README and inspect
- make required and optional object fields visible in compact summaries
- add deterministic diagnostics for schema shapes that need user attention
- keep generation deterministic and offline

## Non-Goals

Do not implement:

- a full JSON Schema validator
- complete OpenAPI 3.1 JSON Schema dialect support
- LLM-based schema simplification
- runtime schema coercion
- generated UI form rendering
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed IR Strategy

Keep existing schema fields:

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

Add only optional shaped metadata if the implementation needs it:

```text
SchemaAnnotations:
  nullable: bool
  read_only_fields: list[str]
  write_only_fields: list[str]
  map_fields: list[str]
  polymorphic_paths: list[str]
  array_without_items: list[str]
  required_fields: list[str]
  optional_fields: list[str]

RequestBody.input_schema: dict | None
Response.output_schema: dict | None
```

The v0 implementation should prefer helper functions over broad IR churn. If `input_schema` or `output_schema` are added, they must be additive and derived from the existing normalized schema.

Generated `capability.json` remains backward compatible because existing `schema` fields stay intact. Old consumers can continue reading the current schema dictionaries.

## Shaping Rules

Schema shaping should be context-aware:

```text
request input schema
response output schema
neutral documentation schema
```

For request input schemas:

1. preserve `writeOnly` fields because clients may need to send secrets
2. omit or clearly mark `readOnly` fields so Agents do not ask users for server-generated values
3. keep required fields after read-only filtering deterministic
4. keep nullable fields visible in summaries and examples
5. preserve `additionalProperties` as map semantics

For response output schemas:

1. preserve `readOnly` fields because server-generated values are expected
2. omit or clearly mark `writeOnly` fields where response summaries would otherwise imply returned secrets
3. keep nullable fields visible in summaries
4. preserve map and polymorphic semantics

For neutral documentation schemas:

1. show both `readOnly` and `writeOnly` markers when present
2. show required versus optional properties
3. keep nested polymorphic branches readable and bounded

## Nullable Policy

OpenAPI 3.0:

```yaml
type: string
nullable: true
```

OpenAPI 3.1:

```yaml
type:
  - string
  - "null"
```

Both should be displayed as nullable in generated documentation and inspect output. The implementation should not force one representation into the other inside the raw schema unless that is already local parser convention.

Examples should choose a non-null example when one is available. Null can be used only when no better default, example, enum, or type fallback exists and the schema permits it.

Diagnostics can emit `nullable_fields_present` as an informational finding when nullable request fields exist.

## ReadOnly And WriteOnly Policy

Request direction:

- `readOnly: true` means the field is server-owned and should not be requested from the user by default
- `writeOnly: true` means the field can remain in request input examples and tool schemas

Response direction:

- `readOnly: true` remains visible
- `writeOnly: true` should be hidden or clearly marked so docs do not imply the value will be returned

The implementation should avoid changing raw OpenAPI source semantics. Direction-specific shaped helpers can filter fields for generated tool parameters, README request examples, smoke/manual examples, and response summaries.

Diagnostics candidates:

- `read_only_request_fields`
- `write_only_response_fields`

## Additional Properties Policy

`additionalProperties` should be preserved and explained:

```yaml
type: object
additionalProperties:
  type: string
```

README and inspect should display this as a map-like object, for example:

```text
object map[string]
```

For `additionalProperties: true`, display a broad map/object shape rather than a closed object. For `additionalProperties: false`, avoid implying arbitrary keys are allowed.

Diagnostics candidate:

- `additional_properties_present`

## Array Policy

Arrays should display item schemas when known:

```text
array[string]
array[object {id:string, name:string?}]
array[oneOf[string | object]]
```

When `items` is absent, keep generation compatible but surface the ambiguity:

- README: `array[unknown]`
- examples: `[]` unless an explicit example/default exists
- diagnostics: `array_without_item_schema`

Nested arrays should be summarized compactly without expanding into unreadable output.

## Polymorphism Policy

`oneOf` and `anyOf` should remain preserved. v0 should improve how they are summarized rather than selecting branches automatically.

README and inspect should:

- distinguish `oneOf` from `anyOf`
- show a bounded list of branch summaries
- avoid recursively expanding large nested branches without limit
- show discriminator names when present

Generated examples should keep the current deterministic behavior unless explicit examples/defaults select a shape. Do not invent branch selection by LLM.

Diagnostics candidate:

- `nested_polymorphic_schema`

## Required And Optional Field Display

Object summaries should make required fields visible:

```text
object {id:string, name:string?, email:string?}
```

The exact display syntax can stay compact, but generated docs should avoid making optional fields look required. For request bodies, this is especially important after read-only filtering because a server-generated required response field may not be required in the shaped input.

Diagnostics candidate:

- `large_object_schema`

## Generated Artifact Effects

README:

- show nullable fields clearly
- mark or omit read-only request fields
- mark write-only request fields when useful
- show map semantics for `additionalProperties`
- show array item summaries
- show bounded `oneOf` / `anyOf` branch summaries
- distinguish required and optional object fields

OpenAI tools schema / generated tool params:

- use request-direction shaping for request bodies
- avoid asking for `readOnly` fields by default
- preserve `writeOnly` fields
- keep existing parameter schemas compatible

Examples and smoke/manual tests:

- prefer explicit examples/defaults/enums as today
- build object examples from shaped request input schemas
- choose non-null nullable examples when possible
- keep ambiguous arrays empty unless examples/defaults exist

`api2agent inspect`:

- show schema shaping summary counts
- expose nullable, read-only/write-only, map, array, and polymorphic hints compactly

Diagnostics:

- `nullable_fields_present`
- `read_only_request_fields`
- `write_only_response_fields`
- `additional_properties_present`
- `nested_polymorphic_schema`
- `array_without_item_schema`
- `large_object_schema`

## Implementation Plan

1. Add schema helper functions for direction-aware shaping and compact summaries.
2. Preserve existing raw normalized schemas.
3. Add nullable detection for OpenAPI 3.0 and OpenAPI 3.1 forms.
4. Add request-body shaping that filters or marks `readOnly` object fields.
5. Add response shaping that filters or marks `writeOnly` object fields.
6. Improve README schema formatter for nullable, maps, arrays, polymorphism, and optional fields.
7. Update generated tool parameter schemas to use request-direction shaping for bodies.
8. Update example generation to use shaped request input schemas.
9. Add diagnostics for schema complexity and directionality.
10. Add fixtures and regression tests.

## Tests

Add fixtures for:

- OpenAPI 3.0 nullable fields
- OpenAPI 3.1 nullable type arrays
- request body objects with `readOnly` and `writeOnly` properties
- response objects with `readOnly` and `writeOnly` properties
- `additionalProperties` as schema, `true`, and `false`
- arrays with object items, polymorphic items, and missing items
- nested `oneOf` / `anyOf`
- required and optional object properties

Regression tests should cover:

- parser preserves raw schema compatibility
- README displays nullable fields
- README displays required versus optional fields
- generated request body examples do not require read-only fields
- generated request body examples preserve write-only fields
- response summaries do not imply write-only fields are returned
- map object summaries are readable
- arrays without item schemas are diagnosed
- nested polymorphic schemas are bounded in summaries
- old capability JSON without shaped schema metadata remains valid

## Dogfood

Run local dogfood against:

- existing `composition.yaml`
- a new schema-shaping fixture with nullable/readOnly/writeOnly/map/array cases
- generated README review
- `api2agent inspect`
- `api2agent diagnose`
- generated smoke/manual examples

No network dependency is required.

## Success Metrics

The implementation is successful when:

- generated Agent-facing inputs stop asking for obvious server-generated fields
- nullable and map semantics are visible in generated docs
- arrays and polymorphic schemas are summarized compactly
- examples remain deterministic and more useful for request bodies
- diagnostics flag schema shapes likely to confuse Agents
- existing schema composition behavior remains compatible
- full Python test suite passes

## Acceptance Criteria For This Design

- current schema handling baseline and gaps are documented
- additive compatibility strategy is defined
- direction-aware request/response shaping rules are defined
- nullable, readOnly/writeOnly, additionalProperties, array, polymorphism, and required/optional policies are defined
- generated README, tools schema, examples, inspect, and diagnostics effects are defined
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
