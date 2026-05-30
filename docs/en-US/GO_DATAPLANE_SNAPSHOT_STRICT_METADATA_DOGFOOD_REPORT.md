# Go Data Plane Snapshot Strict Metadata Dogfood Report

Date: 2026-05-31

## Goal

Require Control Plane exported snapshots to carry the metadata needed for audit, replay, and distribution safety.

Legacy local snapshots without Control Plane metadata remain accepted for now.

## Implemented

Data Plane snapshot compatibility now treats a snapshot as Control Plane/exported when metadata contains any of:

- `exporter`
- `registry_fingerprint`
- `snapshot_version_policy`

When that condition is true, the snapshot must include:

```json
{
  "metadata": {
    "schema_version": "api2agent.protocol.v0.2",
    "registry_fingerprint": "sha256:...",
    "snapshot_version_policy": "explicit"
  }
}
```

Missing required metadata fails startup load, `api2agent-snapshot-check`, and manual reload because all paths use the same snapshot loader.

## Verified Flow

The cross-plane dogfood now verifies:

1. v1 distribution loads.
2. broken `current.json` reload fails and keeps v1.
3. v2 distribution reload succeeds.
4. v3 distribution with incompatible `schema_version` is rejected and keeps v2.
5. v4 distribution with missing `registry_fingerprint` is rejected and keeps v2.
6. strict metadata reload failure writes a `snapshot_reload_event`.
7. execution still succeeds on v2 and records v2 in the routing decision.

## Checks

```json
{
  "strict_metadata_reload_rejected": true,
  "strict_metadata_reload_kept_v2": true,
  "strict_metadata_reload_audit_event_recorded": true,
  "health_after_strict_metadata_reload_still_v2": true,
  "snapshot_check_has_registry_fingerprint": true,
  "snapshot_check_has_explicit_version_policy": true,
  "snapshot_check_schema_version_matches": true
}
```

## Result

Snapshot Strict Metadata Requirement v0 passed.

Control Plane snapshots now need enough metadata to explain where they came from, which protocol contract they target, and which registry state they represent.
