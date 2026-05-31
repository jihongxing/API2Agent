# API2Agent Tooling Re-entry Closeout + Phase Review v0

Date: 2026-05-31

Status: complete

## Decision

The Tooling Re-entry phase can pause.

The current Tooling Layer is now strong enough to return to the next infrastructure task or wait for new product requirements without leaving an unfinished hardening backlog.

The originally recommended next engineering task was:

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```

That design, CLI implementation, live Postgres dogfood, and readiness review are now complete. Current next engineering task:

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

If new product requirements are coming, pause implementation and update PRD/roadmap before starting that task.

## Phase Goal

The re-entry goal was:

```text
Return to API2Agent Tooling with Control/Data Plane constraints,
increase real execution data,
lower API/provider onboarding cost,
and improve response-speed readiness,
without becoming a workflow engine.
```

That goal is met for the current API-first scope.

## Completed Capabilities

### Baseline and Scope

- Tooling Re-entry Review + Expansion Plan documented the constrained return to the Tooling Layer.
- Tooling implementation language decision kept Python as the reference tooling implementation and Go as the production Data/Control Plane direction.
- Tooling Baseline Audit documented real curl/OpenAPI onboarding behavior.

Evidence:

- 4/4 curl inputs generated successfully.
- 4/4 curl inputs achieved first successful direct execution.
- 3/3 no-auth proxy paths achieved first successful proxy execution.
- GitHub REST OpenAPI still exposes the large-spec risk with 1186 unfiltered tools and 3 filtered tools.

### Lower Onboarding Cost

Completed:

- OpenAPI filtering + curl tool naming hardening
- endpoint-level auth inference
- base URL override
- manual write test path
- curl naming residual review

Impact:

- mixed public/protected APIs no longer force auth before testing public endpoints
- local/staging/regional/self-hosted APIs can be tested without patching generated source
- write/delete tests are explicit and guarded
- generic curl names such as `api` are reduced for common `api.*` and `www.*` hosts
- root-path curl tools carry capability intent

### More Real Execution Data

Completed:

- proxy-mode credential dogfood expansion
- generated runner credential intent propagation
- proxy usage metadata preservation for credential, provider region, cost, and selected tool
- manual write proxy dogfood path

Impact:

- generated packages can feed observable proxy execution without raw provider secret leakage
- usage events keep stable tool/provider/capability identity
- write-like tools can be tested intentionally while still producing usage evidence

### Faster Response Readiness

Completed:

- generated package provider-region metadata
- generated package latency benchmark helper
- p50/p95 generated package benchmark output
- base URL override for local/staging/regional endpoints
- large spec performance and inspect/test usability

Impact:

- generated packages now carry enough region and latency metadata to support future location-aware routing work
- developers can compare direct vs proxy execution timing
- large OpenAPI packages have summary, filtering, and targeted test paths instead of raw endpoint dumps only

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| At least five real API onboarding attempts documented | passed |
| Generated packages run safe read paths without manual source edits | passed |
| Generated packages run through proxy mode where credentials allow it | passed |
| Usage events contain stable identity and credential-safe metadata | passed |
| Benchmark output includes latency data | passed |
| API-first and no-workflow-engine constraints remain explicit | passed |

## Validation

Last full validation:

```text
python scripts/api2agent_curl_naming_residual_review.py
python scripts/api2agent_tooling_baseline_audit.py
python -m pytest
169 passed

go test ./...   # services/data-plane
go test ./...   # services/control-plane
```

Recent dogfood scripts added or re-run:

- `scripts/api2agent_tooling_baseline_audit.py`
- `scripts/api2agent_generated_region_metadata_dogfood.py`
- `scripts/api2agent_proxy_credential_dogfood.py`
- `scripts/api2agent_generated_package_latency_benchmark_dogfood.py`
- `scripts/api2agent_endpoint_auth_inference_dogfood.py`
- `scripts/api2agent_base_url_override_dogfood.py`
- `scripts/api2agent_manual_write_test_path_dogfood.py`
- `scripts/api2agent_large_spec_performance_dogfood.py`
- `scripts/api2agent_curl_naming_residual_review.py`

## Remaining Risks

These do not block phase closeout, but should remain visible:

- Large OpenAPI specs are still allowed unfiltered by default; API2Agent warns and guides, but does not auto-slice.
- Generated package UX is still CLI/docs-first, not a polished hosted onboarding UI.
- Real API dogfood coverage is useful but still small.
- Generated package runtime remains Python reference tooling; production neutrality depends on JSON/YAML artifacts and Go plane compatibility.
- Tooling still does not support non-API sources such as workflows, functions, databases, or human tasks by design.
- Hosted Control Plane write-side mutation remains paused until import/replace transaction design is done.

## Non-Goals Preserved

The phase did not implement:

- workflow engine
- non-API runtime
- marketplace
- billing
- credential vault
- hosted SaaS onboarding
- provider settlement

## Closeout Judgment

This phase achieved the intended re-entry:

```text
API input
  -> cheaper generated package
  -> safer direct/proxy execution
  -> better metadata
  -> more observable calls
```

Recommendation:

1. Pause Tooling Re-entry.
2. Preserve the current reports as the v0.1-alpha Tooling evidence set.
3. Return to the previously paused Control Plane write-side design unless product requirements are updated first.

Current next task:

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```
