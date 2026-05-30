# Go Control Plane Service API Closeout

Date: 2026-05-31

Status: complete

Decision: the local Go Control Plane service API milestone is closed. API2Agent is ready to enter hosted persistence design, but not direct database implementation yet.

## 1. Milestone Scope

This milestone closes the first local Control Plane service boundary:

```text
file registry
  -> Control Plane service
  -> registry validation
  -> artifact export
  -> distribution publish
  -> current pointer read
```

The milestone did not attempt to build:

- registry mutation APIs
- Postgres persistence
- remote object storage
- distributed publish locks
- Control Plane admin audit log
- per-project hosted authorization
- credential vault
- billing
- marketplace

## 2. Completed Capabilities

The Go Control Plane service now supports:

- `api2agent-controlplane serve`
- public `GET /healthz`
- admin bearer token guard for `/v1/admin/*`
- `POST /v1/admin/registry/validate`
- `POST /v1/admin/snapshots/export-artifact`
- `POST /v1/admin/distribution/publish`
- `GET /v1/admin/distribution/current`
- HTTP artifact export through the existing registry exporter
- HTTP distribution publish through the existing atomic local publisher
- duplicate publish rejection before `current.json` is advanced
- service dogfood for HTTP validate -> export -> publish -> current

## 3. Evidence

Recent implementation commits:

```text
64085da Add control plane service publish endpoint
839ef8e Add control plane service API skeleton
f4b56ae Document snapshot distribution closeout
efa0dd1 Add snapshot distribution atomic publish guard
```

Dogfood evidence:

- `docs/en-US/GO_CONTROL_PLANE_SERVICE_API_DOGFOOD_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_SNAPSHOT_DISTRIBUTION_CLOSEOUT.md`
- `docs/en-US/GO_CONTROL_PLANE_SNAPSHOT_ATOMIC_PUBLISH_DOGFOOD_REPORT.md`

Current verification baseline:

```text
go test ./...
python -m pytest
python scripts/go_control_plane_service_api_dogfood.py --output .dogfood/go-control-plane-service-api/report.json
python scripts/go_control_plane_minimum_dogfood.py --output .dogfood/go-control-plane-minimum/report.json
```

## 4. Exit Criteria Review

| Criterion | Status | Notes |
|---|---|---|
| Control Plane can run as a local HTTP service | Passed | `serve` starts against the existing file registry. |
| Health endpoint is public | Passed | `/healthz` reports service, protocol, registry source, and distribution metadata. |
| Admin endpoints are guarded | Passed | Unauthenticated admin calls return `AUTH_ERROR`. |
| Registry validation works through HTTP | Passed | The service returns validation counts and registry fingerprint. |
| Artifact export works through HTTP | Passed | The service writes `snapshot.json` and `manifest.json` through existing exporter code. |
| Distribution publish works through HTTP | Passed | The service publishes artifacts through existing atomic publish code. |
| Duplicate publish is safe | Passed | Duplicate publish returns `DISTRIBUTION_ARTIFACT_EXISTS` and keeps `current.json` unchanged. |
| Distribution state is readable | Passed | The service returns the current distribution pointer. |
| Existing CLI and cross-plane dogfood remain stable | Passed | The original Control Plane minimum dogfood still passes. |

## 5. Hosted Persistence Readiness

Ready:

- The Control Plane has a real service boundary.
- Registry loading is already behind `registry.Store`.
- Snapshot export semantics are independent of the file store.
- Local artifact and distribution semantics are stable enough to preserve across storage backends.
- Admin endpoints have a first auth guard.

Not ready:

- No Postgres schema exists.
- No migration plan exists.
- No transaction model exists for registry reads, artifact exports, and publish records.
- No persisted Control Plane admin audit events exist.
- No registry mutation API exists.
- No per-project authorization model exists beyond the local admin token.
- No remote artifact storage or compare-and-swap publish protocol exists.
- No credential vault exists.

## 6. Readiness Decision

API2Agent should not jump directly into Postgres implementation.

The next stage should begin as:

```text
Go Control Plane Persistent Registry Store Design v0
```

This is a design task, not a database implementation task.

## 7. Recommended Next Entry Slice

Scope:

1. Define the persistent registry store contract.
2. Draft the first Postgres table model for projects, API keys, capabilities, providers, credential metadata, routing policy, snapshot metadata, artifact publications, and admin audit events.
3. Define transaction boundaries for registry load, artifact export, and distribution publish.
4. Define versioning and fingerprint rules for database-backed registry state.
5. Define migration and dual-store strategy from file registry to persistent registry.
6. Keep snapshot export output identical to the file-store path.

Exit criteria:

- Persistent store design is documented in English and Chinese.
- Database implementation scope is explicit before code starts.
- Snapshot export compatibility rules are preserved.
- No hosted deployment, vault, billing, or marketplace work is included.

## 8. Strategic Judgment

The project has crossed from local Control Plane CLI into a local Control Plane service.

The next important question is no longer:

```text
Can Control Plane operations be exposed through HTTP?
```

That has been proven.

The next question is:

```text
Can API2Agent persist Control Plane state without changing the Data Plane snapshot contract?
```

That is the right next stage.
