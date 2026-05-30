# Go Data Plane Snapshot Version Compatibility Guard Dogfood Report

Date: 2026-05-31

## Goal

Prevent Data Plane from loading or reloading snapshots that declare an incompatible protocol schema version.

## Implemented

Control Plane exported snapshots now include:

```json
{
  "metadata": {
    "schema_version": "api2agent.protocol.v0.2"
  }
}
```

Data Plane snapshot loading checks:

- if `metadata.schema_version` is absent, legacy local snapshots are still accepted
- if `metadata.schema_version` is present, it must equal `api2agent.protocol.v0.2`
- incompatible snapshots are rejected during startup load, snapshot check, and manual reload

## Verified Flow

The cross-plane dogfood now verifies:

1. v1 distribution loads.
2. broken `current.json` reload fails and keeps v1.
3. v2 distribution reload succeeds.
4. v3 distribution is modified to declare `api2agent.protocol.v9`.
5. reload rejects v3 as incompatible.
6. `/healthz` remains on v2.
7. execution succeeds and records v2 in RoutingDecision and UsageEvent.

## Checks

```json
{
  "snapshot_check_schema_version_matches": true,
  "incompatible_reload_rejected": true,
  "incompatible_reload_kept_v2": true,
  "incompatible_reload_audit_event_recorded": true,
  "health_after_incompatible_reload_still_v2": true,
  "routing_snapshot_version_matches": true
}
```

## Result

Snapshot Version Compatibility Guard v0 passed.

This prevents a distributed snapshot from silently crossing a protocol boundary the Data Plane does not understand.
