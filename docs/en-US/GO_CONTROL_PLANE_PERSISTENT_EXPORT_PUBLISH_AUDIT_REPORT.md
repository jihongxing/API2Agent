# Go Control Plane Persistent Export/Publish Audit Writes Report

Date: 2026-05-31

Status: complete

## Summary

`Go Control Plane Persistent Export/Publish Audit Writes v0` adds persistent write-side audit records for the local Control Plane service when the registry store is explicitly configured as Postgres.

File-store mode remains unchanged. Registry mutation APIs, hosted auth, vault, billing, and marketplace work remain out of scope.

## Implemented

- Added a `PersistentAuditSink` boundary.
- Added a Postgres audit sink for:
  - `registry_revisions`
  - `snapshot_artifact_publications`
  - `admin_audit_events`
- Wired the audit sink into the Postgres runtime path only.
- Recorded admin audit events for:
  - registry validation
  - artifact export
  - distribution publish
  - current pointer reads
- Recorded registry revision rows after successful artifact export.
- Recorded artifact publication rows after successful distribution publish.
- Added fail-closed behavior for successful operations when persistent audit writes fail.
- Kept failure-path audit best-effort so original caller-facing errors are preserved.
- Hardened the live Postgres dogfood script with a built temporary Control Plane binary and dynamic service port.

## Verified

Unit tests cover:

- registry validation audit event writes
- artifact export audit writes
- distribution publish audit writes
- current pointer read audit writes
- `AUDIT_WRITE_FAILED` fail-closed behavior after successful export work

Live Postgres dogfood passed with podman:

```json
{
  "admin_audit_events": 4,
  "registry_revisions": 2,
  "snapshot_artifact_publications": 1
}
```

The live dogfood flow covered:

- schema apply
- seed import
- file/Postgres snapshot parity
- CLI artifact export
- service health
- service registry validation
- service artifact export
- service distribution publish
- service current pointer read
- direct audit table count assertions through podman `psql`

Dogfood output:

```text
.dogfood/go-control-plane-live-postgres/report.json
```

## Non-Goals

- No registry mutation API was added.
- No hosted persistence deployment was added.
- No credential vault was added.
- No billing or settlement logic was added.
- No marketplace feature was added.

## Next Recommended Task

```text
Go Control Plane Persistent Store Failure Semantics Hardening v0
```

Reason: persistent audit writes now introduce explicit fail-closed behavior. Before adding mutation APIs or broader hosted persistence, the project should define and test persistent-store failure semantics across read, export, publish, audit, and dogfood paths.
