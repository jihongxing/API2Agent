# Go Data Plane Snapshot Refresh / Reload Dogfood Report

Date: 2026-05-30

## Goal

Verify the first reload policy for snapshots distributed by the Go Control Plane.

## Policy v0

Default behavior remains:

```text
startup_only
```

That means Data Plane loads `API2AGENT_SNAPSHOT` at startup and does not refresh automatically.

Local manual reload can be enabled with:

```text
API2AGENT_SNAPSHOT_RELOAD_POLICY=manual
```

When enabled, Data Plane exposes:

```http
POST /v1/admin/reload-snapshot
```

If `API2AGENT_PROJECT_KEY` is configured, this endpoint requires the same bearer token as `/v1/execute`.

## Verified Flow

The cross-plane dogfood now verifies:

1. Control Plane exports and publishes snapshot v1 into a local distribution directory.
2. Data Plane starts with `API2AGENT_SNAPSHOT=<distribution_dir>`.
3. `/healthz` reports `snapshot_control_plane_public_ip_v1`.
4. Control Plane exports and publishes snapshot v2 into the same distribution directory.
5. Data Plane receives `POST /v1/admin/reload-snapshot`.
6. `/healthz` reports `snapshot_control_plane_public_ip_v2`.
7. `/v1/execute` succeeds.
8. RoutingDecision and UsageEvent record `snapshot_control_plane_public_ip_v2`.

## Checks

```json
{
  "health_before_reload_snapshot_version_matches": true,
  "reload_response_success": true,
  "reload_previous_snapshot_version_matches": true,
  "reload_snapshot_version_matches": true,
  "distribution_current_after_reload_points_to_v2": true,
  "distribution_v2_artifact_snapshot_exists": true,
  "routing_snapshot_version_matches": true
}
```

## Result

Snapshot Refresh / Reload Policy v0 passed.

This keeps the production default conservative while giving local Control Plane / Data Plane dogfood a concrete reload mechanism.
