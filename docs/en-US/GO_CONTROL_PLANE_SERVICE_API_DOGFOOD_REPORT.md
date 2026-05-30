# Go Control Plane Service API Dogfood Report

Date: 2026-05-31

## Goal

Prove the first local Control Plane service boundary without changing snapshot protocol semantics.

This dogfood validates the HTTP wrapper around existing registry validation, artifact export, and distribution status code paths.

## Implemented

The Go Control Plane now supports:

- `serve` command for a local HTTP service
- public `GET /healthz`
- admin bearer token guard for non-health endpoints
- `POST /v1/admin/registry/validate`
- `POST /v1/admin/snapshots/export-artifact`
- `GET /v1/admin/distribution/current`

The service is intentionally local-first. It does not include hosted persistence, remote object storage, a vault, billing, or marketplace flows.

## Verified Flow

The dogfood script:

1. Builds the Go Control Plane binary.
2. Writes a local file registry.
3. Creates an initial artifact and local distribution through existing CLI commands.
4. Starts the Control Plane service with an admin token.
5. Calls `/healthz` without auth.
6. Verifies an unauthenticated admin call is rejected with `AUTH_ERROR`.
7. Validates the registry through HTTP.
8. Exports a snapshot artifact through HTTP.
9. Reads the current distribution pointer through HTTP.

## Checks

```json
{
  "health_is_public_and_ok": true,
  "unauthorized_admin_rejected": true,
  "registry_validation_passed": true,
  "artifact_export_created_manifest": true,
  "artifact_export_created_snapshot": true,
  "distribution_current_reported": true
}
```

## Result

Go Control Plane Service API Skeleton v0 passed.

The Control Plane is no longer CLI-only. It now has the first local service boundary while still reusing the proven registry, artifact, and distribution primitives.
