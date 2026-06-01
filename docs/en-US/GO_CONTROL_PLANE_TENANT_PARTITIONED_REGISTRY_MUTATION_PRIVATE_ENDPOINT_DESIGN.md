# Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Design v0

Date: 2026-06-01

Status: complete

## Decision

Add a private hosted admin endpoint contract for project-scoped registry replacement:

```text
POST /v1/admin/registry/project-partition/replace
```

This design does not implement the endpoint. It defines the future implementation boundary that composes the existing hosted trusted-gateway principal, permission-source proof, admin idempotency store, persistent registry replacement transaction, and tenant-partition validation helper.

Recommended next implementation task:

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Implementation v0
```

This endpoint must not become public CRUD. It is a private Control Plane admin surface that is reachable only after a hosted gateway has authenticated the public caller, stripped caller-supplied trusted headers, issued trusted project-scoped claims, and forwarded over the trusted gateway boundary.

## Why This Slice Now

The previous slices proved:

- hosted admin identity shape and trusted-gateway principal resolution
- gateway-side trusted header stripping and injection
- gateway-local permission-source decisions
- Control Plane endpoint permission checks as the second gate
- project-scoped audit and idempotency evidence
- local partition validation that rejects cross-project and global registry edits

The remaining risk is endpoint composition:

```text
hosted project principal
  -> project partition endpoint
  -> persistent registry transaction
  -> partition validator
  -> revision + audit + idempotency evidence
```

The implementation must make the partition validator part of the same write transaction that commits the replacement. Loading current registry outside the write transaction would create a stale-check gap. Therefore this design introduces a registry-layer project partition replacement seam rather than asking the HTTP handler to compose the write manually.

## Endpoint Contract

```text
POST /v1/admin/registry/project-partition/replace
```

The endpoint accepts a full registry document as the proposed target view, but only changes inside the authenticated principal's project partition are allowed.

The partition project is always:

```text
partition_project_id = resolved AdminPrincipal.ProjectID
```

It must not be supplied by:

- request body
- query string
- URL path
- public caller headers
- `X-Actor-ID`
- any future public project selector

The existing full import/replace endpoint remains separate:

```text
POST /v1/admin/registry/import-replace
```

That endpoint stays operator/full-registry oriented and must not be exposed as the hosted project mutation surface.

## Required Principal

The Control Plane handler must resolve an admin principal with:

```text
control_plane.registry.project_partition_replace
```

Required principal properties:

- `AuthMethod == trusted_gateway`
- `LocalPrivate == false`
- non-empty `SubjectID`
- non-empty `ActorID`
- non-empty `ProjectID`
- permission list contains `control_plane.registry.project_partition_replace`

Rejected:

- local/private admin-token principals
- hosted principals without project scope
- hosted principals with only `control_plane.registry.import_replace`
- caller-supplied trusted headers that do not pass the trusted gateway authenticator

Local/private full import/replace remains available on the existing operator endpoint. It is intentionally not widened to this hosted partition endpoint.

## Required Headers

| Header | Required | Source |
| --- | --- | --- |
| `Authorization: Bearer <gateway-secret>` | yes | trusted gateway to Control Plane |
| `X-API2Agent-Subject-ID` | yes | gateway-issued trusted identity claim |
| `X-API2Agent-Actor-ID` | yes | gateway-issued trusted actor claim |
| `X-API2Agent-Project-ID` | yes | gateway-issued trusted project claim |
| `X-API2Agent-Permissions` | yes | gateway-issued trusted permission claim |
| `X-Request-ID` | yes | gateway-forwarded request correlation |
| `Idempotency-Key` | yes | gateway-forwarded mutation safety key |

Header validation:

- missing or blank `X-Request-ID` returns `400 INVALID_REQUEST`
- missing or blank `Idempotency-Key` returns `400 INVALID_REQUEST`
- trusted identity failures return `401 AUTH_ERROR`
- missing permission or project scope returns `403 AUTHZ_DENIED`
- the handler must never trust public identity or permission headers directly

## Request Body

Use the same wrapper pattern as import/replace, with a narrower mutation mode:

```json
{
  "registry": {
    "projects": [],
    "api_keys": [],
    "capabilities": [],
    "providers": [],
    "credential_metadata": [],
    "routing_policy": {},
    "snapshot": {}
  },
  "source": "hosted_project_partition_replace",
  "dry_run": false
}
```

Fields:

| Field | Required | v0 behavior |
| --- | --- | --- |
| `registry` | yes | Full proposed registry graph to canonicalize, validate, and partition-check. |
| `source` | no | Audit hint. If absent, use `hosted_project_partition_replace`. |
| `dry_run` | no | Reserved. Omitted or `false` is allowed; `true` returns `400 INVALID_REQUEST` in v0. |

Rejected v0 body fields:

- `project_id`
- `partition_project_id`
- `actor_id`
- `organization_id`
- `permissions`
- any project override or identity override field

The registry remains metadata-only. Plaintext API keys, OAuth tokens, provider secrets, vault material, or gateway secrets must not be accepted or persisted by this endpoint.

## Request Size Limit

Use the same bounded default as private import/replace:

```text
2 MiB
```

Body-size failures return:

```text
413 REQUEST_BODY_TOO_LARGE
```

## Registry-Layer Seam

Do not make the HTTP handler load current registry, call the validator, and then call `ReplacePersistentRegistry` as separate steps.

The future implementation should add a registry-layer seam that owns the transaction:

```go
type ProjectPartitionReplaceOptions struct {
    Principal      registry.AdminPrincipal
    RequestID      string
    IdempotencyKey string
    Source         string
}

type ProjectPartitionReplaceResult struct {
    RegistryStore               string
    RegistryFingerprint          string
    PreviousRegistryFingerprint  string
    SnapshotVersion              string
    Noop                         bool
    Replayed                     bool
    Counts                       registry.RegistryCounts
    PartitionDecision            registry.ProjectPartitionMutationDecision
}

type RegistryProjectPartitionReplacer interface {
    ReplaceProjectPartitionRegistry(
        ctx context.Context,
        proposed registry.Registry,
        opts ProjectPartitionReplaceOptions,
    ) (ProjectPartitionReplaceResult, error)
}
```

The registry-layer implementation should:

1. begin the same serializable write transaction used by persistent registry replacement
2. acquire the existing registry mutation lock
3. load the current persistent registry inside that transaction
4. canonicalize and validate the proposed full registry graph
5. call `ValidateProjectPartitionMutation(current, proposed, principal.ProjectID)`
6. reject before writing if the decision is not allowed
7. compute the idempotency request fingerprint from registry and partition evidence
8. apply the replacement only after the partition decision passes
9. write registry revision, admin audit, and idempotency completion in the same transaction

This keeps the stale-read and time-of-check/time-of-use boundary closed.

## Idempotency

Operation:

```text
registry.project_partition_replace
```

Scope:

```text
project_id = principal.ProjectID
actor_id = principal.ActorID
operation = registry.project_partition_replace
idempotency_key_hash = hash(Idempotency-Key)
```

The request fingerprint should include:

- HTTP method and path
- operation
- principal project id
- principal actor id
- proposed registry fingerprint
- previous registry fingerprint when known
- partition diff fingerprint
- source

Expected behavior:

- same scope, same key, same request returns the stored committed response with `replayed=true`
- same scope, same key, different request returns `409 IDEMPOTENCY_KEY_CONFLICT`
- different projects may reuse the same raw idempotency key because project scope is part of the idempotency key
- raw idempotency keys must not be written to audit metadata or dogfood artifacts

## Response Shape

Changed registry:

```http
201 Created
```

```json
{
  "registry_store": "postgres",
  "registry_fingerprint": "sha256:...",
  "previous_registry_fingerprint": "sha256:...",
  "snapshot_version": "snapshot_v1",
  "noop": false,
  "replayed": false,
  "partition_project_id": "project_alpha",
  "partition_diff_fingerprint": "sha256:...",
  "partition_counts": {
    "projects_changed": 0,
    "api_keys_changed": 1,
    "credential_metadata_changed": 1,
    "providers_changed": 0
  },
  "counts": {
    "projects": 2,
    "api_keys": 3,
    "capabilities": 1,
    "providers": 1,
    "credential_metadata": 2,
    "routing_policies": 1,
    "snapshot_configs": 1
  }
}
```

No-op:

```http
200 OK
```

The response shape is the same, with `noop=true`.

Idempotency replay:

```http
200 OK
```

The response shape is the committed result, with `replayed=true`.

## Error Mapping

Use the existing service error envelope:

```json
{
  "error": {
    "error_type": "REGISTRY_PARTITION_VIOLATION",
    "error_scope": "caller",
    "message": "...",
    "retryable": false
  }
}
```

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| missing/invalid trusted gateway auth | 401 | `AUTH_ERROR` | caller | false |
| missing required permission | 403 | `AUTHZ_DENIED` | caller | false |
| principal missing project scope | 403 | `AUTHZ_DENIED` | caller | false |
| local/private principal used on this endpoint | 403 | `AUTHZ_DENIED` | caller | false |
| wrong method | 405 | `INVALID_REQUEST` | caller | false |
| missing `X-Request-ID` | 400 | `INVALID_REQUEST` | caller | false |
| missing `Idempotency-Key` | 400 | `INVALID_REQUEST` | caller | false |
| invalid JSON body | 400 | `INVALID_REQUEST` | caller | false |
| missing `registry` wrapper field | 400 | `INVALID_REQUEST` | caller | false |
| body contains project or identity override | 400 | `INVALID_REQUEST` | caller | false |
| `dry_run=true` in v0 | 400 | `INVALID_REQUEST` | caller | false |
| request body over limit | 413 | `REQUEST_BODY_TOO_LARGE` | caller | false |
| service not configured for Postgres mutation | 409 | `REGISTRY_MUTATION_UNAVAILABLE` | platform | false |
| invalid registry graph | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| proposed change outside project partition | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| ownership transfer attempted | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| global object changed | 403 | `REGISTRY_PARTITION_VIOLATION` | caller | false |
| idempotency key conflict | 409 | `IDEMPOTENCY_KEY_CONFLICT` | caller | false |
| concurrent registry mutation | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

The service-level registry mutation error mapper should explicitly map:

```text
REGISTRY_PARTITION_VIOLATION -> 403
```

Unknown registry-layer errors should fail closed as `500 REGISTRY_MUTATION_FAILED`.

## Audit Evidence

Required action:

```text
registry.project_partition_replace
```

Required metadata:

- `registry_store=postgres`
- `mutation_mode=project_partition_replace`
- `project_id`
- `organization_id` when available
- `principal_subject_id`
- `principal_actor_id`
- `auth_method=trusted_gateway`
- `token_id` when available
- `gateway_key_id` when available
- `partition_project_id`
- `registry_fingerprint`
- `previous_registry_fingerprint`
- `partition_diff_fingerprint`
- `projects_changed`
- `api_keys_changed`
- `credential_metadata_changed`
- `providers_changed`
- rejected object counts on failure when safe
- idempotency key hash or prefix only
- `source`

Must not include:

- raw public bearer token
- gateway shared secret
- raw idempotency key
- provider credential secret
- plaintext API key material

Gateway-local auth/authz failures remain gateway-local and must not create Control Plane audit or idempotency rows. Partition violations happen after trusted forwarding, so the Control Plane should write failure audit when the audit sink is available.

## Permission Source Mapping

Future gateway permission-source implementation should map a hosted principal that can mutate its project partition to:

```text
control_plane.registry.project_partition_replace
```

It must not grant `control_plane.registry.import_replace` for hosted project mutation.

The local dogfood permission source may add this permission for a project-scoped test principal in the implementation slice, but this design does not add OAuth/OIDC, public role CRUD, or a durable permission store.

## Snapshot Boundary

The endpoint changes mutable Control Plane registry state only.

It must not automatically:

- export a snapshot artifact
- publish distribution `current.json`
- reload Data Plane instances
- let Data Plane read mutable Control Plane tables

The propagation sequence remains explicit:

```text
project partition replace
  -> snapshot export
  -> distribution publish
  -> Data Plane reload
```

## Tests Required For Implementation

Minimum HTTP and registry-layer tests:

1. route is registered at `POST /v1/admin/registry/project-partition/replace`
2. trusted-gateway auth is required
3. local/private principal is rejected
4. `control_plane.registry.project_partition_replace` is required
5. `control_plane.registry.import_replace` alone is insufficient
6. missing project scope returns `403 AUTHZ_DENIED`
7. `X-Request-ID` is required
8. `Idempotency-Key` is required
9. invalid JSON returns `400 INVALID_REQUEST`
10. missing `registry` returns `400 INVALID_REQUEST`
11. project or identity override fields return `400 INVALID_REQUEST`
12. `dry_run=true` returns `400 INVALID_REQUEST`
13. over-limit body returns `413 REQUEST_BODY_TOO_LARGE`
14. unconfigured/file-store mutation returns `409 REGISTRY_MUTATION_UNAVAILABLE`
15. invalid registry graph returns `400 REGISTRY_MUTATION_INVALID`
16. cross-project mutation returns `403 REGISTRY_PARTITION_VIOLATION`
17. global capability/routing/snapshot change returns `403 REGISTRY_PARTITION_VIOLATION`
18. valid same-project partition mutation invokes the registry-layer project partition replacer
19. partition validation is executed inside the replacement transaction
20. success response includes partition project id, diff fingerprint, changed counts, and registry fingerprints
21. failure audit includes partition evidence but no secrets
22. success audit includes hosted principal evidence but no raw keys/tokens
23. idempotency replay returns stored committed response
24. idempotency conflict returns `409 IDEMPOTENCY_KEY_CONFLICT`
25. gateway contract harness maps hosted project mutation permission without exposing full import/replace
26. mutation does not export, publish, reload, or touch Data Plane mutable reads

## Non-Goals

Do not implement:

- public CRUD registry APIs
- OAuth/OIDC provider integration
- public user/project/role CRUD
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

## Acceptance Criteria

This design is accepted when:

- method/path are documented
- hosted/trusted principal requirements are explicit
- project scope is derived only from the resolved principal
- request wrapper and rejected override fields are documented
- registry-layer transaction seam is explicit
- idempotency scope and request fingerprint are documented
- response shape includes partition evidence
- `REGISTRY_PARTITION_VIOLATION -> 403` is explicit
- audit evidence and secret redaction rules are documented
- snapshot propagation remains manual
- implementation test requirements are named
- public CRUD, OAuth/OIDC, production gateway deployment, vault, billing, marketplace, workflow runtime, provider onboarding, automatic propagation, and Data Plane mutable-table reads remain out of scope

## Recommended Next Task

```text
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Implementation v0
```

That task should implement the private hosted admin endpoint, registry-layer project partition replacement seam, permission constant, stable HTTP error mapping, tests, and local dogfood proof. It should not add public CRUD or automatic propagation.
