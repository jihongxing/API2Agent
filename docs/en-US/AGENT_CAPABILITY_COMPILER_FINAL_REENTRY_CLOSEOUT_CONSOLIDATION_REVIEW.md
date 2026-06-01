# Agent Capability Compiler Final Re-entry Closeout + Consolidation Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler re-entry phase can close.

Within the current API-first re-entry scope, the compiler is complete enough to pause at:

```text
100%
```

This does not mean the compiler has no future backlog. It means the re-entry goal is satisfied: API2Agent now has a much stronger path from OpenAPI/curl inputs to Agent-ready, reviewable, deterministic generated capability packages, with diagnostics, examples, summaries, calibration evidence, and one cached real public spec in the default evidence loop.

Recommended next project task:

```text
Go Control Plane Hosted Admin Gateway Permission Source Design v0
```

That was the paused hosted-readiness task before the compiler re-entry. The compiler work no longer blocks returning to it.

## Re-entry Goal Review

The re-entry goal was to strengthen the Agent capability compiler without changing API2Agent's product boundary.

Accepted constraints:

- API-first
- no workflow engine
- no hosted runtime dependency
- no marketplace/provider onboarding
- no vault
- no billing
- no public Control Plane CRUD
- no production gateway permission source work during compiler re-entry
- no automatic snapshot publish/reload

These constraints held.

## Completed Slices

### Compiler Expansion Design

Selected deterministic quality diagnostics as the first expansion slice.

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`

### Quality Diagnostics

Implemented deterministic package diagnostics, `diagnostics.json`, `api2agent diagnose`, README/inspect summaries, and regression coverage.

References:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_CLOSEOUT_PHASE_REVIEW.md`

### OpenAPI Real-World Hardening Chain

Completed OpenAPI hardening across:

- examples/defaults propagation
- security requirement combinations
- server handling
- schema shaping
- discriminator handling
- response shape documentation
- bounded JSON Schema keyword coverage

References:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_EXAMPLES_DEFAULTS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_CLOSEOUT_PHASE_REVIEW.md`

### Calibration And Evidence Loop

Implemented and refined the local offline calibration harness:

- real-spec calibration harness
- diagnostics score calibration
- summary noise reduction
- generic example reduction
- cached real-spec corpus expansion

References:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_CLOSEOUT_PHASE_REVIEW.md`

## Current Evidence

Latest full test suite:

```text
python -m pytest -q
221 passed
```

Latest calibration dogfood:

```text
OpenAPI real-spec calibration: 5 pass, 2 warn, 0 fail, 1 skipped
```

Default calibration corpus now includes:

- small reference fixture
- schema-rich fixture
- auth-rich fixture
- server-rich fixture
- write-heavy fixture
- synthetic large REST case
- committed cached Petstore real public spec excerpt
- optional user-provided cached real spec slot

The two warning cases are accepted:

- `write_heavy_unsafe`: intentionally write/delete-only, score 56
- `large_rest_synthetic`: intentionally over 50 tools

The cached real public spec case passes:

```text
cached_petstore_expanded: pass tools=4 score=82
generic_example_count=0
```

## What Improved

The compiler now provides:

- deterministic quality diagnostics
- compact human-readable quality summaries
- full-fidelity JSON diagnostics and inspect output
- source examples/defaults/enums/consts propagation
- name-aware deterministic examples
- server metadata and override guidance
- security combination metadata and runner handling for supported auth
- direction-aware schema shaping
- discriminator-aware summaries and examples
- response shape documentation
- bounded JSON Schema keyword coverage
- calibrated diagnostics scoring
- summary-density metrics
- generic example metrics
- cached real-spec source metadata and checksum validation
- offline calibration evidence

## Residual Risks

### Corpus Breadth

The corpus now includes one cached real public spec, but it is not a broad public API benchmark. More cached specs can be added later once the project has a concrete question to answer.

### Runtime Validation

The compiler documents and shapes schemas, but generated runners still do not perform full runtime schema validation. This remains a deliberate non-goal for the re-entry.

### OAuth And Complex Auth

OAuth/OpenID remains metadata-oriented unless a supported credential injection mode is available. Full OAuth product semantics belong outside this compiler re-entry.

### Large Public Specs

Large specs are measurable and warn clearly, but the product still expects filtering before Agent use. This is correct for the current Agent usability boundary.

### Generated Examples Are Advisory

Examples are deterministic and safer, but not provider-valid records. They are first-call aids, not data discovery.

### Hosted Platform Work Is Still Deferred

Compiler readiness does not solve hosted permission issuance, public auth, production gateway deployment, tenant partitioning, or hosted operational controls. Those are the correct next lane.

## Closeout Judgment

The Agent Capability Compiler is ready to pause.

The project should not continue adding compiler slices by default. Future compiler work should be triggered by concrete evidence from real users, new real-spec calibration cases, or hosted Control Plane integration needs.

The next highest-value move is to return to the hosted-readiness backlog at the previously deferred permission-source design.

## Next Recommended Task

```text
Go Control Plane Hosted Admin Gateway Permission Source Design v0
```

Scope should remain narrow:

- permission source contract
- trusted gateway permission issuance assumptions
- principal/project/organization mapping
- endpoint permission lookup semantics
- audit/idempotency evidence
- fail-closed behavior
- local harness dogfood expectations

Still do not start marketplace, billing, vault, public CRUD, automatic propagation, or workflow runtime work.
