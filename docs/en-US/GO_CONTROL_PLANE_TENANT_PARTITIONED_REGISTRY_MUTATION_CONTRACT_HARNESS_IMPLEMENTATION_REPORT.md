# Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

The Control Plane registry package now has a local contract helper for tenant-partitioned mutation validation.

This does not expose a new HTTP endpoint and does not change production import/replace behavior. It proves the partition diff rules that a later hosted project mutation endpoint must satisfy before it can replace registry rows.

## Implemented

- Added `ValidateProjectPartitionMutation(current, proposed, projectID)`.
- Added `ProjectPartitionMutationDecision` evidence with:
  - `partition_project_id`
  - `operation=registry.project_partition_replace`
  - changed object counts
  - rejected object counts
  - stable violation records
  - proposed/previous registry fingerprints
  - partition diff fingerprint
  - snapshot-boundary-change marker
- Added stable partition violation error behavior:
  - `REGISTRY_PARTITION_VIOLATION`
  - `scope=caller`
  - `retryable=false`
- Kept existing full-registry validation before partition decisions.
- Kept missing project scope fail-closed with `AUTHZ_DENIED`.
- Treated provider rows without `metadata.owner_project_id` as platform-owned.
- Allowed project-owned provider changes only when ownership metadata matches the principal project.
- Rejected provider ownership transfer.
- Rejected global capability, routing policy, and snapshot config changes.
- Added idempotency fingerprint coverage for project-isolated partition requests.

## Contract Tests

Covered:

- same-project project row update passes
- same-project API key metadata update passes
- same-project credential metadata update passes
- caller-owned provider metadata update passes
- other project row change fails
- other project API key deletion fails
- other project credential metadata change fails
- platform credential metadata change fails
- global capability change fails
- global routing policy change fails
- active snapshot config change fails
- platform-owned provider change fails
- provider ownership transfer fails
- new provider without ownership fails
- invalid proposed registry fails before partition mutation
- missing project scope fails with `AUTHZ_DENIED`
- same raw idempotency key is isolated by project scope

## Validation

Passed:

```text
go test ./internal/registry
```

Go test directory:

```text
services/control-plane
```

## Non-Goals Preserved

No public CRUD, public project/user/role CRUD, OAuth/OIDC integration, invitation/login/session lifecycle, production gateway deployment, durable hosted permission store, provider onboarding workflow, marketplace, vault, billing, workflow runtime, automatic snapshot export/publish/reload, or Data Plane mutable table reads were added.

## Next Recommended Task

```text
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness Closeout + Phase Review v0
```
