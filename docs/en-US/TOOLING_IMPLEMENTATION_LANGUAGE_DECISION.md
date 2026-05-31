# Tooling Implementation Language Decision

Date: 2026-05-31

Status: accepted

## Decision

API2Agent Tooling Re-entry continues in Python.

Python remains the Tooling Layer reference implementation, local CLI surface, package generator, and dogfood harness. This does not make API2Agent a Python-bound project.

The project stays technology-neutral by making the stable contracts language-neutral:

- API2Agent IR
- capability package metadata
- generated tool schemas
- provider candidate metadata
- credential intent metadata
- usage, routing, ledger, replay, shadow, golden trace, and receipt-ready event contracts
- Control Plane snapshots consumed by the Go Data Plane

Implementation split:

```text
Python:
  OpenAPI/curl parsing
  IR generation
  package generation
  generated README/smoke test/MCP server
  local CLI
  Tooling baseline audits
  local dogfood harness

Go:
  production Data Plane
  production proxy path
  routing hot path
  retry/failover
  timeout budget enforcement
  durable event ingestion
  Control Plane registry, snapshot, distribution, and persistence
```

## Why This Is Compatible With Neutrality

API2Agent's neutrality is a protocol and artifact property, not a requirement that every early implementation be rewritten in multiple languages.

The neutral boundary is:

```text
API input -> language-neutral API2Agent artifacts -> runtime-specific implementations
```

Python is allowed to be the fastest reference tooling implementation as long as:

- generated artifacts are JSON/YAML contract objects, not Python-only objects
- generated packages preserve protocol identity fields
- Go services can consume the relevant artifacts without importing Python runtime internals
- tests and dogfoods validate semantic compatibility across Python and Go where the paths overlap
- future TypeScript, Rust, Java, or other SDK/tooling implementations can emit the same artifacts

## Why Not Rewrite Tooling in Go Now

The current Tooling Re-entry goals are:

1. more real execution data
2. lower API/provider onboarding cost
3. faster Agent API response visibility

These goals are mostly driven by parser quality, generation quality, generated documentation, smoke tests, proxy compatibility, credential-safe defaults, and latency metadata. Rewriting the compiler/generator stack in Go now would slow down the onboarding-cost work without materially improving the current bottleneck.

Go is still the correct direction for production execution and control infrastructure. It is not required for every tooling iteration.

## Guardrails

Python Tooling may continue to improve:

- OpenAPI reliability
- curl reliability
- operation naming
- endpoint-level auth inference
- base URL override handling
- generated package metadata
- generated smoke tests
- generated documentation
- local benchmark and dogfood helpers

Python Tooling must not expand into:

- hosted production Data Plane
- production proxy hot path
- production routing engine
- durable event ingestion service
- hosted Control Plane
- billing, settlement, or credential vault
- workflow engine or non-API runtime

If a future change requires production execution semantics, it should be implemented in Go or behind a language-neutral contract first.

## Handoff Rule

Future contributors should not interpret "continue in Python" as "keep adding production runtime features to Python."

The intended meaning is:

```text
Use Python to improve API-first onboarding and reference tooling.
Use Go for production execution and control paths.
Keep the protocol and emitted artifacts language-neutral.
```

