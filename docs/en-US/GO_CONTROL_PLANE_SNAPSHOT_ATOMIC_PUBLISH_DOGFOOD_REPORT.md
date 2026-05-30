# Go Control Plane Snapshot Atomic Publish Dogfood Report

Date: 2026-05-31

## Goal

Avoid half-published distribution state when publishing a snapshot artifact fails.

This is a local distribution guard. It does not yet implement remote object storage transactions or distributed locking.

## Implemented

Control Plane publish now:

- validates the source artifact before writing distribution state
- rejects duplicate `snapshot_version` artifact directories
- copies `snapshot.json` and `manifest.json` into a temporary artifact directory first
- commits the artifact directory only after both files are copied
- writes `current.json` through a temporary file before replacement
- cleans up temporary artifact directories on failure

## Verified Flow

The cross-plane dogfood now verifies:

1. v10 artifact publishes successfully.
2. distribution `current.json` advances to v10.
3. publishing the same v10 artifact again is rejected because the target artifact already exists.
4. `current.json` remains on v10 after the rejected duplicate publish.
5. no temporary v10 artifact directory remains after rejection.

## Checks

```json
{
  "atomic_publish_advanced_current_to_v10": true,
  "duplicate_atomic_publish_rejected": true,
  "duplicate_atomic_publish_kept_current_v10": true,
  "duplicate_atomic_publish_left_no_temp_artifacts": true
}
```

## Result

Snapshot Distribution Atomic Publish Guard v0 passed.

The local publisher no longer writes artifact files directly into the final directory before the artifact is complete.
