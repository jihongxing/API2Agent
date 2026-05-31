# API2Agent Tooling Re-entry Review + Tooling Expansion Plan v0

Date: 2026-05-31

Status: complete

## Summary

It is appropriate to pause deeper Control Plane implementation and return to the API2Agent Tooling Layer.

This is not a retreat to a one-shot generator. It is a constrained re-entry:

```text
API -> Agent-ready package -> default observable execution path -> real usage data
```

The Tooling Layer should now optimize for three product goals:

1. more real execution data
2. lower API/provider onboarding cost
3. faster response for Agent API calls

The implementation boundary remains API-first. API2Agent must not become a workflow engine.

## Why Now

The infrastructure track has reached a good pause point:

- Go Data Plane has proven execution, event ordering, retry/failover, credentials, timeout budgets, quota, and durable event ingestion.
- Go Control Plane has proven snapshot export, distribution, service API, Postgres load parity, runtime wiring, live Postgres dogfood, persistent audit writes, failure semantics, and mutation boundary review.
- The next Control Plane task is design work for import/replace transactions, not an urgent runtime blocker.

This means the project can safely return to the top of the funnel: making more real APIs easier to convert into reliable Agent capabilities.

## Re-entry Decision

Decision:

```text
Pause deeper Control Plane write-side work.
Resume API2Agent Tooling Layer expansion under Control/Data Plane constraints.
```

Implementation language decision:

```text
Continue Tooling Re-entry in Python as the reference tooling implementation.
Keep production execution and control paths in Go.
Keep protocol artifacts language-neutral.
```

See `docs/en-US/TOOLING_IMPLEMENTATION_LANGUAGE_DECISION.md`.

The Tooling Layer is now responsible for feeding the execution/data flywheel:

```text
lower onboarding cost
  -> more generated packages
  -> more calls through observable paths
  -> more usage/latency/cost/error data
  -> better routing and reliability
```

## Product Goals

### Goal 1: More Real Execution Data

Tooling should increase the number of real API calls that API2Agent can observe.

Tooling implications:

- generated packages should make proxy/observable execution easy to choose
- generated packages should preserve capability/provider/tool identity
- generated packages should emit enough metadata for usage, replay, routing, and future receipts
- generated packages should keep credential intent separate from raw provider secrets
- quickstarts and dogfoods should prefer real APIs over synthetic examples when safe

Success signals:

- more successful real API dogfoods
- more generated packages that run through proxy mode without manual edits
- more usage events with stable `capability_id`, `provider_id`, `tool_id`, `execution_mode`, `credential_reference`, and latency metadata

### Goal 2: Lower API/Provider Onboarding Cost

Tooling should make API onboarding cheaper than hand-writing Agent tools.

Tooling implications:

- OpenAPI import should handle common real-world specs with less manual patching
- curl import should infer better names, auth, parameters, and defaults
- large specs should be filtered into Agent-usable packages
- generated docs should show the minimum useful call path
- generated smoke tests should be safe by default but useful enough to verify integration

Success signals:

- time from OpenAPI/curl input to first successful call decreases
- fewer manual edits needed after generation
- fewer generated packages with vague names like `api`
- large specs produce focused packages instead of unusable endpoint dumps

### Goal 3: Faster Response

Tooling should help generated capabilities return useful responses faster.

Tooling implications:

- generated packages should preserve provider region metadata when known
- generated runners should expose timeout controls and sensible defaults
- benchmark helpers should report p50/p95 latency
- docs should guide developers toward direct/local/proxy modes intentionally
- generated provider metadata should support future location-aware routing

Success signals:

- generated package dogfoods include latency results
- p50/p95 latency is visible in benchmark outputs
- provider region metadata is present when APIs expose it or users configure it
- generated runners avoid avoidable overhead in direct local execution

## Hard Constraints

### API-first

Current implementation scope remains:

- OpenAPI
- curl
- HTTP/REST APIs
- generated capability package
- generated runner
- generated smoke test
- generated MCP server

### Not a Workflow Engine

Do not implement:

- workflow engine execution
- Zapier/n8n/Temporal/Airflow orchestration
- local function runtime
- arbitrary script sandbox
- database runtime
- human task routing
- agent-as-provider runtime

Workflow systems may later be invoked through API-like adapters or endpoints, but API2Agent must not become the workflow engine.

### Not Marketplace Work

Do not implement:

- marketplace UI
- provider public onboarding
- provider revenue share
- billing or settlement
- marketplace ranking edits

Marketplace remains a far-term result of reliable execution, control, routing, metrics, and economics.

### Preserve Control Layer Compatibility

Tooling work must preserve:

- proxy mode
- credential-safe generated runners
- usage event identity fields
- routing decision compatibility
- replay/shadow/golden trace paths
- Protocol v0.2 direction
- Go Data Plane snapshot compatibility when generated packages become provider candidates

### Preserve Implementation Neutrality

Python is the current Tooling Layer implementation, not the protocol identity.

Tooling work must preserve:

- JSON/YAML artifacts as the stable contract boundary
- no hidden dependency on Python runtime internals from Go services
- semantic compatibility with Go Data Plane and Go Control Plane contracts where paths overlap
- future ability for TypeScript, Rust, Java, or other implementations to emit the same API2Agent artifacts

## Expansion Scope

### Track A: OpenAPI Reliability

Purpose:

Make more real OpenAPI specs generate usable Agent capability packages.

Candidate tasks:

- endpoint-level auth extraction
- base URL/server override hardening
- large spec filtering defaults
- operation naming improvements
- schema edge-case handling for common real specs
- generation diagnostics that explain skipped or risky operations

### Track B: curl Reliability

Purpose:

Make single-command API onboarding feel nearly instant.

Candidate tasks:

- better curl capability/provider/tool naming
- better Bearer/API key/header/query auth inference
- stronger query/header/body default preservation
- safer write-operation smoke-test guidance
- generated README improvements for curl-derived packages

### Track C: Generated Package Observability Defaults

Purpose:

Make generated packages naturally feed API2Agent's control and metrics layers.

Candidate tasks:

- generated package metadata audit
- proxy-mode setup simplification
- generated runner identity fields hardening
- credential intent documentation in generated README
- latency/timeout metadata propagation from generated runner paths

### Track D: Real API Dogfood Harness

Purpose:

Increase real execution data without adding hosted infrastructure.

Candidate tasks:

- maintain a small catalog of safe read-only real API dogfoods
- run generated packages through direct and proxy modes
- record onboarding steps, manual edits, first-call time, success, cost estimate, and latency
- produce a tooling benchmark report

### Track E: Speed and Region Readiness

Purpose:

Prepare generated packages for faster execution and future location-aware routing.

Candidate tasks:

- optional provider region metadata in generated packages
- generated benchmark command/report for p50/p95 latency
- timeout defaults in generated runner docs
- direct vs proxy latency comparison dogfood

## Prioritized Sprint Plan

### Sprint 1: Tooling Baseline Audit

Output:

```text
API2Agent Tooling Baseline Audit v0
```

Measure:

- OpenAPI generation success
- curl generation success
- first successful call path
- manual edits required
- generated naming quality
- proxy compatibility
- credential safety
- p50/p95 latency where calls are safe

Recommended real inputs:

- GitHub REST read endpoint
- httpbin bearer/read endpoints
- ipify public IP
- Open-Meteo weather
- one medium/large OpenAPI spec

### Sprint 2: Low-Cost Onboarding Fixes

Target fixes:

- endpoint-level auth
- base URL override
- curl naming
- generated README guidance
- safer manual write-test path design

### Sprint 3: More Data by Default

Target fixes:

- proxy-mode setup simplification
- generated runner identity metadata checks
- credential intent examples
- direct/proxy dogfood report

### Sprint 4: Faster Response Readiness

Target fixes:

- generated package latency benchmark helper
- p50/p95 reporting
- optional provider region metadata
- direct vs proxy latency comparison

## Acceptance Criteria

The re-entry is successful when:

- at least five real API onboarding attempts are documented
- generated packages can run without manual source edits for the safe read paths
- generated packages can run through proxy mode where credentials allow it
- usage events contain stable identity and credential-safe metadata
- benchmark output includes latency data
- docs clearly preserve API-first and no-workflow-engine constraints

## Recommended Next Task

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

The baseline audit, onboarding hardening, provider-region metadata, authenticated proxy credential dogfood, generated-package latency benchmark, endpoint-level auth inference, base URL override, manual write test path, large spec performance, curl naming residual review, and Tooling Re-entry closeout slices are complete.

The Tooling Re-entry phase is now paused. The Control Plane import/replace transaction design, CLI implementation, live Postgres dogfood, and readiness review are also complete, so the next engineering task is private admin endpoint design.

## Non-Goals

- No Control Plane mutation API work in this re-entry plan.
- No workflow engine.
- No new non-API capability source runtime.
- No hosted SaaS implementation.
- No vault.
- No billing.
- No marketplace.
