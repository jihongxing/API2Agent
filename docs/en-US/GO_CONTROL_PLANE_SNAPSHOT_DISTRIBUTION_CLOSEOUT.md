# Go Control Plane Snapshot Distribution Closeout

Date: 2026-05-31

Status: complete

Decision: the local Go Control Plane snapshot distribution milestone is closed. API2Agent is ready to move from CLI-only Control Plane operations into a local Control Plane service boundary.

## 1. Milestone Scope

This milestone closes the local snapshot distribution chain:

```text
registry.json
  -> routing snapshot
  -> snapshot artifact
  -> local distribution/current.json
  -> Go Data Plane startup or manual reload
```

The milestone did not attempt to build:

- hosted SaaS
- remote object storage distribution
- distributed locking or multi-writer publish
- Postgres-backed registry persistence
- KMS-backed credential vault
- billing or marketplace flows
- public provider onboarding

## 2. Completed Capabilities

The Go Control Plane and Go Data Plane now support:

- local Control Plane registry models for projects, API keys, capabilities, providers, credential metadata, routing policy, and snapshot metadata
- `registry.Store` as the Control Plane state source boundary
- local file-backed registry loading
- registry validation before export
- Data Plane-compatible routing snapshot export
- snapshot compatibility checking through the Go Data Plane checker
- explicit snapshot version policy and deterministic registry fingerprints
- snapshot artifact export with `snapshot.json` and `manifest.json`
- artifact manifest validation before write and publish
- local snapshot distribution with `current.json` plus versioned artifact directories
- Data Plane loading from a bare snapshot file, distribution directory, or direct `current.json` path
- manual Data Plane snapshot reload policy
- reload failure semantics that keep the previous serving snapshot active
- reload audit events in the durable event stream
- schema version compatibility checks
- strict Control Plane metadata requirements
- manifest, pointer, snapshot metadata, and content digest consistency checks
- path safety checks for artifact and distribution metadata
- local atomic publish behavior through temporary artifact directories and temporary `current.json` writes
- duplicate `snapshot_version` rejection before advancing `current.json`

## 3. Evidence

Recent implementation commits:

```text
efa0dd1 Add snapshot distribution atomic publish guard
f317e55 Add snapshot artifact path safety guard
9e8c586 Add snapshot artifact content digest guard
01553f1 Add snapshot manifest consistency guard
52fed35 Add snapshot strict metadata requirement
0245963 Add snapshot version compatibility guard
cc9cb82 Add snapshot reload audit events
a6ccf79 Add snapshot reload failure semantics
191618e Add data plane snapshot reload policy
6a88b1e Add control plane snapshot distribution stub
90e02c3 Add control plane snapshot export artifact
5114862 Add control plane snapshot versioning metadata
6ae8df9 Add control plane registry store
78ca3f6 Add control plane snapshot compatibility gate
e19af2b Harden control plane registry validation
e287ac5 Implement Go control plane minimum
```

Dogfood evidence:

- `docs/en-US/GO_CONTROL_PLANE_MINIMUM_DOGFOOD_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_SNAPSHOT_DISTRIBUTION_DOGFOOD_REPORT.md`
- `docs/en-US/GO_DATAPLANE_SNAPSHOT_RELOAD_DOGFOOD_REPORT.md`
- `docs/en-US/GO_DATAPLANE_SNAPSHOT_RELOAD_AUDIT_DOGFOOD_REPORT.md`
- `docs/en-US/GO_DATAPLANE_SNAPSHOT_COMPATIBILITY_GUARD_DOGFOOD_REPORT.md`
- `docs/en-US/GO_DATAPLANE_SNAPSHOT_STRICT_METADATA_DOGFOOD_REPORT.md`
- `docs/en-US/GO_DATAPLANE_SNAPSHOT_MANIFEST_CONSISTENCY_DOGFOOD_REPORT.md`
- `docs/en-US/GO_DATAPLANE_SNAPSHOT_CONTENT_DIGEST_DOGFOOD_REPORT.md`
- `docs/en-US/GO_DATAPLANE_SNAPSHOT_PATH_SAFETY_DOGFOOD_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_SNAPSHOT_ATOMIC_PUBLISH_DOGFOOD_REPORT.md`

Current verification baseline:

```text
go test ./...
python -m pytest
python scripts/go_control_plane_minimum_dogfood.py --output .dogfood/go-control-plane-minimum/report.json
```

## 4. Exit Criteria Review

| Criterion | Status | Notes |
|---|---|---|
| Control Plane can produce a Data Plane-compatible snapshot | Passed | `export-snapshot` output is accepted by `api2agent-snapshot-check` and the Go Data Plane. |
| Snapshot artifacts are explicit and auditable | Passed | Artifacts contain `snapshot.json`, `manifest.json`, registry fingerprint, version policy, and content digest. |
| Local distribution can expose the current snapshot | Passed | `current.json` points to a versioned artifact directory. |
| Data Plane can consume distributed snapshots | Passed | Startup, snapshot check, and manual reload use the same resolver. |
| Failed reloads keep the active snapshot stable | Passed | Broken or incompatible distributed snapshots do not replace the serving snapshot. |
| Reload attempts are auditable | Passed | Failed and successful reloads write `snapshot_reload_event` records. |
| Snapshot metadata is production-auditable | Passed | Schema version, registry fingerprint, version policy, manifest consistency, and digest are validated. |
| Distribution metadata is path-safe | Passed | Absolute paths and `..` traversal are rejected before file reads. |
| Local publish avoids half-published state | Passed | Artifacts are copied through temp dirs, duplicate versions are rejected, and `current.json` is updated through a temp file. |

## 5. Remaining Gaps

These gaps are expected and should move into the next Control Plane stages.

- local filesystem distribution only
- no remote object storage publish protocol
- no compare-and-swap or distributed lock for concurrent publishers
- `current.json` replacement is best-effort local atomic behavior, not a cross-filesystem transaction
- no signed artifacts or provenance chain
- no Postgres-backed registry store
- no Control Plane HTTP service API
- no hosted API key enforcement for Control Plane operations
- no KMS-backed credential vault
- no hosted analytics API
- no billing
- no marketplace

## 6. Readiness Decision

API2Agent should stop adding more local snapshot distribution guards by default.

The local distribution chain is now strong enough for the current architecture phase:

```text
Control Plane registry -> artifact -> distribution -> Data Plane reload
```

The next stage should begin as:

```text
Go Control Plane Service API Skeleton v0
```

Readiness is conditional:

- ready to create a local Control Plane service boundary
- ready to wrap existing registry validation, artifact export, and distribution status behind an HTTP process
- not ready for hosted public alpha
- not ready for remote object storage distribution
- not ready for billing or marketplace

## 7. Recommended Next Entry Slice

The next implementation slice should be:

```text
Go Control Plane Service API Skeleton v0
```

Scope:

1. Local Control Plane HTTP process.
2. `GET /healthz` with service, protocol, and registry source metadata.
3. Read-only registry validation endpoint.
4. Snapshot artifact export endpoint backed by the existing exporter.
5. Distribution status endpoint that reads `current.json` without exposing secrets.
6. Admin bearer token guard for non-health endpoints.

Exit criteria:

- The service can start against the existing local file registry.
- The service can validate the registry through HTTP.
- The service can export an artifact through HTTP using existing registry/exporter code.
- The service can report the current local distribution pointer through HTTP.
- Existing CLI commands and dogfood continue to pass.
- No hosted database, vault, billing, or marketplace work is included.

## 8. Strategic Judgment

The project has crossed from a local Data Plane primitive into a local Control Plane distribution primitive.

The next important question is no longer:

```text
Can the Control Plane produce a snapshot for the Data Plane?
```

That has been proven.

The next question is:

```text
Can API2Agent expose Control Plane operations as a stable service boundary without changing the protocol semantics?
```

That is the correct next stage.
