# Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

OpenAPI cached real-spec corpus expansion v0 is implemented for the Agent Capability Compiler.

The calibration harness now includes a committed offline cached real-spec case with source metadata, checksum verification, redaction/cache policy evidence, path containment checks, and result artifact metadata. This gives the compiler a real public OpenAPI shape in the default calibration run without adding network dependency, provider execution, hosted runtime behavior, or non-API scope.

Implemented:

- cached source metadata support on `CalibrationCase`
- metadata validation for required cached cases
- SHA-256 checksum verification for cached source files
- path containment checks under `.dogfood/openapi-real-spec-calibration/inputs`
- safe source/cache metadata in calibration `result.json`
- a committed Swagger Petstore expanded excerpt under `.dogfood/openapi-real-spec-calibration/inputs/cached-real/`
- regression coverage for valid metadata, checksum mismatch, missing metadata, path containment, optional skips, and default manifest inclusion

No LLM generation, provider execution, network-dependent tests, runtime validation, hosted service, workflow, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation was added.

## Files

Implementation:

- `scripts/api2agent_openapi_real_spec_calibration.py`

Cached corpus:

- `.dogfood/openapi-real-spec-calibration/inputs/cached-real/petstore_expanded.openapi.json`
- `.dogfood/openapi-real-spec-calibration/inputs/cached-real/petstore_expanded.metadata.json`

Tests:

- `tests/test_openapi_real_spec_calibration.py`

Design reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_DESIGN.md`

## Cached Source

Cached case:

```text
cached_petstore_expanded
```

Source metadata:

```text
source_name = OpenAPI Initiative Swagger Petstore expanded example
source_url = https://github.com/OAI/OpenAPI-Specification/blob/main/examples/v3.0/petstore-expanded.yaml
source_license = Apache-2.0
cache_sha256 = sha256:c41e9e47dabacb0837b78e6414bd46d24c7a78b24acdfd1ea7f80803e050b008
```

The cached file is a deterministic JSON excerpt that preserves pets paths, server metadata, response schemas, component references, mixed read/write/delete tools, and `allOf` schema shape. Contact email and externalDocs metadata are omitted. The metadata records the cache, reduction, and redaction policies.

## Behavior Changes

The default manifest now includes one required cached real-spec case:

```text
cached_petstore_expanded
```

For cases with `metadata_path`, the harness validates:

- source path is under `.dogfood/openapi-real-spec-calibration/inputs`
- metadata path is under `.dogfood/openapi-real-spec-calibration/inputs`
- metadata file exists and is valid JSON
- required metadata fields are present
- metadata `case_id` matches the calibration case
- metadata `sha256` matches the source file bytes

The existing backward-compatible optional user-provided slot remains:

```text
optional_cached_real_spec
```

Cases without `metadata_path` keep their previous behavior.

## Dogfood Evidence

Run:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Observed:

```text
OpenAPI real-spec calibration: 5 pass, 2 warn, 0 fail, 1 skipped
- small_reference_basic: pass tools=1 score=87
- schema_rich_keywords: pass tools=2 score=70
- auth_rich_security: pass tools=5 score=62
- server_rich_choices: pass tools=3 score=62
- write_heavy_unsafe: warn tools=2 score=56 - diagnostics_score < 60; no read tools when write/delete tools exist
- large_rest_synthetic: warn tools=60 score=82 - tool_count > 50
- cached_petstore_expanded: pass tools=4 score=82
- optional_cached_real_spec: skipped tools=0 score=None - optional source_path is not present
```

Cached Petstore case evidence:

```text
tool_count = 4
read_tools = 2
write_tools = 1
delete_tools = 1
diagnostics_score = 82
schema_hint_counts = numeric_constraints=1, schema_keywords=10, string_constraints=10
response_category_counts = default=4, success=4
generic_example_count = 0
generic_first_call_params = []
```

## Validation

Passed:

```text
python -m py_compile scripts\api2agent_openapi_real_spec_calibration.py
```

Passed:

```text
python -m pytest tests\test_openapi_real_spec_calibration.py -q
```

Result:

```text
9 passed
```

Passed local dogfood:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Observed:

```text
OpenAPI real-spec calibration: 5 pass, 2 warn, 0 fail, 1 skipped
```

## Compatibility

Compatibility is preserved:

- existing fixture calibration cases remain unchanged
- optional cached user-provided spec behavior remains supported
- calibration artifact contract remains additive
- generated package contracts are unchanged
- generated runner behavior is unchanged
- diagnostics behavior is unchanged

The intentional behavior change is a broader default calibration corpus with source/cache metadata for committed real-spec cases.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Closeout + Phase Review v0
```

The closeout should decide whether one required cached case is sufficient for v0, whether additional cached cases should wait until after final consolidation, and whether the Agent Capability Compiler can move to final re-entry closeout.
