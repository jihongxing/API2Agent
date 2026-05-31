# Agent Capability Compiler Quality Diagnostics Closeout + Phase Review v0

Date: 2026-06-01

Status: complete

## Decision

The Agent Capability Compiler Quality Diagnostics implementation slice can close.

The compiler now gives developers a deterministic quality signal for generated OpenAPI and curl capability packages before those packages are wired into Agents or proxy execution.

Recommended next task:

```text
Agent Capability Compiler OpenAPI Real-World Hardening Design v0
```

The next design should use diagnostics as a measurement layer while improving OpenAPI handling for real-world specs. It should remain API-first and must not add workflow execution, marketplace/provider onboarding, vault, billing, hosted public CRUD, production gateway permission source, or automatic snapshot propagation.

## What Is Now Complete

### Design

Completed:

- selected quality diagnostics as the first compiler expansion slice
- target generate/diagnose/inspect workflows
- additive `diagnostics.json` contract
- initial finding set
- scoring heuristic
- tests and dogfood requirements
- non-goals preserving API-first boundaries

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`

### Implementation

Completed:

- `api2agent.diagnostics` pure IR diagnostics engine
- generated package `diagnostics.json`
- generation-time diagnostics summary
- generated README diagnostics section
- `api2agent inspect` diagnostics summary
- `api2agent diagnose <package_dir>`
- `api2agent diagnose <package_dir> --json`
- recomputation for old packages without `diagnostics.json`
- deterministic tests for usability, safety, auth, schema, execution, and observability findings

Reference:

- `docs/en-US/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| generated packages include additive `diagnostics.json` | passed |
| diagnostics can be recomputed from `capability.json` | passed |
| CLI exposes human-readable diagnostics | passed |
| CLI exposes JSON diagnostics contract | passed |
| generation prints compact diagnostics summary | passed |
| generated README includes diagnostics summary | passed |
| inspect remains compatible with old packages | passed |
| diagnostics do not block generation by default | passed |
| findings cover Agent usability risks | passed |
| findings cover safety risks | passed |
| findings cover auth/credential risks | passed |
| findings cover schema/input risks | passed |
| findings cover execution/observability risks | passed |
| tests cover deterministic findings and CLI behavior | passed |
| no workflow, marketplace, vault, billing, hosted public CRUD, gateway permission source, or automatic propagation is added | passed |

## Validation

Passed:

```text
python -m py_compile api2agent\diagnostics.py api2agent\cli.py api2agent\generators\package.py api2agent\generators\readme.py
```

Passed:

```text
pytest tests\test_diagnostics.py tests\test_generators.py tests\test_cli.py
```

Result:

```text
52 passed
```

Passed:

```text
pytest
```

Result:

```text
177 passed
```

Passed:

```text
git diff --check
```

## Closeout Judgment

This implementation slice is complete.

Quality diagnostics now gives API2Agent a reusable feedback layer for compiler expansion:

- developers get concrete findings instead of silent package generation
- large or vague packages can be flagged before Agent wiring
- write-only packages are called out before unsafe testing
- auth/schema/observability issues become deterministic testable outputs
- generated package compatibility is preserved

This is a good foundation for the next compiler expansion phase.

## Remaining Risks

### Findings Need Calibration Against More Real Specs

Current dogfood covers fixtures and local curl examples. Larger real OpenAPI specs may reveal noisy findings, missing finding categories, or score calibration issues.

### Diagnostics Are Advisory

Warnings do not block generation by default. This is correct for v0, but CI-style enforcement may eventually need `--fail-on warning|error`.

### Schema Quality Is Still Shallow

Diagnostics can flag broad or missing schemas, but it does not yet improve nested schema shaping, enum/example propagation, or Agent-facing input simplification.

### OpenAPI Complexity Remains The Next Big Compiler Gap

Multiple servers, security combinations, nested request bodies, examples/defaults, and filtering diagnostics still need a deeper design.

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Real-World Hardening Design v0
```

That design should define how diagnostics, OpenAPI parsing, package generation, tests, and dogfood work together to improve real-world OpenAPI onboarding without broadening API2Agent into workflow runtime or hosted product scope.
