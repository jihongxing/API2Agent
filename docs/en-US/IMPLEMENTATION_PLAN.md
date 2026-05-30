# API2Agent Implementation Plan

## 1. Current Build Target

The current repository implements the Free Tooling Layer:

```text
OpenAPI / curl
  -> API2Agent IR
  -> filtered capability package
  -> generated runner
  -> generated smoke test
  -> generated MCP server
```

This proved local usability and the first controlled execution loop.

Current phase:

```text
Python MVP freeze
  -> Protocol v0.2 contract freeze
  -> Production Architecture RFC
  -> Control Plane / Data Plane split
```

The Python implementation remains the reference implementation, local tooling surface, and dogfood harness. It should not expand into the long-term hosted data plane.

## 2. Current Repository Structure

```text
api2agent/
  cli.py
  filters.py
  ir/
    models.py
  parsers/
    openapi.py
    curl.py
  generators/
    package.py
    runner.py
    tools.py
    mcp.py
    readme.py
    smoke_test.py
  safety/
    classifier.py
tests/
  fixtures/
docs/
  en-US/
  cn-ZH/
```

## 3. Completed Tooling Milestones

- Project skeleton
- API2Agent IR
- OpenAPI parser
- curl parser
- safety classifier
- package generator
- runner generator
- smoke test generator
- MCP server generator
- MCP stdio integration test
- tool filtering / selection
- bilingual docs
- open-core license
- control layer MVP
- capability/provider/routing model
- usage, ledger, replay, shadow, and golden trace
- credential orchestration MVP
- region-aware routing and provider-region selection
- decision dataset seed
- MVP exit review
- Architecture Definition Phase documentation
- API2Agent Protocol v0.2 planning document

## 4. Remaining Tooling Reliability Work

These are still valuable, but they are no longer the strategic endpoint:

1. Endpoint-level auth
2. Base URL override
3. Manual write test path
4. Better curl naming
5. Large spec performance

Do not expand into many new input formats before proxy and metrics exist.

## 5. Next Major Build: Control Layer MVP

Goal:

```text
generated package
  -> API2Agent Proxy
  -> third-party API
  -> usage event
```

### Step 1: Usage Event Schema

Define a neutral event model:

- project_id
- capability_id
- provider_id
- tool_id
- timestamp
- method
- path
- status_code
- success
- latency_ms
- estimated_cost
- error_type

Done when:

- event model can serialize to JSON
- tests cover success and failure events

### Step 2: Proxy Call Contract

Define:

```http
POST /v1/proxy/call
```

Request:

```json
{
  "capability_id": "github_repos",
  "tool_id": "list_repos",
  "provider_id": "github",
  "params": {}
}
```

Done when:

- contract is documented
- runner can be generated in direct mode or proxy mode

### Step 3: Local Proxy Prototype

Build a minimal local service first.

Suggested stack:

- FastAPI or simple ASGI app
- SQLite for usage events
- httpx for forwarding
- pytest for proxy tests

Done when:

- proxy forwards one generated tool call
- proxy records a usage event
- proxy returns structured success/error result

### Step 4: Quota MVP

Add project-level quota:

- max calls per project
- quota exceeded error
- usage count query

Done when:

- proxy blocks calls after quota
- quota event is recorded clearly

### Step 5: Metrics Report

Add CLI or endpoint report:

- total calls
- success rate
- average latency
- estimated cost
- error type counts

Done when:

- user can see whether an API capability is reliable and expensive

## 6. Capability Layer MVP

This layer starts with a minimal machine-readable schema.

Define:

- Capability Schema v0.1
- Provider Candidate model
- mapping from tool to capability
- metrics snapshot per candidate

Done when:

- two providers can map to one capability
- metrics can be compared

## 7. Routing Layer MVP

Routing v0 supports simple policies:

- random
- lowest estimated cost
- highest observed success rate
- lowest average latency
- balanced score

Done when:

- a capability request can route to one of two providers
- routing decision is logged
- failover can try a second provider

CLI:

```bash
api2agent route capability-registry.json \
  --capability-id image_generation \
  --strategy lowest_cost \
  --db api2agent-usage.sqlite
```

Minimal provider registry:

```json
{
  "providers": [
    {
      "id": "provider_a",
      "capability_id": "image_generation",
      "provider_id": "a",
      "tool_id": "generate",
      "estimated_cost": 0.02
    }
  ]
}
```

## 8. Credential Orchestration MVP

Credential orchestration comes before billing and marketplace work.

Define:

- Credential Schema v0.1
- owner types: user, project, platform, provider
- sources: env, config, inline, none
- resolver order
- injection patch contract
- usage event `credential_reference`
- redaction rules

Done when:

- one authenticated API can be called with a resolved local credential
- raw secrets are not stored in usage events
- replay warns when exact replay needs a credential that cannot be resolved
- ledger can preserve credential attribution without exposing secrets

Current implementation:

- Credential Schema v0.1 code models are implemented.
- Local resolver supports env/config/inline/none.
- Generated package execution can inject credentials.
- Usage events record `credential_reference`.
- Local package replay can re-resolve credentials from redacted metadata.
- Generated package proxy mode sends credential intent instead of provider secrets.
- Local proxy resolves credential intent and injects provider auth before forwarding.
- Local proxy can load JSON/YAML credential config through `--credential-config`.
- Config credentials can be used as provider-level fallback when payload credential intent is absent.
- Credential precedence is deterministic: inline, config, request/env intent, none.
- Config credential ownership prefers exact project owner, then local owner, then config order.
- Credential scope can restrict access by provider, capability, tool, or wildcard.
- Out-of-scope credentials fail with redacted `credential_scope_denied` errors.
- Credential lifecycle metadata supports status, expiry, and rotation hints.
- Disabled and expired credentials fail with redacted machine-readable errors.
- Usage CLI can print secret-safe credential audit events and failure counts.
- Real authenticated proxy credential dogfood passed against httpbin bearer auth.
- New strategic priority: maximize real execution data and minimize API/provider onboarding cost.
- New routing requirement: location-aware execution and region-aware latency.
- Region-aware usage schema, provider metadata, and decision dataset contract are implemented locally.
- `region_aware_latency` routing strategy is implemented.
- `api2agent route` and `api2agent call` accept `--client-region`.
- routing decisions persist `client_region`.
- routing decisions persist deterministic `selected_provider_region`.
- generated package usage events record derived `provider_region`.
- Python MVP has reached its documented exit criteria.
- Architecture Definition Phase is active.
- Protocol v0.2 freeze planning is documented.
- Protocol v0.2 frozen contract is documented.
- Protocol v0.2 machine-readable schema snapshot is available.
- Production Architecture RFC is documented.
- Data Plane and Control Plane backend direction is Go.
- Python reference migration plan is documented.
- Go Data Plane Skeleton plan is documented.
- Go Data Plane Skeleton implementation is present under `services/data-plane`.
- Go/Python dual-run dogfood passed for `network.public_ip.get`.
- Python is frozen as a reference implementation and local dogfood harness, not the production data plane.
- Go Data Plane Skeleton hardening is complete:
  - `/healthz` exposes protocol and snapshot metadata.
  - snapshot TTL parsing and expiration helpers are implemented.
  - project-key bearer auth, timeout failure mapping, missing-adapter failed decisions, and event sequence IDs are covered by Go tests.
- Go Data Plane protocol conformance and failover dogfood are complete:
  - emitted RequestContext, RoutingDecision, UsageEvent, and DecisionLog records are checked against the v0.2 schema snapshot.
  - failover policy can retry a controlled HTTP 500 primary provider and succeed on a fallback provider.
  - each attempt writes a UsageEvent, and DecisionLog aggregates both attempt IDs.
  - see `docs/en-US/GO_DATAPLANE_FAILOVER_DOGFOOD_REPORT.md`.
- Go Data Plane env credential resolution skeleton is complete:
  - `/v1/execute` accepts a request-level credential intent.
  - local env-backed secrets can be resolved and injected into provider requests.
  - usage events record `credential_reference` and redacted credential metadata only.
  - missing env secrets fail before provider forwarding and still write a failed UsageEvent.
  - see `docs/en-US/GO_DATAPLANE_CREDENTIAL_DOGFOOD_REPORT.md`.
- Go Data Plane durable event ingestion is complete:
  - JSONL event writer fsyncs each event before returning.
  - writer startup recovers the next event sequence ID from existing `events.jsonl`.
  - corrupt existing event logs fail startup instead of silently resetting sequence state.
  - restart dogfood produced monotonic sequence IDs `1..8` across two Data Plane process runs.
  - see `docs/en-US/GO_DATAPLANE_DURABLE_EVENTS_DOGFOOD_REPORT.md`.
- Go Data Plane real external provider retry dogfood is complete:
  - `httpbin/status/500` writes a failed first `UsageEvent`.
  - `httpbin/ip` succeeds as the fallback attempt and returns normalized `{"ip": ...}` output.
  - `DecisionLog` records success and references both usage attempts.
  - the dogfood also captured a failed `api.ipify.org` fallback attempt from the local Go runtime, proving external API availability must be measured from the actual execution runtime.
  - see `docs/en-US/GO_DATAPLANE_REAL_EXTERNAL_PROVIDER_RETRY_DOGFOOD_REPORT.md`.
- Go Data Plane stage review is complete:
  - the current stage is summarized in `docs/en-US/GO_DATAPLANE_STAGE_REVIEW.md`.
  - the next hardening slice is narrowed to conformance validation, event write failure policy, and runtime provider availability probing.
- Go Data Plane Consolidation Hardening v0 is complete:
  - reusable Protocol v0.2 conformance validator is available in Go.
  - durable and real external retry dogfood scripts validate emitted JSONL events.
  - event write failures now fail closed with `EVENT_WRITE_FAILED`.
  - runtime provider reachability probe is dogfooded.
  - see `docs/en-US/GO_DATAPLANE_CONSOLIDATION_HARDENING_REPORT.md`.
- Timeout Budget Semantics v0 is complete:
  - `timeout_budget_ms` is enforced as a request-level total deadline.
  - each provider attempt receives only the remaining request budget.
  - fallback is skipped when the total budget is exhausted.
  - `UsageEvent.request_metadata` records total, attempt, remaining, and policy timeout metadata.
  - `DecisionLog.routing_context` records timeout budget exhaustion state.
  - local dogfood covers slow-primary exhaustion and fast-failure fallback.
  - see `docs/en-US/GO_DATAPLANE_TIMEOUT_BUDGET_DOGFOOD_REPORT.md`.
- Snapshot Freshness Gate v0 is complete:
  - `/v1/execute` checks snapshot TTL before routing.
  - expired snapshots fail closed with `SNAPSHOT_EXPIRED`.
  - invalid snapshot TTL fails closed with `SNAPSHOT_INVALID`.
  - expired snapshots do not call provider adapters.
  - failed freshness checks still emit `RequestContext` and failed `DecisionLog`.
  - `/healthz` reports expired snapshots as `degraded`.
  - see `docs/en-US/GO_DATAPLANE_SNAPSHOT_FRESHNESS_DOGFOOD_REPORT.md`.
- Project Quota Gate v0 is complete:
  - Go Data Plane can enforce a local process-level project quota.
  - quota is configured with `API2AGENT_PROJECT_QUOTA`.
  - quota failures return `QUOTA_EXCEEDED` with HTTP `429`.
  - quota failures do not call provider adapters.
  - quota failures still emit `RequestContext` and failed `DecisionLog`.
  - see `docs/en-US/GO_DATAPLANE_PROJECT_QUOTA_DOGFOOD_REPORT.md`.
- Go Data Plane Credential Config v0 is complete:
  - Go Data Plane can load local JSON credentials through `API2AGENT_CREDENTIAL_CONFIG`.
  - config credentials can inject provider auth without per-request credential intent.
  - config credential references are recorded as `config:<credential_id>`.
  - raw secrets are not written to emitted events.
  - config credential scope and lifecycle checks are enforced.
  - see `docs/en-US/GO_DATAPLANE_CREDENTIAL_CONFIG_DOGFOOD_REPORT.md`.
- Go Data Plane Credential Audit Metadata v0 is complete:
  - local credential definitions can carry `credential_version`.
  - credential resolution records safe `resolved_at` audit metadata.
  - rotation hints and lifecycle status are preserved in redacted usage metadata.
  - Protocol v0.2 `CredentialReference` remains unchanged; audit extensions stay under `UsageEvent.request_metadata.credential`.
  - see `docs/en-US/GO_DATAPLANE_CREDENTIAL_CONFIG_DOGFOOD_REPORT.md`.
- Execution Event Ordering / Attempt Correlation v0 is complete:
  - each provider attempt uses its `UsageEvent.id` as the attempt id.
  - fallback attempts set `UsageEvent.parent_attempt_id` to the previous attempt id.
  - attempt ids and parent ids are also present in safe request metadata.
  - `DecisionLog.routing_context.attempt_chain` records ordered attempt correlation.
  - controlled and real external retry dogfoods validate the attempt chain.
- Go Data Plane Milestone Closeout + Phase 6 Readiness Review is complete:
  - local Go Data Plane execution and observability primitive is closed.
  - Phase 6 is approved to begin as a local Go Control Plane minimum.
  - readiness is conditional: no hosted public alpha, billing, or marketplace yet.
  - see `docs/en-US/GO_DATAPLANE_MILESTONE_CLOSEOUT.md`.

Next engineering task:

```text
Go Control Plane Minimum v0
```

Initial scope:

1. Project model
2. API2Agent project API key model
3. Capability registry model
4. Provider registry model
5. Credential metadata model without secret storage
6. Routing snapshot export format consumed by the existing Go Data Plane

Current Phase 6 progress:

- Go Control Plane Minimum v0 is complete:
  - `services/control-plane` contains the initial Go module.
  - `api2agent-controlplane export-snapshot` exports a Data Plane-compatible routing snapshot from local registry JSON.
  - local registry JSON covers projects, API keys, capabilities, providers, credential metadata, routing policy, and snapshot export metadata.
  - Go Data Plane loads a Control Plane exported snapshot and preserves exporter metadata.
  - cross-plane dogfood proves `Control Plane registry -> snapshot export -> Data Plane execute`.
  - see `docs/en-US/GO_CONTROL_PLANE_MINIMUM_DOGFOOD_REPORT.md`.
- Control Plane Registry Validation v0 is complete:
  - registry validation enforces unique project, API key, capability, provider, and credential ids.
  - API keys must reference known projects.
  - providers must reference known capabilities and matching capability versions.
  - active providers must include `metadata.base_url`.
  - routing strategy, routing mode, failover policy, snapshot source, and snapshot TTL are validated.
  - credential metadata validates owner/project references, provider references, status, auth type, injection mode, source, and scope references.
  - dogfood verifies invalid registries are rejected before snapshot export.
- Control Plane Snapshot Compatibility Gate v0 is complete:
  - Go Data Plane provides `api2agent-snapshot-check`.
  - the snapshot checker loads exported snapshots, parses TTL, validates required capability/provider/routing fields, and reports JSON.
  - Control Plane minimum dogfood now gates snapshot export with `api2agent-snapshot-check` before Data Plane execution.
  - this protects the Control Plane/Data Plane contract from silent drift.
- Control Plane Registry Store v0 is complete:
  - `registry.Store` defines the Control Plane state source boundary.
  - `registry.FileStore` is the current local implementation.
  - `api2agent-controlplane export-snapshot` now loads registry state through the store interface.
  - future hosted phases can add a Postgres-backed store without changing snapshot export semantics.
- Control Plane Snapshot Versioning Policy v0 is complete:
  - snapshots continue to require explicit `snapshot.version`.
  - exported snapshots include `snapshot_version_policy=explicit`.
  - exported snapshots include deterministic `registry_fingerprint=sha256:<hash>` metadata.
  - registry fingerprints are stable for identical registry content and change when registry content changes.
  - `api2agent-snapshot-check` reports version policy and registry fingerprint metadata.
- Control Plane Snapshot Export Artifact v0 is complete:
  - `api2agent-controlplane export-artifact` writes an artifact directory instead of only a bare snapshot file.
  - artifact layout is `snapshot.json` plus `manifest.json`.
  - the manifest records artifact version, export time, registry store/source, snapshot file/version/source, snapshot version policy, registry fingerprint, and validation summary.
  - Control Plane minimum dogfood verifies manifest existence, snapshot reference, registry fingerprint agreement with `api2agent-snapshot-check`, and valid registry validation summary before Data Plane execution.
  - this creates the local artifact boundary needed before snapshot distribution.
- Control Plane Snapshot Distribution Stub v0 is complete:
  - `api2agent-controlplane publish-artifact` publishes an artifact directory into a local distribution directory.
  - distribution layout is `current.json` plus `artifacts/<snapshot_version>/snapshot.json` and `artifacts/<snapshot_version>/manifest.json`.
  - `current.json` records distribution version, publish time, snapshot version, artifact file references, registry fingerprint, and snapshot version policy.
  - Go Data Plane snapshot loading now accepts a bare snapshot file, a distribution directory containing `current.json`, or a direct `current.json` path.
  - `api2agent-snapshot-check` can validate a distribution directory because it uses the same snapshot resolver.
  - cross-plane dogfood proves `Control Plane registry -> artifact export -> local distribution publish -> Data Plane execute`.
  - see `docs/en-US/GO_CONTROL_PLANE_SNAPSHOT_DISTRIBUTION_DOGFOOD_REPORT.md`.
- Control Plane Snapshot Refresh / Reload Policy v0 is complete:
  - Data Plane default snapshot policy remains `startup_only`.
  - local manual reload is enabled only with `API2AGENT_SNAPSHOT_RELOAD_POLICY=manual`.
  - `POST /v1/admin/reload-snapshot` reloads the configured snapshot source, including a distribution directory whose `current.json` has changed.
  - `/healthz` reports snapshot reload policy, loaded-at timestamp, source path, and resolved snapshot path.
  - if `API2AGENT_PROJECT_KEY` is set, the reload endpoint requires the same bearer token as `/v1/execute`.
  - cross-plane dogfood proves v1 startup, v2 distribution publish, manual reload, and v2 execution event attribution.
  - see `docs/en-US/GO_DATAPLANE_SNAPSHOT_RELOAD_DOGFOOD_REPORT.md`.
- Control Plane Snapshot Reload Failure Semantics v0 is complete:
  - reload is atomic from the serving snapshot point of view: failed reload does not replace the active snapshot.
  - failed reload returns `SNAPSHOT_RELOAD_FAILED`, `reloaded=false`, `kept_snapshot_version`, current `snapshot_resolved_to`, and retryable error metadata.
  - `/healthz` remains on the previous snapshot after a failed reload.
  - cross-plane dogfood proves broken `current.json` failure keeps v1 active, then valid v2 publish and reload succeeds.
- Control Plane Snapshot Reload Audit Events v0 is complete:
  - Data Plane writes `snapshot_reload_event` for failed and successful reload attempts.
  - successful reload writes the audit event before swapping the active snapshot.
  - failed reload writes an audit event while keeping the previous snapshot active.
  - reload audit events share the same append-only event stream and event sequence IDs as execution events.
  - cross-plane dogfood verifies failed reload audit, successful reload audit, and execution graph ordering.
  - see `docs/en-US/GO_DATAPLANE_SNAPSHOT_RELOAD_AUDIT_DOGFOOD_REPORT.md`.
- Control Plane Snapshot Version Compatibility Guard v0 is complete:
  - Control Plane exported snapshots include `metadata.schema_version=api2agent.protocol.v0.2`.
  - Data Plane snapshot loading rejects snapshots that declare a different `metadata.schema_version`.
  - the guard applies to startup load, `api2agent-snapshot-check`, and manual reload because they use the same snapshot loader.
  - legacy local snapshots without `metadata.schema_version` are still accepted for now.
  - cross-plane dogfood verifies incompatible v3 reload is rejected, v2 remains active, and execution continues on v2.
  - see `docs/en-US/GO_DATAPLANE_SNAPSHOT_COMPATIBILITY_GUARD_DOGFOOD_REPORT.md`.

## 9. Marketplace Is Later

Do not build a marketplace UI before:

- proxy works
- credential orchestration exists
- metrics exist
- capability abstraction exists
- routing works
- pricing metadata exists

Marketplace should be the result of routing plus economics, not the starting point.
