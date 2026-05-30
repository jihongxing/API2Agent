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
4. Dogfood points `current.json` at a missing snapshot and calls `POST /v1/admin/reload-snapshot`.
5. The failed reload returns `SNAPSHOT_RELOAD_FAILED`, `reloaded=false`, and `kept_snapshot_version=snapshot_control_plane_public_ip_v1`.
6. A failed `snapshot_reload_event` is written.
7. `/healthz` still reports `snapshot_control_plane_public_ip_v1`.
8. Control Plane exports and publishes snapshot v2 into the same distribution directory.
9. Data Plane receives `POST /v1/admin/reload-snapshot`.
10. A successful `snapshot_reload_event` is written before the active snapshot is swapped.
11. An incompatible v3 snapshot declares `api2agent.protocol.v9` and is rejected.
12. `/healthz` remains on `snapshot_control_plane_public_ip_v2`.
13. `/v1/execute` succeeds.
14. RoutingDecision and UsageEvent record `snapshot_control_plane_public_ip_v2`.

## Checks

```json
{
  "health_before_reload_snapshot_version_matches": true,
  "failed_reload_rejected": true,
  "failed_reload_kept_previous_snapshot": true,
  "health_after_failed_reload_still_v1": true,
  "failed_reload_audit_event_recorded": true,
  "reload_response_success": true,
  "reload_previous_snapshot_version_matches": true,
  "reload_snapshot_version_matches": true,
  "successful_reload_audit_event_recorded": true,
  "incompatible_reload_rejected": true,
  "incompatible_reload_kept_v2": true,
  "incompatible_reload_audit_event_recorded": true,
  "health_after_incompatible_reload_still_v2": true,
  "distribution_current_after_reload_points_to_v2": true,
  "distribution_v2_artifact_snapshot_exists": true,
  "routing_snapshot_version_matches": true
}
```

## Result

Snapshot Refresh / Reload Policy v0 passed.

This keeps the production default conservative while giving local Control Plane / Data Plane dogfood a concrete reload mechanism.

Reload Failure Semantics v0 also passed: failed reload does not swap the active snapshot, and the failure response is machine-readable and retryable.

Reload Audit Events v0 also passed: failed and successful reload attempts are written into the append-only event stream.

Snapshot Version Compatibility Guard v0 also passed: incompatible schema versions are rejected without replacing the active snapshot.
