# Agent Capability Compiler OpenAPI Real-Spec Calibration Design v0

Date: 2026-06-01

Status: complete

## Decision

The next Agent Capability Compiler implementation slice should be:

```text
Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Implementation v0
```

This slice should create a repeatable local calibration harness for a small, curated set of real OpenAPI specs. The harness should measure generated package usability across summaries, examples, diagnostics, package size, filtering guidance, and first-call ergonomics without adding runtime validation, hosted services, provider onboarding, workflow execution, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation.

## Why This Slice Now

The compiler has completed the main OpenAPI hardening run:

- examples/defaults propagation
- security requirement combinations
- server handling
- schema shaping
- discriminator handling
- response shape documentation
- bounded JSON Schema keyword coverage
- diagnostics and inspect visibility

The next risk is no longer one obvious missing feature. The risk is calibration: real specs may expose summary density, noisy diagnostics, missing filter guidance, awkward examples, overly large packages, or subtle schema/auth/server combinations that individual fixtures do not reveal.

The baseline audit already showed this pattern:

- GitHub REST generated successfully but produced an unfiltered 1186-tool package.
- Swagger Petstore exposed relative server URL and auth-boundary issues.
- curl and simple OpenAPI packages worked, but large real specs needed better guidance.

The compiler now needs a stable real-spec evidence loop before selecting the next semantic feature.

## Goals

- define a local, repeatable real-spec calibration harness
- keep calibration deterministic and offline by default
- measure generated package quality across a curated corpus
- record package-level and tool-level metrics in a machine-readable artifact
- surface regressions in summary readability, example quality, diagnostics noise, and package size
- identify the next OpenAPI hardening gap using evidence, not intuition
- preserve the API-first compiler boundary

## Non-Goals

Do not implement:

- real provider execution as part of calibration by default
- network-dependent tests in the main suite
- runtime request or response validation
- OpenAPI 3.1 dialect enforcement
- LLM-based schema interpretation
- provider marketplace onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- production gateway permission source
- workflow runtime
- automatic snapshot publish/reload

## Calibration Corpus

Use a small curated corpus with explicit purpose labels. The implementation should support local paths first and optional user-provided paths later.

Recommended corpus slots:

| Slot | Purpose | Examples Of Signals |
| --- | --- | --- |
| `small_reference` | compact baseline spec | README clarity, examples, response summaries |
| `large_rest` | large endpoint surface | tool count, filter guidance, inspect truncation, generation time |
| `auth_rich` | security combinations | auth alternatives, combined auth, endpoint overrides |
| `server_rich` | servers and variables | relative servers, variables, environment/profile hints |
| `schema_rich` | schema complexity | nullable/readOnly/writeOnly, discriminators, keyword markers, response docs |
| `write_heavy` | safety and manual paths | read/write split, manual write examples, diagnostics |

Initial sources can reuse existing fixtures for stable regression and known public specs from prior dogfood where local cached copies are available. The harness should not require network access to pass.

## Calibration Metrics

The harness should emit one JSON artifact:

```text
.dogfood/openapi-real-spec-calibration/result.json
```

Recommended top-level fields:

```text
contract_version
generated_at
cases
summary
recommendations
```

Per case:

```text
case_id
purpose
source_path
filters
generated
tool_count
read_tools
write_tools
delete_tools
unknown_safety_tools
required_parameter_count
schema_hint_counts
response_category_counts
diagnostics_status
diagnostics_score
diagnostics_summary
finding_counts
readme_bytes
capability_bytes
generation_ms
inspect_excerpt
sample_tool_details
```

The artifact should be deterministic enough for review, but timestamps can remain informational.

## Scoring And Gates

Calibration should be report-oriented, not a hard release gate at first.

Recommended status:

- `pass`: generated package exists, diagnostics are usable, and no calibration-specific severe issue is detected
- `warn`: package generated but exposes high tool count, warning-heavy diagnostics, missing base URL, too many required inputs, or noisy summaries
- `fail`: generation fails, output is missing required artifacts, diagnostics JSON cannot load, or inspect cannot render

Recommended warning thresholds:

- `tool_count > 50`
- `diagnostics_status == "fail"`
- `diagnostics_score < 60`
- `readme_bytes > 200_000`
- `generation_ms > 30_000`
- no read tools when write/delete tools exist
- schema hint categories present but no readable inspect detail

Thresholds should be documented as calibration defaults, not product promises.

## Harness Behavior

Implementation should add a script, not a new production runtime:

```text
scripts/api2agent_openapi_real_spec_calibration.py
```

Behavior:

1. load a small manifest of calibration cases
2. run `parse_openapi_file` and `generate_package` directly
3. optionally apply include-tag/include-path/include-operation/max-tools filters per case
4. load generated `capability.json` and `diagnostics.json`
5. compute metrics using existing helpers where possible
6. run inspect-style summarization without invoking external services
7. write `.dogfood/openapi-real-spec-calibration/result.json`
8. print a concise summary table

The script should use temporary output directories under `.dogfood/openapi-real-spec-calibration/generated/`.

## Manifest Strategy

Start with a Python-defined manifest in the script or a small JSON/YAML manifest if the repo already has a suitable pattern.

Each case should define:

```text
case_id
purpose
source_path
filters
expected_status
notes
```

The first implementation can use existing local fixtures for most slots and leave large real-spec cached paths optional if no local copy is available. Optional cases should be marked skipped rather than failing the harness.

## Generated Artifact Review

The harness should capture short excerpts, not full README copies:

- first 5 inspect lines
- first 5 tool detail lines
- schema hints summary
- response categories summary
- top diagnostics finding ids
- first-call params for one selected read tool when available

This keeps calibration artifacts reviewable and avoids committing bulky generated packages.

## Tests

Add regression coverage for:

- manifest case loading
- metrics extraction from generated packages
- skipped optional case behavior
- pass/warn/fail status classification
- result artifact contract fields
- no network dependency
- generated output path containment under `.dogfood/openapi-real-spec-calibration`

Use existing fixtures:

- `basic.yaml`
- `schema_keywords.yaml`
- `security_combinations.yaml`
- `server_choices.yaml`
- `unsafe.yaml`
- a synthetic large spec generated in the test or reused from existing large-spec tests

## Dogfood

Run:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Expected dogfood output:

- a JSON artifact at `.dogfood/openapi-real-spec-calibration/result.json`
- concise console summary with case statuses
- at least one small baseline case
- at least one schema-rich case
- at least one auth-rich case
- at least one server-rich case
- one large-surface case, synthetic or cached real spec

## Output Review Questions

The implementation report should answer:

1. Which case produced the noisiest diagnostics?
2. Which case produced the largest package?
3. Which summaries were hardest to read?
4. Which generated examples remained generic?
5. Which diagnostics should become more precise?
6. Which real-spec gap should become the next hardening task?

## Success Metrics

The implementation is successful when:

- calibration can run locally without network access
- results are machine-readable and concise enough for review
- generated package metrics are comparable across cases
- oversized packages and diagnostics-heavy cases are visible
- optional real-spec inputs can be skipped cleanly
- full Python test suite passes

## Acceptance Criteria For This Design

- rationale for calibration-after-keyword-coverage is documented
- corpus slots are defined
- metric contract is defined
- status thresholds are defined
- harness behavior is defined
- manifest and artifact strategy are defined
- tests and dogfood are named
- non-goals preserve API-first compiler boundaries
