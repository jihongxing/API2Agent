# Agent Capability Compiler OpenAPI Discriminator Handling Design v0

Date: 2026-06-01

Status: complete

## Decision

The next OpenAPI hardening implementation slice should be:

```text
Agent Capability Compiler OpenAPI Discriminator Handling Implementation v0
```

This slice should make OpenAPI discriminator metadata visible and useful for Agent-facing polymorphic schemas while preserving raw schema compatibility and offline deterministic generation.

It should remain API-first and must not add a full JSON Schema validator, generated SDK type system, workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation.

## Why This Slice Now

Schema shaping now handles nullable fields, readOnly/writeOnly directionality, maps, arrays, required/optional summaries, and bounded `oneOf` / `anyOf` display. The biggest remaining polymorphism gap is discriminator handling.

Real OpenAPI specs often use discriminators to explain which schema branch applies:

```yaml
oneOf:
  - $ref: "#/components/schemas/CardPayment"
  - $ref: "#/components/schemas/BankTransfer"
discriminator:
  propertyName: type
  mapping:
    card: "#/components/schemas/CardPayment"
    bank_transfer: "#/components/schemas/BankTransfer"
```

Current generation preserves the raw dictionary, but generated summaries, examples, and diagnostics do not explain how `type=card` maps to the card branch. Agents see a polymorphic object without the branch-selection key.

## Current Baseline

Already present:

- local `$ref` resolution
- recursive schema normalization
- raw `discriminator` dictionaries are preserved because unknown schema keys are preserved
- `oneOf` and `anyOf` are preserved
- schema shaping displays bounded polymorphic summaries
- diagnostics can report nested polymorphic schemas
- generated examples remain deterministic and do not use LLM branch selection

Important gaps:

- discriminator `propertyName` is not shown in README or inspect schema summaries
- discriminator `mapping` entries are not shown
- generated examples do not set a discriminator property
- branch labels are generic summaries rather than mapped names
- diagnostics do not report discriminator presence or malformed discriminator metadata
- unresolved mapping targets are not surfaced
- branches that cannot set the discriminator value are not flagged

## Goals

- preserve raw discriminator metadata without changing existing schema fields
- make discriminator property names visible in README and inspect summaries
- show mapping values and branch labels compactly
- use discriminator metadata to improve deterministic request examples when no explicit example/default exists
- diagnose common discriminator problems in real specs
- keep generated OpenAI tool schemas compatible with request-direction schema shaping
- keep generation deterministic and offline
- avoid becoming a schema validator or type generator

## Non-Goals

Do not implement:

- full JSON Schema validation
- complete OpenAPI 3.1 discriminator semantics
- runtime branch validation or coercion
- LLM branch selection
- generated SDK classes or tagged union types
- UI form rendering
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed Compatibility Strategy

Keep existing raw schema fields:

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

Do not require a new IR model for v0. Prefer helper functions in the schema shaping layer that derive discriminator facts from raw schemas:

```text
DiscriminatorSummary:
  property_name: str
  mapping_keys: list[str]
  branch_count: int
  unresolved_mappings: list[str]
  branch_labels: list[str]
```

If future implementation needs additive metadata, it must be optional and derived from raw schema dictionaries.

Old generated `capability.json` files remain valid.

## Discriminator Extraction Rules

For any schema object:

1. detect `discriminator` only when it is an object
2. read `propertyName` when it is a non-empty string
3. read `mapping` when it is an object
4. preserve mapping keys as candidate discriminator values
5. preserve mapping targets as strings; do not require all targets to be local refs
6. associate discriminator metadata with sibling `oneOf` / `anyOf` branches
7. do not select or validate branches during parsing

The parser can continue preserving raw schemas. Most v0 behavior can live in schema shaping helpers, diagnostics, README formatting, inspect, and example generation.

## Summary Formatting Rules

Schema summaries should make discriminator intent visible:

```text
oneOf[discriminator=type: card=>CardPayment | bank_transfer=>BankTransfer]
```

When branch labels cannot be resolved, fall back to existing bounded branch summaries:

```text
oneOf[discriminator=type: card=>object {...} | bank_transfer=>object {...}]
```

For missing or invalid mapping:

```text
oneOf[discriminator=type: object {...} | object {...}]
```

Summaries should stay bounded:

- show at most the existing branch display limit
- include `...` for additional branches
- never expand the same recursive branch forever
- preserve `oneOf` versus `anyOf`

## Example Generation Rules

When a request body schema has a discriminator and no explicit example/default/examples map:

1. use the first mapping key in source order when `mapping` exists
2. otherwise use the first branch
3. construct an example from that branch using existing deterministic example rules
4. set the discriminator property to the selected mapping key when possible
5. if the branch declares the discriminator property with `const`, `enum`, `default`, or `example`, prefer that value
6. do not synthesize values from branch names unless no mapping or branch value exists
7. keep readOnly filtering and writeOnly preservation from schema shaping

This improves first-call examples without pretending to validate every branch.

## OpenAI Tools Schema Rules

Generated OpenAI tool schemas should:

- preserve raw discriminator metadata when compatible with downstream schema consumers
- continue request-direction shaping for request bodies
- keep discriminator property visible for request input when it is not readOnly
- not flatten polymorphic branches into one merged object
- not require branch-specific fields beyond what the source schema already requires

## Diagnostics

Add deterministic findings:

- `discriminator_present`
- `discriminator_mapping_present`
- `discriminator_missing_property`
- `discriminator_without_polymorphism`
- `discriminator_mapping_unresolved`
- `discriminator_branch_without_tag`

Severity guidance:

- informational for presence and mapping summaries
- warning for missing `propertyName`
- warning for discriminator without sibling `oneOf` / `anyOf`
- warning for unresolved local mapping targets
- informational or warning for branches that cannot identify a discriminator value, depending on whether examples are affected

## Inspect And README Effects

README:

- show discriminator property in schema summaries
- show mapping keys in bounded branch summaries
- make first-call/manual examples include discriminator values when generated from schema fallback

`api2agent inspect`:

- include discriminator counts in schema hints
- show discriminator-aware body and parameter summaries

Diagnostics:

- report discriminator quality findings
- include mapping keys and unresolved mapping targets as evidence

## Implementation Plan

1. Add discriminator extraction helpers to `api2agent/schema_shaping.py`.
2. Update polymorphic schema summaries to include discriminator property and mapping keys.
3. Add deterministic discriminator-aware branch/example selection for request bodies.
4. Preserve request-direction readOnly/writeOnly shaping while selecting branches.
5. Add schema hint counts for discriminators.
6. Add diagnostics for discriminator presence, malformed metadata, unresolved mappings, and untagged branches.
7. Add README and inspect coverage through existing summary paths.
8. Add OpenAPI fixture with discriminator mapping and an intentionally imperfect discriminator case.
9. Add parser, generator, diagnostics, and CLI regression tests.
10. Dogfood generated README, inspect, diagnose, and manual examples locally.

## Tests

Add fixtures for:

- `oneOf` with discriminator `propertyName`
- `oneOf` with discriminator `mapping`
- `anyOf` with discriminator metadata
- missing `propertyName`
- discriminator without sibling `oneOf` / `anyOf`
- mapping target pointing at a local `$ref`
- mapping target that cannot be resolved
- branch with discriminator property enum/const/default/example
- request body branch with readOnly/writeOnly fields

Regression tests should cover:

- raw discriminator metadata remains in parsed schema
- README schema summary shows `discriminator=<property>`
- README summary shows mapping keys
- request body examples set the discriminator property
- generated OpenAI tool body schema keeps discriminator metadata and request-direction shaping
- inspect shows discriminator schema hints
- diagnostics report discriminator presence and malformed mappings
- old capability JSON without discriminator metadata remains valid

## Dogfood

Run local dogfood against:

- a new discriminator fixture
- generated README review
- `api2agent inspect`
- `api2agent diagnose`
- generated manual write example

No network dependency is required.

## Success Metrics

The implementation is successful when:

- polymorphic schema summaries explain the branch selection key
- generated examples include a discriminator value when source metadata allows it
- malformed discriminator metadata is diagnosed
- existing schema shaping behavior remains compatible
- existing composition and schema shaping tests still pass
- full Python test suite passes

## Acceptance Criteria For This Design

- current discriminator baseline and gaps are documented
- compatibility strategy is defined
- discriminator extraction rules are defined
- summary formatting rules are defined
- example generation rules are defined
- OpenAI tools schema, README, inspect, and diagnostics effects are defined
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
