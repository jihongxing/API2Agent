# Agent Capability Compiler OpenAPI Discriminator Handling Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI discriminator handling is implemented for the Agent capability compiler.

Generated packages now preserve raw discriminator metadata while making discriminator-aware polymorphic schemas clearer in README, inspect, generated examples, OpenAI tool schemas, and diagnostics.

The implementation supports:

- discriminator extraction from raw schema dictionaries
- discriminator-aware `oneOf` / `anyOf` summaries
- mapping key display in bounded polymorphic summaries
- deterministic request example branch selection from discriminator mapping
- discriminator property insertion in generated request examples
- request-direction readOnly filtering inside polymorphic branches
- writeOnly preservation inside generated request body examples and tool schemas
- inspect schema hints for discriminator counts
- diagnostics for discriminator presence, mappings, missing `propertyName`, discriminator without polymorphism, unresolved mappings, and untagged branches

No full JSON Schema validator, OpenAPI 3.1 dialect engine, runtime branch validation, LLM branch selection, SDK type generation, UI form rendering, workflow runtime, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation was added.

## Files

Implementation:

- `api2agent/schema_shaping.py`
- `api2agent/generators/examples.py`
- `api2agent/diagnostics.py`

Existing generated artifact paths reused the shared schema shaping helpers:

- `api2agent/generators/readme.py`
- `api2agent/generators/tools.py`
- `api2agent/cli.py`

Tests and fixtures:

- `tests/fixtures/openapi/discriminator.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

## Contract

No required IR fields were added.

Existing raw schema fields remain the compatibility source of truth:

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

Discriminator facts are derived from raw schemas:

```text
discriminator.propertyName
discriminator.mapping
oneOf / anyOf branches
branch title / tag property values
```

Old generated `capability.json` files remain valid.

## Generated Artifact Effects

README and inspect now show discriminator-aware schema summaries:

```text
body: oneOf[discriminator=method: card=>CardPayment | bank_transfer=>BankTransfer | cash=>CashPayment] required
```

Generated manual write examples now select the first discriminator mapping and set the discriminator property:

```text
{'body': {'method': 'card', 'card_number': 'example', 'token': 'example'}}
```

Generated OpenAI tools schemas preserve discriminator metadata and request-direction shaping. In the discriminator fixture, the `readOnly` `id` field is omitted from the card branch while the `writeOnly` `token` remains.

`api2agent inspect` now includes discriminator hints:

```text
Schema hints: discriminator_mappings=3, discriminators=3, polymorphic=2, read_only=2, write_only=2
```

## Diagnostics

New diagnostics include:

- `discriminator_present`
- `discriminator_mapping_present`
- `discriminator_missing_property`
- `discriminator_without_polymorphism`
- `discriminator_mapping_unresolved`
- `discriminator_branch_without_tag`

These findings are deterministic and advisory/warning level. They do not validate branch payloads at runtime.

## Dogfood Evidence

Generated package:

```text
python -m api2agent.cli generate tests\fixtures\openapi\discriminator.yaml --output tmp\openapi-discriminator-handling --force
```

Observed:

```text
Generated capability package: tmp\openapi-discriminator-handling
Diagnostics: warn score=10 errors=0 warnings=8 info=12
```

`inspect` showed:

```text
Schema hints: discriminator_mappings=3, discriminators=3, polymorphic=2, read_only=2, write_only=2
body: oneOf[discriminator=method: card=>CardPayment | bank_transfer=>BankTransfer | cash=>CashPayment] required
```

`diagnose` showed the new discriminator findings:

```text
discriminator_present
discriminator_mapping_present
discriminator_mapping_unresolved
discriminator_branch_without_tag
discriminator_missing_property
discriminator_without_polymorphism
```

Generated manual write example included the selected discriminator value:

```text
{'body': {'method': 'card', 'card_number': 'example', 'token': 'example'}}
```

## Compatibility

Compatibility is preserved:

- raw discriminator dictionaries remain in generated schemas
- existing schema shaping behavior remains compatible
- request-direction readOnly/writeOnly handling is preserved inside selected branches
- OpenAI tools schemas are still generated from shaped request schemas
- generated examples still prefer explicit examples/defaults/enums before discriminator fallback
- generated runner behavior is unchanged
- old capability JSON without discriminator metadata remains valid

## Validation

Passed:

```text
python -m py_compile api2agent\schema_shaping.py api2agent\generators\examples.py api2agent\diagnostics.py api2agent\cli.py
```

Passed:

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

Result:

```text
79 passed
```

Passed:

```text
pytest
```

Result:

```text
197 passed
```

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Discriminator Handling Closeout + Phase Review v0
```

The closeout should decide whether this discriminator handling slice can close and whether the next OpenAPI hardening target should be richer response documentation, deeper JSON Schema keyword coverage, or another real-spec friction point.
