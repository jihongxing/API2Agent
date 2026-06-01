# Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Design v0

Date: 2026-06-01

Status: complete

## Decision

The next Agent Capability Compiler implementation slice should be:

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Implementation v0
```

This slice should add a small, committed, offline cached real-spec corpus to the OpenAPI calibration harness. The goal is broader confidence in compiler behavior against public, non-fixture OpenAPI shapes while keeping calibration deterministic, reviewable, and legally safe.

The implementation should not depend on network access. It should not execute providers. It should not add hosted runtime behavior, public CRUD, workflow execution, marketplace/provider onboarding, vault, billing, production gateway permission source, or automatic propagation.

## Why This Slice Now

The compiler has closed the core OpenAPI hardening chain:

- diagnostics and package quality visibility
- examples/defaults propagation
- security requirement combinations
- server handling
- schema shaping
- discriminator handling
- response shape documentation
- bounded JSON Schema keyword coverage
- real-spec calibration harness
- diagnostics score calibration
- summary noise reduction
- generic example reduction

The default calibration run now reports:

```text
OpenAPI real-spec calibration: 4 pass, 2 warn, 0 fail, 1 skipped
```

Default generated cases also report:

```text
generic_example_count = 0
generic_first_call_params = []
```

The remaining compiler risk is confidence breadth. The current corpus is stable, but it is mostly local fixtures plus a synthetic large spec. A cached real public spec can expose realistic operation naming, tag layouts, parameter conventions, response shapes, server metadata, and auth combinations that handcrafted fixtures may miss.

## Goals

- add one or more cached real public OpenAPI specs to calibration
- keep the harness offline and deterministic by default
- preserve a clear source attribution and license/cache review record
- avoid committing secrets, live credentials, user data, or generated provider outputs
- keep checked-in fixtures small enough for review
- measure the cached case with the existing calibration artifact contract
- expose whether real-spec behavior changes diagnostics score, summary density, generic examples, package size, or filter guidance
- keep the compiler API-first and local

## Non-Goals

Do not implement:

- network fetches during normal tests or calibration
- real provider execution
- runtime request/response validation
- LLM-based schema interpretation
- broad OpenAPI corpus crawling
- automatic upstream refresh
- hosted service behavior
- provider marketplace onboarding
- credential vault writes
- billing or settlement
- public Control Plane CRUD
- production gateway permission source
- workflow runtime
- automatic snapshot publish/reload

## Corpus Policy

### Source Criteria

Each cached real spec must satisfy all of these:

- publicly available source
- redistribution or repository inclusion is allowed by license or explicit terms
- no embedded secrets, tokens, user identifiers, private hostnames, or live credentials
- stable enough that a committed cache is meaningful
- API-first HTTP/OpenAPI surface
- exercises at least one real-world dimension not already covered well by fixtures
- reasonable size after optional deterministic reduction

Preferred source types:

- official public API OpenAPI documents with permissive licenses
- public demo/reference API specs with explicit redistribution terms
- small curated excerpts from permissively licensed specs when full specs are too large

Avoid:

- specs whose licensing is ambiguous
- specs generated from private services
- specs that include real customer examples
- specs requiring auth or network calls to inspect
- giant specs that make review noisy without adding new compiler signal

### Cache Metadata

Every cached spec should have adjacent metadata, either in a manifest entry or sidecar file:

```text
case_id
purpose
source_name
source_url
source_license
source_retrieved_at
cache_policy
reduction_policy
redaction_policy
sha256
notes
```

`source_retrieved_at` is informational. The cached file contents, not the live upstream URL, are the calibration input.

### Redaction Policy

Before committing a cached spec:

- remove or replace secrets, bearer tokens, API keys, session ids, and passwords
- remove real email addresses unless they are official example addresses such as `user@example.com`
- remove private hostnames, internal IPs, and tenant/customer identifiers
- preserve schema structure, operation ids, tags, parameters, examples, and response metadata when safe
- document every intentional reduction or redaction in metadata

Redaction must be deterministic and reviewable. Do not use an LLM or opaque script as the only redaction evidence.

### Size Policy

Default target:

```text
cached spec <= 500 KiB
generated capability.json <= 1 MiB
tool_count <= 100 unless the case is explicitly large-surface
```

If the full public spec is too large, prefer a deterministic reduced excerpt that keeps:

- original OpenAPI version
- original info title/version when license allows
- selected tags/paths/operations
- components required by selected operations
- security/server/schema features needed for calibration

The reduction should be documented as a cache transformation, not hidden as an original upstream copy.

## Artifact Location

Recommended layout:

```text
.dogfood/openapi-real-spec-calibration/inputs/
  cached-real/
    <case_id>.openapi.json
    <case_id>.metadata.json
```

The existing optional path can remain compatible:

```text
.dogfood/openapi-real-spec-calibration/inputs/cached_real.openapi.json
```

But the implementation should prefer the `cached-real/` directory for multiple cases and clearer attribution.

## Manifest Changes

Replace or supplement the single `optional_cached_real_spec` case with named cached cases:

```text
cached_<source>_<purpose>
```

Each case should define:

```text
case_id
purpose
source_path
metadata_path
filters
expected_status
optional
notes
```

Recommended purposes:

- `cached_real_small`
- `cached_real_auth`
- `cached_real_schema`
- `cached_real_large`

For v0, one required cached real case is enough if it adds meaningful signal. Additional cases can remain optional.

## Calibration Metrics

The existing artifact fields remain compatible. Add cached-spec metadata fields per case:

```text
source_name
source_url
source_license
source_retrieved_at
cache_sha256
cache_policy
reduction_policy
redaction_policy
```

The harness should continue reporting:

- `tool_count`
- `read_tools`, `write_tools`, `delete_tools`
- `required_parameter_count`
- `schema_hint_counts`
- `response_category_counts`
- `diagnostics_status`
- `diagnostics_score`
- `diagnostics_summary`
- `finding_counts`
- `repeated_finding_groups`
- `readme_bytes`
- `readme_tool_section_lines`
- `capability_bytes`
- `generation_ms`
- `inspect_line_count`
- `max_inspect_line_chars`
- `first_call_params`
- `generic_example_count`
- `generic_first_call_params`

## Status And Thresholds

Cached real cases should remain report-oriented, but v0 should classify clear regressions.

Recommended fail conditions:

- cached source file missing for required cases
- metadata file missing or invalid for required cached cases
- metadata checksum does not match source file
- generation fails
- generated package lacks `capability.json` or `diagnostics.json`
- source path resolves outside the calibration inputs directory
- redaction metadata is absent

Recommended warn conditions:

- `tool_count > 100`
- `diagnostics_score < 60`
- `generic_example_count > 0`
- `max_inspect_line_chars > 180`
- `readme_bytes > 200_000`
- `generation_ms > 30_000`
- write/delete tools exist but no read tools exist
- source license metadata is present but marked `review_required`

Recommended pass conditions:

- required cached metadata validates
- package generation succeeds
- diagnostics are readable
- first-call params are captured when applicable
- no generic first-call params remain
- warnings, if present, are expected and documented

## Implementation Plan

1. Add metadata model/helpers for cached calibration sources.
2. Add checksum verification for cached source files.
3. Add path containment checks under `.dogfood/openapi-real-spec-calibration/inputs`.
4. Extend `CalibrationCase` with optional `metadata_path`.
5. Add at least one required cached real case or a required curated public-spec excerpt with metadata.
6. Keep optional user-provided cached spec compatibility.
7. Extend `result.json` with safe source metadata.
8. Add regression tests for metadata validation, checksum mismatch, path containment, optional skips, and status classification.
9. Run calibration dogfood and capture the new cached case in the implementation report.

## Test Plan

Add or update tests for:

- valid cached metadata loads and appears in result artifact
- checksum mismatch fails the case
- missing metadata fails required cached cases
- optional cached cases still skip cleanly
- source paths cannot escape the calibration inputs directory
- redaction/license/cache policy fields are required for committed cached cases
- cached real case participates in summary counts
- generic example metrics remain present
- existing default fixture cases remain stable

## Dogfood Plan

Run:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Expected after implementation:

- at least one cached real case is generated, not skipped
- `optional_cached_real_spec` is either replaced by named cached cases or remains as a backward-compatible optional slot
- result artifact includes source metadata and checksum
- default summary remains `0 fail`
- generic example counts stay zero or produce explicit recommendations
- large or noisy real cases produce warnings, not silent failures

## Acceptance Criteria

- cached real-spec corpus policy is implemented
- at least one committed cached real/public-spec case has source metadata
- normal calibration remains offline and deterministic
- required cached cases validate checksum, metadata, and path containment
- optional cached cases still skip cleanly when absent
- result artifact includes safe source/cache metadata
- calibration recommendations include cached real-spec issues when present
- targeted and full test suites pass
- no LLM generation, provider execution, network-dependent tests, hosted service, workflow, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation is added

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Implementation v0
```
