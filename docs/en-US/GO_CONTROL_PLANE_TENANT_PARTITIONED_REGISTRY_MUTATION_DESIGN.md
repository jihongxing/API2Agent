# Go Control Plane Tenant-Partitioned Registry Mutation Design v0

Date: 2026-06-01

Status: complete

## Decision

The next hosted Control Plane mutation primitive should be a tenant-partitioned registry mutation boundary, not public CRUD and not another full-registry replacement endpoint.

Recommended next implementation task:

```text
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness v0
```

That implementation should add local contract tests or dogfood-only helpers that prove the partition validation rules before changing production mutation behavior.

## Why This Slice Now

Hosted admin identity, trusted gateway authentication, gateway header stripping, gateway-issued permissions, and idempotency scope are now proven locally.

The remaining hosted risk is mutation scope:

```text
trusted project-scoped principal
  -> currently can call registry.import_replace
  -> full mutable registry graph can be replaced
```

For local/private administration this is acceptable. For hosted administration it is too broad. A project-scoped actor must not be able to delete or rewrite another project, another project credential metadata, platform routing policy, platform snapshot config, or shared capability definitions.

## Current Baseline

The mutable registry graph currently contains:

- `projects`
- `api_keys`
- `capabilities`
- `providers`
- `credential_metadata`
- `routing_policies`
- `snapshot_configs`

The current import/replace implementation:

- validates the full registry graph
- deletes all mutable registry rows
- inserts the replacement graph
- writes `registry_revisions`
- writes `admin_audit_events`
- completes idempotency records scoped by `project_id + actor_id + operation + idempotency_key_hash`

Existing project-owned or project-related fields:

- `api_keys.project_id`
- `credential_metadata.owner_type=project`
- `credential_metadata.owner_id=<project_id>`
- admin principal `ProjectID`
- admin audit metadata `project_id`
- idempotency `project_id`

Objects that are still effectively platform/global in v0:

- `capabilities`
- provider candidate definitions without explicit owner metadata
- active global `routing_policy`
- active `snapshot_config`

## Goals

- define how hosted project identity constrains registry mutation scope
- define a safe project partition envelope
- prevent cross-project deletion, overwrite, or ownership transfer
- keep global/platform registry objects protected from project-scoped mutation
- preserve full-registry validation before commit
- preserve registry revision, audit, and idempotency evidence
- preserve snapshot export/publish/reload separation
- define stable failure semantics and tests for a later implementation slice

## Non-Goals

Do not implement:

- public CRUD APIs
- public project/user/role CRUD
- OAuth/OIDC provider integration
- invitation/login/session lifecycle
- production gateway deployment
- durable hosted permission store
- provider onboarding workflow
- marketplace/provider submission
- credential vault writes
- plaintext credential storage
- billing or settlement state
- workflow runtime
- automatic snapshot export, publish, or Data Plane reload
- Data Plane reads from mutable Control Plane tables

## Boundary Model

Introduce a conceptual mutation mode:

```text
project_partition_replace
```

This mode accepts a full registry document as the proposed target view, but only permits changes inside the authenticated principal's project partition.

The project partition is derived from:

```text
partition_project_id = resolved AdminPrincipal.ProjectID
```

It must not come from:

- request body
- public headers
- `X-Actor-ID`
- URL path parameters supplied by a public caller
- query parameters

For local/private mode, `project_partition_replace` should remain disabled unless tests explicitly inject a hosted-style principal. Local/private full import/replace remains available for operator administration.

## Project Partition Definition

### Owned By The Project

These rows may be changed by a project-scoped hosted mutation when their owner is exactly the resolved `ProjectID`:

| Object | Project ownership rule |
| --- | --- |
| `projects` | only the row with `id == principal.ProjectID`; status/name/default-mode policy must be explicit |
| `api_keys` | only rows where `project_id == principal.ProjectID` |
| `credential_metadata` | only rows where `owner_type == "project"` and `owner_id == principal.ProjectID` |
| project-owned providers | only rows with explicit future `owner_project_id == principal.ProjectID` or equivalent metadata |

### Read-Only For Project-Scoped Mutation

These rows must not be created, deleted, or changed by `project_partition_replace` in v0:

| Object | Rule |
| --- | --- |
| `capabilities` | platform/global only in v0 |
| providers without explicit project owner | platform/global only in v0 |
| providers owned by another project | reject |
| `credential_metadata` for user/platform/provider owners | reject |
| `routing_policies` with `scope_type=global` | reject |
| `routing_policies` for another project | reject |
| active `snapshot_configs` | platform/global only |

Project-scoped routing policy may be designed later, but v0 should not mutate routing policy rows unless resolver/export semantics already know how to apply them without changing the snapshot contract.

## Provider Ownership

Provider candidates currently do not have first-class project ownership. Therefore v0 must not allow project-scoped mutation of provider rows unless ownership is made explicit first.

Recommended future schema field:

```text
providers.owner_type in ('platform', 'project')
providers.owner_id
```

Minimal v0-compatible alternative for contract harness only:

```text
provider.metadata.owner_project_id
```

Rules:

- missing owner metadata means platform-owned.
- platform-owned providers are read-only for project-scoped mutation.
- `owner_project_id` must equal `principal.ProjectID` for project mutation.
- changing provider ownership is not allowed in a project-scoped mutation.
- changing `capability_id` or `capability_version` for an existing project-owned provider is not allowed unless the target capability already exists and remains platform-approved.
- provider metadata must still not contain secrets.

## Mutation Algorithm

Design a validator around the existing full-registry validation:

```text
current persistent registry
  + proposed registry
  + principal project id
  -> partition diff
  -> allow/reject decision
```

Steps:

1. Resolve admin principal and required permission.
2. Require hosted/trusted project scope.
3. Parse proposed registry wrapper.
4. Canonicalize and validate proposed full registry.
5. Load current persistent registry in the same serializable write transaction.
6. Compute a logical diff by stable object keys.
7. Reject any create/update/delete outside the caller's project partition.
8. Reject ownership transfers.
9. Reject global routing policy or snapshot config changes.
10. Reject capability changes in v0.
11. Execute replacement with the existing registry-wide mutation lock only after the partition diff passes.
12. Write registry revision, admin audit, and idempotency completion in the same transaction.

This keeps the database write primitive simple while adding a pre-commit safety gate.

## Permission Model

Do not reuse broad full-registry replacement permission for hosted project-scoped mutation.

Recommended permissions:

| Operation | Permission |
| --- | --- |
| full local/private import/replace | `control_plane.registry.import_replace` |
| hosted project partition replace | `control_plane.registry.project_partition_replace` |
| partition validation only | `control_plane.registry.project_partition_validate` |

The gateway permission source can map dogfood principals to these later, but this design does not modify the permission source.

## Endpoint Shape For Later Implementation

Prefer a separate private admin endpoint to avoid silently changing full import/replace semantics:

```text
POST /v1/admin/registry/project-partition/replace
```

Required:

- hosted/trusted gateway principal
- `X-Request-ID`
- `Idempotency-Key`
- request wrapper with `registry`

Rejected in v0:

- local/private principal unless explicitly enabled in contract tests
- request body project override
- dry-run execution that bypasses validation semantics

The existing endpoint remains:

```text
POST /v1/admin/registry/import-replace
```

It remains operator/full-registry oriented and should not be exposed as a public hosted project mutation surface.

## Idempotency Scope

Use the resolved principal:

```text
project_id = principal.ProjectID
actor_id = principal.ActorID
operation = registry.project_partition_replace
idempotency_key_hash = hash(Idempotency-Key)
```

Request fingerprint should include:

- operation
- method/path
- partition project id
- proposed registry fingerprint
- partition diff fingerprint
- source

Same key and same request replays the committed response.

Same key and different request returns:

```text
409 IDEMPOTENCY_KEY_CONFLICT
```

Different projects can reuse the same raw idempotency key independently because `project_id` is part of the scope.

## Audit Evidence

Required action:

```text
registry.project_partition_replace
```

Required audit metadata:

- `project_id`
- `organization_id` when available
- `principal_subject_id`
- `auth_method`
- `token_id` when available
- `gateway_key_id` when available
- `partition_project_id`
- `mutation_mode=project_partition_replace`
- `registry_fingerprint`
- `previous_registry_fingerprint`
- `partition_diff_fingerprint`
- affected object counts by class:
  - `projects_changed`
  - `api_keys_changed`
  - `credential_metadata_changed`
  - `providers_changed`
- rejected object counts by class on failure when safe
- idempotency key hash/prefix only, never raw key

Audit metadata must not contain:

- raw public bearer token
- trusted gateway secret
- provider credential secret
- plaintext API key material

## Snapshot Boundary

Partitioned mutation still changes Control Plane mutable state only.

It must not automatically:

- export a snapshot artifact
- publish distribution `current.json`
- reload Data Plane instances
- let Data Plane read mutable Control Plane tables

The follow-up remains explicit:

```text
project_partition_replace
  -> snapshot export
  -> distribution publish
  -> Data Plane reload
```

Snapshot export continues to produce a full immutable routing snapshot. Project partitioning constrains mutation authority; it does not make the Data Plane consume partial mutable views.

## Failure Semantics

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| missing/invalid hosted identity | 401 | `AUTH_ERROR` | caller | false |
| missing required permission | 403 | `AUTHZ_DENIED` | caller | false |
| principal missing project scope | 403 | `AUTHZ_DENIED` | caller | false |
| local/private principal used on hosted partition endpoint | 403 | `AUTHZ_DENIED` | caller | false |
| invalid JSON/body wrapper | 400 | `INVALID_REQUEST` | caller | false |
| invalid full registry graph | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| proposed change outside partition | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| ownership transfer attempted | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| global object changed | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| idempotency key conflict | 409 | `IDEMPOTENCY_KEY_CONFLICT` | caller | false |
| concurrent mutation lock conflict | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

Gateway-local auth/authz denials remain gateway-local and should not create Control Plane audit/idempotency rows.

Control Plane partition violations occur after trusted forwarding and should create failure audit when the audit sink is available.

## Validation Rules

The partition validator should reject:

- deleting any project row other than `principal.ProjectID`
- changing another project row
- deleting another project's API key metadata
- adding API key metadata for another project
- changing `credential_metadata` owned by another project
- changing `credential_metadata` with `owner_type != project`
- changing platform-owned providers
- changing providers owned by another project
- changing provider ownership metadata
- adding provider rows without explicit project ownership
- changing capabilities
- changing active global routing policy
- changing active snapshot config
- changing registry graph in a way that fails existing `Registry.Validate()`

The validator may allow:

- updating allowed fields on the caller's own project row
- adding/removing/updating caller-project API key metadata, still without plaintext key material
- adding/removing/updating caller-project credential metadata, still metadata-only
- adding/removing/updating explicitly caller-owned provider rows after provider ownership is represented

## Contract Harness Plan

The next implementation should prove the rules before changing production endpoints.

Suggested harness/tests:

1. Same-project API key metadata change passes.
2. Same-project credential metadata change passes.
3. Another project's API key deletion fails with `REGISTRY_PARTITION_VIOLATION`.
4. Another project's credential metadata change fails with `REGISTRY_PARTITION_VIOLATION`.
5. Global routing policy change fails with `REGISTRY_PARTITION_VIOLATION`.
6. Active snapshot config change fails with `REGISTRY_PARTITION_VIOLATION`.
7. Capability change fails with `REGISTRY_PARTITION_VIOLATION`.
8. Platform-owned provider change fails with `REGISTRY_PARTITION_VIOLATION`.
9. Project-owned provider change passes only when owner metadata matches principal project.
10. Provider ownership transfer fails.
11. Same idempotency key can be reused by different project scopes.
12. Same idempotency key with different request in one project fails.
13. Failure audit includes partition evidence but no secrets.
14. Successful mutation does not export, publish, reload, or touch Data Plane mutable reads.

## Acceptance Criteria

This design is accepted when:

- project partition ownership rules are explicit
- global/platform read-only objects are explicit
- provider ownership gap and migration options are explicit
- mutation algorithm is explicit
- endpoint and permission shape for later implementation are explicit
- idempotency and audit evidence are explicit
- snapshot boundary remains explicit
- failure semantics are explicit
- tests/dogfood expectations are named
- public CRUD, OAuth/OIDC, production gateway deployment, vault, billing, marketplace, workflow runtime, provider onboarding, automatic propagation, and Data Plane mutable-table reads remain out of scope

## Recommended Next Task

```text
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness v0
```

That task should implement only local validation helpers, tests, or dogfood harness coverage for the partition rules. It should not expose a public CRUD surface or deploy a production gateway.
