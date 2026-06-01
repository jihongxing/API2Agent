# Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

Implemented the private hosted admin endpoint for project-scoped registry replacement:

```text
POST /v1/admin/registry/project-partition/replace
```

The endpoint requires a trusted-gateway, non-local, project-scoped principal with:

```text
control_plane.registry.project_partition_replace
```

It does not expose public CRUD and does not automatically export, publish, reload, or let the Data Plane read mutable Control Plane tables.

## What Changed

- Added `PermissionRegistryProjectPartitionReplace`.
- Added `RegistryProjectPartitionReplacer` to the HTTP service.
- Registered `POST /v1/admin/registry/project-partition/replace`.
- Added request handling with:
  - `X-Request-ID` requirement
  - `Idempotency-Key` requirement
  - 2 MiB body cap
  - wrapper body parsing
  - `dry_run=true` rejection
  - unknown identity/project override field rejection through strict JSON decoding
- Added trusted hosted principal guard:
  - rejects local/private principals
  - requires `trusted_gateway`
  - requires project and actor scope
  - requires `control_plane.registry.project_partition_replace`
- Added response evidence:
  - `partition_project_id`
  - `partition_diff_fingerprint`
  - `partition_counts`
  - registry fingerprints and object counts
  - replay flag
- Mapped `REGISTRY_PARTITION_VIOLATION` to `403`.
- Wired the `serve` runtime to provide the project partition replacer when Postgres mutation mode is configured.
- Updated the local hosted gateway contract harness endpoint permission map.

## Registry-Layer Transaction Seam

Added:

```go
registry.ReplaceProjectPartitionRegistry(ctx, db, proposed, opts)
```

The registry layer owns the serializable write transaction:

1. validate/canonicalize proposed registry
2. begin serializable write transaction
3. acquire the registry mutation lock
4. load current persistent registry inside the transaction
5. call `ValidateProjectPartitionMutation(current, proposed, principal.ProjectID)`
6. reserve idempotency after partition validation
7. replace mutable rows only after validation passes
8. write registry revision, admin audit, and idempotency completion in the same transaction

Partition violations return before mutable row replacement.

## Idempotency

The new endpoint uses:

```text
operation = registry.project_partition_replace
project_id = principal.ProjectID
actor_id = principal.ActorID
```

The idempotency request summary stores partition evidence, including the diff fingerprint. The conflict fingerprint uses stable caller request fields and proposed registry fingerprint so a replay does not conflict merely because current registry became the committed target after the first request.

Cached idempotency responses include the full partition result, including `partition_decision`.

## Audit Evidence

Success and failure audit action:

```text
registry.project_partition_replace
```

Audit metadata includes:

- hosted principal evidence
- `partition_project_id`
- `partition_diff_fingerprint`
- changed counts
- rejected counts when safe
- registry fingerprints
- idempotency key hash/prefix only

Raw public tokens, gateway secrets, raw idempotency keys, and credential secrets are not written by this path.

## Tests

Added and updated coverage for:

- registry-layer project partition replacement success
- same-transaction partition validation before mutable row replacement
- partition violation returns `REGISTRY_PARTITION_VIOLATION`
- partition violation does not replace mutable rows
- project-scoped idempotency operation and cached partition response
- idempotency replay returns cached partition evidence
- HTTP endpoint registration
- local/private principal rejection
- broad import/replace permission is insufficient
- required request/idempotency headers
- invalid JSON/body wrapper
- identity override rejection
- partition evidence response shape
- replay headers and `200 OK`
- `REGISTRY_PARTITION_VIOLATION -> 403`
- gateway permission map includes the new endpoint

## Validation

Passed:

```text
go test ./...
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
```

Go test directory:

```text
services/control-plane
```

## Non-Goals Preserved

Not added:

- public CRUD
- OAuth/OIDC
- public user/project/role CRUD
- invitation/login/session lifecycle
- production gateway deployment
- durable hosted permission store
- provider onboarding
- marketplace
- vault writes
- billing
- workflow runtime
- automatic snapshot export/publish/reload
- Data Plane reads from mutable Control Plane tables

## Recommended Next Task

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Live Dogfood + Closeout v0
```

That task should run the endpoint against a real service process and live Postgres through the local hosted gateway harness, then close the slice if evidence confirms trusted-only access, partition rejection, audit/idempotency evidence, and no automatic propagation.
