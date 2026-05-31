# Go Control Plane Persistent Registry Store Schema v0 Report

Date: 2026-05-31

Status: complete

## Summary

This slice turns the persistent registry store design into a testable schema/load-parity contract.

It does not switch the Control Plane runtime to Postgres. `registry.FileStore` remains the default runtime store.

## Implemented

- Added a Postgres schema draft at `services/control-plane/schema/postgres/001_persistent_registry_store.sql`.
- Covered the first persistent registry tables:
  - `projects`
  - `api_keys`
  - `capabilities`
  - `providers`
  - `credential_metadata`
  - `routing_policies`
  - `snapshot_configs`
  - `registry_revisions`
  - `snapshot_artifact_publications`
  - `admin_audit_events`
- Added table-level constraints for the v0 control-plane model:
  - active providers must include `metadata.base_url`
  - routing policies allow one active global policy
  - snapshot configs allow one active config
  - snapshot artifact publications reject duplicate active snapshot versions
  - API keys include `key_hash` for future hosted verification while raw keys remain out of scope
- Added `MapRegistryToPersistentRows` to map the current in-memory `registry.Registry` into persistent row-shaped structs.
- Added `CanonicalRegistry` to sort registry collections deterministically before persistent mapping and fingerprint calculation.

## Verified

- The SQL schema test checks the required tables and critical constraints.
- The existing `network.public_ip.get` file registry fixture maps into persistent row structs.
- The mapping preserves provider `base_url` metadata.
- File registry import does not invent API key hashes or raw secret fields.
- Persistent mapping creates registry revision metadata but does not invent artifact publication or admin audit rows.
- Canonical registry ordering sorts projects, API keys, capabilities, providers, provider regions, credential metadata, and credential scopes without mutating the input registry.

## Non-Goals

This slice does not implement:

- live Postgres connectivity
- `PostgresStore.Load(ctx)`
- hosted deployment
- registry mutation APIs
- credential vault
- billing
- marketplace features

## Validation

```text
go test ./...
```

from `services/control-plane` passed.

## Next Recommended Step

This schema report is followed by `docs/en-US/GO_CONTROL_PLANE_PERSISTENCE_PHASE_REVIEW.md`.

The phase review narrows the next implementation slice to:

```text
Go Control Plane PostgresStore Load Parity v0
```
