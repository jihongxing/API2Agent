# Go Data Plane Snapshot Path Safety Dogfood Report

Date: 2026-05-31

## Goal

Prevent artifact and distribution metadata from escaping their intended directories through unsafe file references.

This protects:

- `manifest.snapshot_file`
- `current.snapshot_file`
- `current.manifest_file`

## Implemented

Control Plane now rejects unsafe artifact references before writing or publishing artifacts:

- absolute paths are rejected
- `..` traversal is rejected
- references must stay inside the artifact directory

Data Plane now applies the same rule when resolving distributed snapshots:

- `current.json` references must stay inside the distribution directory
- `manifest.json` snapshot references must stay inside the artifact directory

Direct `API2AGENT_SNAPSHOT=<snapshot.json>` paths are unchanged. The guard applies to references inside distribution metadata.

## Verified Flow

The cross-plane dogfood now verifies:

1. v8 artifact has `manifest.snapshot_file="../snapshot.json"`.
2. Control Plane rejects v8 publish before advancing `current.json`.
3. v9 is published normally.
4. distribution `current.json` is then modified to use `snapshot_file="../outside.json"`.
5. Data Plane reload rejects the unsafe pointer path and keeps v2 active.

## Checks

```json
{
  "unsafe_manifest_path_publish_rejected": true,
  "unsafe_manifest_path_publish_did_not_advance_current": true,
  "unsafe_pointer_path_reload_rejected": true,
  "unsafe_pointer_path_reload_kept_v2": true,
  "unsafe_pointer_path_reload_audit_event_recorded": true,
  "health_after_unsafe_pointer_path_reload_still_v2": true
}
```

## Result

Snapshot Artifact Path Safety Guard v0 passed.

Snapshot distribution now rejects path traversal before reading or publishing referenced files.
