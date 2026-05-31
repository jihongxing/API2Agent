# Go Control Plane Persistent Store Failure Semantics Hardening Report

Date: 2026-05-31

Status: complete

## Summary

`Go Control Plane Persistent Store Failure Semantics Hardening v0` makes the local Control Plane service distinguish persistent-store platform failures from file-registry validation failures.

The default file-store path remains unchanged. Registry mutation APIs, hosted auth, vault, billing, and marketplace work remain out of scope.

## Implemented

- Added stable persistent registry load failure semantics for Postgres-backed service operations.
- `registry-store=postgres` load failures now return:
  - HTTP status: `503`
  - `error_type`: `PERSISTENT_STORE_READ_FAILED`
  - `error_scope`: `platform`
  - `retryable`: `true`
- File-store load failures remain:
  - HTTP status: `400`
  - `error_type`: `REGISTRY_INVALID`
  - `error_scope`: `caller`
  - `retryable`: `false`
- Success-path persistent audit write failures remain fail-closed with:
  - HTTP status: `500`
  - `error_type`: `AUDIT_WRITE_FAILED`
  - `error_scope`: `platform`
  - `retryable`: `true`
- Failure-path admin audit writes remain best-effort so original caller-facing errors are preserved.

## Verified

Regression tests cover:

- Postgres-backed registry validation read failures.
- Postgres-backed artifact export read failures.
- File-store read failures remain `REGISTRY_INVALID`.
- Registry validation fails closed when required audit writes fail.
- Artifact export fails closed when required audit writes fail.
- Distribution publish fails closed when required audit writes fail.
- Current pointer read fails closed when required audit writes fail.

Validation commands:

```text
services/control-plane: go test ./...
services/data-plane: go test ./...
repo root: python -m pytest
live Postgres dogfood: passed
```

Live Postgres dogfood still verifies persistent audit rows:

```json
{
  "admin_audit_events": 4,
  "registry_revisions": 2,
  "snapshot_artifact_publications": 1
}
```

## Non-Goals

- No registry mutation API was added.
- No transaction bundling was added across filesystem publish and audit writes.
- No hosted persistence deployment was added.
- No credential vault was added.
- No billing or settlement logic was added.
- No marketplace feature was added.

## Next Recommended Task

```text
Go Control Plane Persistent Registry Mutation Boundary Review v0
```

Reason: persistent read-side loading, runtime wiring, audit writes, and failure semantics are now hardened enough to review the mutation boundary before adding any write APIs.
