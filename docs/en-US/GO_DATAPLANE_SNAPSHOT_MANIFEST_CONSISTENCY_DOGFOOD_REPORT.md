# Go Data Plane Snapshot Manifest Consistency Dogfood Report

Date: 2026-05-31

## Goal

Prevent a distributed snapshot artifact from carrying inconsistent metadata across:

- `snapshot.json`
- `manifest.json`
- `current.json`

This protects both publish-time artifact integrity and reload-time distribution integrity.

## Implemented

Control Plane now validates artifact consistency before writing or publishing an artifact:

- `manifest.snapshot_version` must match `snapshot.snapshot_version`
- `manifest.snapshot_source` must match `snapshot.snapshot_source`
- `manifest.registry_fingerprint` must match `snapshot.metadata.registry_fingerprint`
- `manifest.snapshot_version_policy` must match `snapshot.metadata.snapshot_version_policy`

Data Plane now validates distribution consistency before loading a snapshot from `current.json`:

- `current.json` must agree with `manifest.json`
- `manifest.json` must point to the same snapshot file as `current.json`
- `manifest.json` must agree with `snapshot.json` metadata

## Verified Flow

The cross-plane dogfood now verifies:

1. v1 distribution loads.
2. v2 distribution reload succeeds.
3. incompatible v3 schema reload is rejected and keeps v2.
4. v4 is published, then its distributed `snapshot.json` is tampered.
5. Data Plane reload rejects v4 due manifest/snapshot fingerprint mismatch and keeps v2.
6. v5 artifact has a tampered `manifest.json` before publish.
7. Control Plane rejects v5 publish before advancing `current.json`.

## Checks

```json
{
  "manifest_consistency_reload_rejected": true,
  "manifest_consistency_reload_kept_v2": true,
  "manifest_consistency_reload_audit_event_recorded": true,
  "health_after_manifest_consistency_reload_still_v2": true,
  "manifest_mismatch_publish_rejected": true,
  "manifest_mismatch_publish_did_not_advance_current": true
}
```

## Result

Snapshot Metadata Manifest Consistency Guard v0 passed.

The local distribution path now rejects metadata drift at both Control Plane publish time and Data Plane reload time.
