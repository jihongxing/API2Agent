# Go Control Plane Minimum Dogfood Report

Date: 2026-05-30

## Goal

Verify that the new minimum Go Control Plane can export a versioned routing snapshot that the existing Go Data Plane can consume without code changes in the Data Plane snapshot loader.

This report also verifies that invalid registry relationships are rejected before snapshot export.

## Setup

Control Plane registry:

- project model
- API key model
- capability registry model
- provider registry model
- credential metadata model
- routing policy
- snapshot export metadata

Data Plane:

- existing `api2agent-dataplane`
- same `/v1/execute` path
- same Protocol v0.2 execution graph

## Dogfood Command

```bash
python scripts/go_control_plane_minimum_dogfood.py \
  --output .dogfood/go-control-plane-minimum/report.json
```

The script builds:

- `api2agent-controlplane`
- `api2agent-dataplane`
- `api2agent-snapshot-check`

## Observed Result

The control plane exported a snapshot with:

- `snapshot_version = snapshot_control_plane_public_ip_v1`
- `snapshot_source = pull`
- `snapshot_version_policy = explicit`
- `registry_fingerprint = sha256:<hash>`
- one capability
- one active provider
- one credential metadata entry

The data plane then:

- accepted the exported snapshot through `api2agent-snapshot-check`
- loaded the exported snapshot
- reported the same snapshot version in `/healthz`
- executed `network.public_ip.get`
- returned the fixed public IP from the local provider
- wrote a valid execution graph

The control plane also rejected an invalid registry where an API key referenced a missing project:

```text
api_key "key_local_dev" references unknown project "missing_project"
```

## Result

Go Control Plane Minimum v0 passed.

This proves the first Phase 6 boundary:

```text
Control Plane registry -> versioned snapshot export -> Data Plane consumption
```

## Checks

```json
{
  "control_plane_export_success": true,
  "snapshot_check_passed": true,
  "snapshot_check_has_registry_fingerprint": true,
  "snapshot_check_has_explicit_version_policy": true,
  "invalid_registry_rejected": true,
  "health_snapshot_version_matches": true,
  "response_success": true,
  "response_ip_matches_provider": true,
  "usage_has_attempt_id": true,
  "routing_snapshot_version_matches": true,
  "event_order_is_graph": true
}
```

## Non-Goals

This slice does not add:

- hosted database
- hosted credential vault
- billing
- marketplace
- multi-region hosted proxy
- dashboard
