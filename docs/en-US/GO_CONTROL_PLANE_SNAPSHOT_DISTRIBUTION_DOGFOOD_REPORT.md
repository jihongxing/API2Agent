# Go Control Plane Snapshot Distribution Dogfood Report

Date: 2026-05-30

## Goal

Verify the first local snapshot distribution boundary:

```text
Control Plane artifact -> local distribution current pointer -> Data Plane snapshot load
```

## Scope

This is a local stub only. It does not add hosted distribution, remote pull, push delivery, object storage, signing, or multi-region propagation.

## Implemented

- `api2agent-controlplane publish-artifact`
- local distribution layout:
  - `current.json`
  - `artifacts/<snapshot_version>/snapshot.json`
  - `artifacts/<snapshot_version>/manifest.json`
- Data Plane snapshot resolver support for:
  - bare snapshot file path
  - distribution directory containing `current.json`
  - direct `current.json` path

## Verified

The dogfood script now:

- exports a snapshot artifact
- publishes the artifact into a local distribution directory
- runs `api2agent-snapshot-check` against the distribution directory
- starts Go Data Plane with `API2AGENT_SNAPSHOT=<distribution_dir>`
- verifies `/v1/execute` succeeds with the distributed snapshot

## Checks

```json
{
  "distribution_current_exists": true,
  "distribution_current_points_to_snapshot": true,
  "distribution_current_fingerprint_matches_manifest": true,
  "distribution_artifact_snapshot_exists": true,
  "snapshot_check_passed": true,
  "health_snapshot_version_matches": true,
  "response_success": true
}
```

## Result

Control Plane Snapshot Distribution Stub v0 passed.

The project now has a local distribution contract between Control Plane artifact publishing and Data Plane snapshot consumption.
