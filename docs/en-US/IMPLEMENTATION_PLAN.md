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
Hosted Admin Trusted Gateway Service Dogfood Complete
```

The Python implementation remains the reference implementation, local tooling surface, and dogfood harness. The Tooling Re-entry hardening backlog is complete, and the current Go Control Plane gate is closeout of the trusted-gateway hosted admin service dogfood.

Implementation language decision:

```text
Python = Tooling reference implementation and local dogfood harness.
Go = production Data Plane and Control Plane implementation.
Protocol artifacts = language-neutral boundary.
```

See `docs/en-US/TOOLING_IMPLEMENTATION_LANGUAGE_DECISION.md`.

Current Tooling Layer goals:

1. more real execution data
2. lower API/provider onboarding cost
3. faster Agent API responses

Current Tooling Layer constraints:

- API-first
- no workflow engine
- no new non-API runtime
- no marketplace
- no billing
- no vault
- preserve proxy, usage, credential, replay, shadow, golden trace, and Protocol v0.2 compatibility

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

The active Tooling Re-entry hardening backlog is complete, and the closeout review is complete.

Recently completed:

- Manual write test path
- Large spec performance
- Better curl naming residual review
- Tooling Re-entry closeout review

Do not expand into many new input formats. The current tooling expansion remains API-first: OpenAPI, curl, HTTP/REST, generated packages, generated runner, smoke test, and MCP server.

Current re-entry plan:

- see `docs/en-US/API2AGENT_TOOLING_REENTRY_REVIEW_AND_EXPANSION_PLAN.md`

Next tooling task:

```text
none - Tooling Re-entry is paused after closeout
```

Next engineering task:

```text
Go Control Plane Private Admin Import/Replace Endpoint Implementation v0
```

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
- Control Plane Snapshot Strict Metadata Requirement v0 is complete:
  - Control Plane/exported snapshots must include `metadata.schema_version`, `metadata.registry_fingerprint`, and `metadata.snapshot_version_policy`.
  - legacy local snapshots without Control Plane metadata are still accepted for now.
  - startup load, `api2agent-snapshot-check`, and manual reload share the same strict metadata guard.
  - cross-plane dogfood verifies a v4 distribution missing `registry_fingerprint` is rejected, v2 remains active, and a reload audit event is recorded.
  - see `docs/en-US/GO_DATAPLANE_SNAPSHOT_STRICT_METADATA_DOGFOOD_REPORT.md`.
- Control Plane Snapshot Metadata Manifest Consistency Guard v0 is complete:
  - Control Plane validates `snapshot.json` and `manifest.json` consistency before writing or publishing artifacts.
  - Data Plane validates `current.json`, `manifest.json`, and `snapshot.json` consistency before loading a distributed snapshot.
  - publish-time manifest mismatch is rejected before advancing `current.json`.
  - reload-time distribution tampering is rejected while the previous active snapshot remains serving.
  - see `docs/en-US/GO_DATAPLANE_SNAPSHOT_MANIFEST_CONSISTENCY_DOGFOOD_REPORT.md`.
- Control Plane Snapshot Artifact Content Digest Guard v0 is complete:
  - Control Plane artifact manifests now include `snapshot_digest=sha256:<hash>`.
  - distribution `current.json` carries the same snapshot digest for pointer-level audit.
  - Control Plane rejects artifact publish when `snapshot.json` file bytes do not match the manifest digest.
  - Data Plane rejects distributed snapshot reload when file bytes no longer match the manifest/current digest.
  - see `docs/en-US/GO_DATAPLANE_SNAPSHOT_CONTENT_DIGEST_DOGFOOD_REPORT.md`.
- Control Plane Snapshot Artifact Path Safety Guard v0 is complete:
  - Control Plane rejects unsafe `manifest.snapshot_file` references before writing or publishing artifacts.
  - Data Plane rejects unsafe `current.snapshot_file`, `current.manifest_file`, and `manifest.snapshot_file` references before reading distributed files.
  - absolute paths and `..` traversal are rejected inside distribution metadata.
  - direct `API2AGENT_SNAPSHOT=<snapshot.json>` paths remain unchanged.
  - see `docs/en-US/GO_DATAPLANE_SNAPSHOT_PATH_SAFETY_DOGFOOD_REPORT.md`.
- Control Plane Snapshot Distribution Atomic Publish Guard v0 is complete:
  - Control Plane copies artifacts through a temporary artifact directory before committing the final versioned artifact path.
  - `current.json` is written through a temporary file before replacement.
  - duplicate `snapshot_version` publishes are rejected before changing `current.json`.
  - duplicate publish dogfood verifies current remains stable and no temporary artifact dirs remain.
  - see `docs/en-US/GO_CONTROL_PLANE_SNAPSHOT_ATOMIC_PUBLISH_DOGFOOD_REPORT.md`.
- Go Control Plane Snapshot Distribution Closeout + Phase Review is complete:
  - the local snapshot distribution chain is closed from registry to artifact to distribution to Data Plane reload.
  - remaining gaps are explicitly deferred to service API, remote storage, hosted persistence, vault, billing, or marketplace stages.
  - the next implementation slice is narrowed to a local Control Plane service API skeleton.
  - see `docs/en-US/GO_CONTROL_PLANE_SNAPSHOT_DISTRIBUTION_CLOSEOUT.md`.
- Go Control Plane Service API Skeleton v0 is complete:
  - `api2agent-controlplane serve` starts a local HTTP service over the existing file registry.
  - `/healthz` is public and reports service/protocol metadata.
  - `/v1/admin/registry/validate`, `/v1/admin/snapshots/export-artifact`, `/v1/admin/distribution/publish`, and `/v1/admin/distribution/current` require admin bearer auth.
  - service dogfood verifies auth guard, registry validation, HTTP artifact export, and distribution pointer reads.
  - see `docs/en-US/GO_CONTROL_PLANE_SERVICE_API_DOGFOOD_REPORT.md`.
- Go Control Plane Service Snapshot Publish Endpoint v0 is complete:
  - `/v1/admin/distribution/publish` publishes an existing artifact into the configured local distribution.
  - the endpoint reuses the same atomic publish and duplicate-version guards as the CLI.
  - duplicate publish returns `DISTRIBUTION_ARTIFACT_EXISTS` and leaves `current.json` unchanged.
  - service dogfood now verifies HTTP export -> HTTP publish -> HTTP current pointer.
  - see `docs/en-US/GO_CONTROL_PLANE_SERVICE_API_DOGFOOD_REPORT.md`.
- Go Control Plane Service API Closeout + Hosted Persistence Readiness Review is complete:
  - the local service boundary is closed around registry validation, artifact export, distribution publish, and current pointer reads.
  - hosted persistence readiness is approved for design only, not direct database implementation.
  - the next implementation slice is narrowed to persistent registry store design.
  - see `docs/en-US/GO_CONTROL_PLANE_SERVICE_API_CLOSEOUT.md`.
- Go Control Plane Persistent Registry Store Design v0 is complete:
  - persistent registry store remains behind the existing `registry.Store` read boundary.
  - the first Postgres logical table model is documented for projects, API keys, capabilities, providers, credential metadata, routing policy, snapshot configs, registry revisions, artifact publications, and admin audit events.
  - registry load, artifact export, and distribution publish transaction boundaries are defined.
  - fingerprint, versioning, migration, and dual-store rules are documented.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_STORE_DESIGN.md`.
- Control, Receipt, and Trust Layer Strategy is documented:
  - `UsageEvent` remains the internal observation record.
  - future `Receipt` is defined as protocol-grade, verifiable execution evidence derived from execution records.
  - receipt farming and Edge-Mesh privacy requirements are captured as strategic constraints.
  - this does not change the current next task.
  - see `docs/en-US/CONTROL_RECEIPT_AND_TRUST_LAYER_STRATEGY.md`.
- Go Control Plane Persistent Registry Store Schema v0 is complete:
  - Postgres schema draft is added under `services/control-plane/schema/postgres`.
  - schema tests cover required tables and critical constraints.
  - `MapRegistryToPersistentRows` maps the existing file registry fixture into persistent row-shaped structs.
  - `CanonicalRegistry` sorts persistent export inputs without mutating the source registry.
  - `FileStore` remains the default runtime store.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_STORE_SCHEMA_REPORT.md`.
- Go Control Plane Persistence Phase Review is complete:
  - completed Data Plane and Control Plane local primitives are summarized.
  - runtime persistence readiness is approved only for a narrow load-parity slice.
  - active requirements are reaffirmed: API-first, snapshot-contract stability, no secrets in registry tables, and no marketplace/billing/vault scope.
  - the next implementation slice is narrowed to `PostgresStore.Load(ctx)` parity.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENCE_PHASE_REVIEW.md`.
- Go Control Plane PostgresStore Load Parity v0 is complete:
  - `PostgresStore.Load(ctx)` reads persistent registry rows inside a read-only `REPEATABLE READ` transaction.
  - persistent row loading rebuilds the same in-memory `Registry` shape used by `FileStore`.
  - file-backed and Postgres-loaded registries produce equivalent snapshot contract output in tests.
  - runtime store selection, Postgres driver wiring, and live DB dogfood are intentionally deferred.
  - see `docs/en-US/GO_CONTROL_PLANE_POSTGRES_STORE_LOAD_PARITY_REPORT.md`.
- Go Control Plane Persistent Store Runtime Wiring v0 is complete:
  - `--registry-store file|postgres` and `--postgres-dsn` are wired into local commands.
  - `pgx` stdlib driver support is added for explicit Postgres selection.
  - `seed-postgres` imports a file registry into the persistent schema.
  - `file` remains the default runtime store.
  - live Postgres dogfood was completed with podman because Docker and host `psql` are not available in the current environment.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_STORE_RUNTIME_WIRING_REPORT.md`.
- Go Control Plane Live Postgres Store Dogfood v0 is complete:
  - podman provisioned a temporary Postgres-compatible database.
  - schema application, seed import, file/postgres snapshot parity, CLI artifact export, service validation, and service artifact export passed.
  - file-store and postgres-store snapshot output matched exactly for the existing fixture.
  - see `docs/en-US/GO_CONTROL_PLANE_LIVE_POSTGRES_STORE_DOGFOOD_REPORT.md`.
- Go Control Plane Persistent Export/Publish Audit Writes v0 is complete:
  - Postgres runtime mode now attaches a persistent audit sink.
  - service registry validation, artifact export, distribution publish, and current pointer reads write `admin_audit_events` when persistent audit is configured.
  - successful artifact export writes `registry_revisions`.
  - successful distribution publish writes `snapshot_artifact_publications`.
  - live Postgres dogfood verified `admin_audit_events=4`, `registry_revisions=2`, and `snapshot_artifact_publications=1`.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_EXPORT_PUBLISH_AUDIT_REPORT.md`.
- Go Control Plane Persistent Store Failure Semantics Hardening v0 is complete:
  - Postgres-backed registry load failures now return `PERSISTENT_STORE_READ_FAILED` with HTTP 503, platform scope, and retryable semantics.
  - file-store load failures remain `REGISTRY_INVALID` with HTTP 400, caller scope, and non-retryable semantics.
  - successful admin operations fail closed with `AUDIT_WRITE_FAILED` when required persistent audit writes fail.
  - failure-path admin audit writes remain best-effort so original errors are preserved.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_STORE_FAILURE_SEMANTICS_REPORT.md`.
- Go Control Plane Persistent Registry Mutation Boundary Review v0 is complete:
  - granular registry CRUD APIs are deferred.
  - the next safe write-side path is a controlled full-registry import/replace transaction.
  - mutable registry state is limited to `projects`, `api_keys`, `capabilities`, `providers`, `credential_metadata`, `routing_policies`, and `snapshot_configs`.
  - `registry_revisions`, `snapshot_artifact_publications`, and `admin_audit_events` remain append-only evidence surfaces.
  - transaction, audit, idempotency, failure, and rollback requirements are documented before implementation.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_MUTATION_BOUNDARY_REVIEW.md`.
- API2Agent Tooling Re-entry Review + Tooling Expansion Plan v0 is complete:
  - the project is returning to the Tooling Layer with Control/Data Plane constraints.
  - current Tooling Layer goals are more real execution data, lower API/provider onboarding cost, and faster Agent API responses.
  - current implementation remains API-first and explicitly does not become a workflow engine.
  - Control Plane import/replace transaction design remains paused while tooling baseline audit runs.
  - see `docs/en-US/API2AGENT_TOOLING_REENTRY_REVIEW_AND_EXPANSION_PLAN.md`.
- API2Agent Tooling Baseline Audit v0 is complete:
  - the reproducible audit script is available at `scripts/api2agent_tooling_baseline_audit.py`.
  - curl generation and first direct call succeeded for ipify, Open-Meteo, GitHub repo read, and httpbin bearer.
  - no-auth proxy execution succeeded for ipify, Open-Meteo, and GitHub repo read.
  - GitHub REST OpenAPI generated successfully but exposed a 1186-tool unfiltered package risk.
  - the next Tooling fix is narrowed to OpenAPI filtering and curl tool naming hardening.
  - see `docs/en-US/API2AGENT_TOOLING_BASELINE_AUDIT_REPORT.md`.
- API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0 is complete:
  - root-path curl tools now include capability intent.
  - non-root curl naming remains path-based for backward compatibility.
  - OpenAPI generation warns when oversized packages remain unbounded.
  - targeted tests and the baseline audit script passed after the change.
  - see `docs/en-US/API2AGENT_OPENAPI_FILTERING_CURL_NAMING_HARDENING_REPORT.md`.
- Generated Package Region Metadata v0 is complete:
  - `--provider-region` writes region metadata into generated `capability.json`.
  - generated README files include provider region guidance.
  - generated runners propagate provider-region intent to proxy payloads.
  - region metadata dogfood passed with API-first scope.
  - see `docs/en-US/API2AGENT_GENERATED_PACKAGE_REGION_METADATA_REPORT.md`.
- Proxy-mode Credential Dogfood Expansion v0 is complete:
  - `scripts/api2agent_proxy_credential_dogfood.py` runs a generated authenticated package through the local proxy.
  - local credential config injects provider auth at the proxy without generated-package secrets.
  - usage events preserve credential-safe attribution and provider-region metadata.
  - see `docs/en-US/API2AGENT_PROXY_CREDENTIAL_DOGFOOD_EXPANSION_REPORT.md`.
- Generated Package Latency Benchmark Helper v0 is complete:
  - `run_generated_package_latency_benchmark` provides reusable direct/proxy generated-package timing.
  - `api2agent benchmark-package` exposes p50/p95 latency for generated package tools.
  - local dogfood verified direct/proxy timing, proxy usage ids, and provider-region attribution.
  - see `docs/en-US/API2AGENT_GENERATED_PACKAGE_LATENCY_BENCHMARK_REPORT.md`.
- Endpoint-level Auth Inference v0 is complete:
  - OpenAPI mixed public/protected operations now generate endpoint-aware auth metadata.
  - generated runners only require auth for tools whose operation needs it.
  - proxy credential intent and local credential config selection are tool-specific for mixed-auth providers.
  - local dogfood verified public/no-auth, bearer, and API key endpoints through direct and proxy execution.
  - see `docs/en-US/API2AGENT_ENDPOINT_AUTH_INFERENCE_REPORT.md`.
- Base URL Override v0 is complete:
  - generated packages can override provider base URLs at runtime with `API2AGENT_BASE_URL`.
  - generated packages can override one tool with `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>`.
  - direct and proxy execution share the same URL resolution semantics.
  - local dogfood verified default, global override, tool-specific override, invalid override fail-fast, and proxy usage metadata.
  - see `docs/en-US/API2AGENT_BASE_URL_OVERRIDE_REPORT.md`.
- Manual Write Test Path v0 is complete:
  - generated packages now include a guarded `manual_write_test.py`.
  - default `api2agent test` remains read-only.
  - `api2agent test --allow-write` explicitly opts into write/delete testing.
  - local dogfood verified default no-write behavior, direct opt-in execution, proxy opt-in execution, and usage metadata preservation.
  - see `docs/en-US/API2AGENT_MANUAL_WRITE_TEST_PATH_REPORT.md`.
- Large Spec Performance v0 is complete:
  - OpenAPI filters are applied during parsing instead of only after full tool construction.
  - `api2agent inspect` prints large-package summaries and bounded tool lists.
  - `api2agent test --tool ... --params ...` supports targeted generated read-tool checks.
  - local dogfood verified a 1200-operation spec across unfiltered warning, bounded generation, inspect summary, and targeted execution.
  - see `docs/en-US/API2AGENT_LARGE_SPEC_PERFORMANCE_REPORT.md`.
- Better curl naming residual review v0 is complete:
  - generic leading curl host labels such as `api` and `www` no longer produce vague default capability names.
  - generated auth env names now inherit better capability intent, e.g. `GITHUB_API_TOKEN`.
  - explicit `--name` and non-root path-based tool naming remain stable.
  - local dogfood verified generic API subdomain, root-path inferred naming, explicit name override, and non-root path compatibility.
  - see `docs/en-US/API2AGENT_CURL_NAMING_RESIDUAL_REVIEW.md`.
- API2Agent Tooling Re-entry Closeout + Phase Review v0 is complete:
  - Tooling Re-entry is judged ready to pause.
  - acceptance criteria, validation, and remaining risks are documented.
  - next engineering scope returns to Control Plane import/replace transaction design unless product requirements are updated first.
  - see `docs/en-US/API2AGENT_TOOLING_REENTRY_CLOSEOUT_REVIEW.md`.
- API2Agent Stage Consolidation Before Import/Replace v0 is complete:
  - Tooling, Go Data Plane, and Go Control Plane persistent read/audit states are consolidated.
  - entry gates for import/replace design are documented.
  - invariant boundaries are reaffirmed before write-side design starts.
  - see `docs/en-US/API2AGENT_STAGE_CONSOLIDATION_BEFORE_IMPORT_REPLACE.md`.
- Go Control Plane Persistent Registry Import/Replace Transaction Design v0 is complete:
  - the first write-side operation is scoped to controlled full-registry import/replace.
  - `seed-postgres` remains a dogfood helper, not the production mutation path.
  - serializable transaction, advisory lock, idempotency, same-transaction audit, rollback, and snapshot boundary semantics are specified.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_TRANSACTION_DESIGN.md`.
- Go Control Plane Persistent Registry Import/Replace CLI Implementation v0 is complete:
  - `api2agent-controlplane import-replace-postgres` is implemented as a narrow local/admin write path.
  - `ReplacePersistentRegistry` covers serializable transaction, advisory lock, full mutable-table replacement, no-op detection, revision/audit writes, and rollback behavior.
  - unit tests cover no-op, replacement, lock conflict, audit failure rollback, and transaction options.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_CLI_IMPLEMENTATION_REPORT.md`.
- Go Control Plane Persistent Registry Import/Replace Live Postgres Dogfood v0 is complete:
  - live Postgres dogfood used podman.
  - schema apply, seed, changed-registry import/replace, same-registry no-op, and snapshot export passed.
  - persistent audit counts were asserted: `registry_revisions=2`, `admin_audit_events=2`, `providers=1`.
  - see `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_LIVE_POSTGRES_DOGFOOD_REPORT.md`.
- Go Control Plane Import/Replace Closeout + Mutation API Readiness Review v0 is complete:
  - local/admin CLI primitive is accepted as complete for the current write-side slice.
  - readiness decision is design-only for a private admin endpoint.
  - public CRUD and endpoint implementation remain deferred.
  - see `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_CLOSEOUT_MUTATION_API_READINESS_REVIEW.md`.
- Go Control Plane Private Admin Import/Replace Endpoint Design v0 is complete:
  - `POST /v1/admin/registry/import-replace` is the accepted private admin endpoint.
  - the endpoint requires `Authorization`, `X-Request-ID`, and `Idempotency-Key`.
  - the request body uses a wrapper object with `registry`, optional `source`, and reserved `dry_run=false`.
  - FileStore remains unchanged; only Postgres mutation mode can run import/replace.
  - response shape, request-size limit, error mapping, audit mapping, and implementation tests are documented.
  - see `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`.
- Go Control Plane Private Admin Import/Replace Endpoint Implementation v0 is complete:
  - `POST /v1/admin/registry/import-replace` is implemented behind the existing admin auth boundary.
  - Postgres runtime wiring injects a narrow registry import replacer.
  - FileStore/unconfigured mutation returns `REGISTRY_MUTATION_UNAVAILABLE`.
  - changed registry returns `201`; same-fingerprint no-op returns `200`.
  - required request headers, 2 MiB request-size limit, error mapping, and option propagation are covered by tests.
  - see `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_IMPLEMENTATION_REPORT.md`.
- Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0 is complete:
  - live service dogfood used podman-backed Postgres.
  - HTTP import/replace returned `201` with `noop=false`.
  - repeated import returned `200` with `noop=true`.
  - service validation/export saw the replaced registry and `httpbin_public_ip_v1` provider.
  - persistent audit counts were asserted: `registry_revisions=3`, `admin_audit_events=4`, `providers=1`.
  - see `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_LIVE_POSTGRES_DOGFOOD_REPORT.md`.
- Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0 is complete:
  - design, implementation, and live dogfood are accepted as complete.
  - the private admin write-side endpoint milestone can close.
  - remaining risks are documented.
  - the next safe proof is snapshot propagation from import/replace to Data Plane execution.
  - see `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_CLOSEOUT_PHASE_REVIEW.md`.
- Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0 is complete:
  - HTTP import/replace changed the persistent registry provider to `httpbin_public_ip_v1`.
  - Control Plane exported and published the replacement snapshot.
  - Data Plane manual reload moved from `snapshot_propagation_ipify_v1` to `snapshot_propagation_httpbin_v2`.
  - Data Plane execution returned replacement-provider output `{ "ip": "203.0.113.88" }`.
  - usage and decision records attributed the replacement provider and snapshot version.
  - persistent audit counts were asserted.
  - see `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`.
- Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0 is complete:
  - the manual propagation milestone can close.
  - the architecture rule remains intact: Data Plane consumes immutable/versioned snapshots, not mutable Control Plane tables.
  - remaining hosted-readiness risks are documented.
  - the next task is narrowed to admin mutation idempotency store design.
  - see `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`.
- Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0 is complete:
  - hosted/trusted-gateway service mode starts without `--admin-token`.
  - trusted gateway success, missing gateway auth, and missing permission were verified over real HTTP.
  - Postgres audit and idempotency records preserve trusted principal evidence.
  - dogfood fixed import/replace audit metadata to include hosted principal evidence.
  - see `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`.

Next engineering task:

```text
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Closeout + Phase Review v0
```

References:

- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_LIVE_POSTGRES_DOGFOOD_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_IMPLEMENTATION_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`

## 9. Marketplace Is Later

Do not build a marketplace UI before:

- proxy works
- credential orchestration exists
- metrics exist
- capability abstraction exists
- routing works
- pricing metadata exists

Marketplace should be the result of routing plus economics, not the starting point.
