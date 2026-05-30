# Go Control Plane Persistent Registry Store Design v0

Date: 2026-05-31

Status: design frozen for the next implementation slice

Decision: API2Agent should introduce a persistent registry store behind the existing `registry.Store` boundary while preserving the current Data Plane snapshot contract.

## 1. Goal

Move Control Plane state from a local file registry toward a durable database-backed registry without changing:

- routing snapshot shape
- artifact manifest semantics
- distribution pointer semantics
- Data Plane snapshot loading behavior
- registry validation rules
- registry fingerprint audit field

The database becomes a Control Plane source of truth. The exported snapshot remains the Data Plane contract.

## 2. Non-Goals

This design does not implement:

- hosted deployment
- public signup or user management
- secret vault storage
- provider billing
- marketplace
- remote object storage
- distributed publish locks
- registry mutation HTTP APIs

## 3. Current Boundary

Current Go interface:

```go
type Store interface {
    Load(ctx context.Context) (*Registry, error)
}
```

Current implementation:

```text
registry.FileStore
```

Design rule:

```text
Persistent store v0 must implement Load(ctx) without changing snapshot export callers.
```

Future mutation APIs should use a separate writer interface. They should not be squeezed into the read-only `Store` contract.

## 4. Persistent Store Contract

`PostgresStore.Load(ctx)` must:

1. Open a read-only transaction.
2. Read one consistent active registry view.
3. Build the same in-memory `registry.Registry` object used by `FileStore`.
4. Sort rows deterministically before constructing arrays.
5. Run `Registry.Validate()`.
6. Return the registry to the existing exporter.

The exporter must not know whether the registry came from file or Postgres.

## 5. First Postgres Table Model

This is a logical model, not yet a migration file.

### 5.1 `projects`

Stores project identity metadata.

Required fields:

- `id`
- `name`
- `status`
- `default_mode`
- `created_at`
- `updated_at`

Constraints:

- `id` primary key
- `status in ('active', 'disabled')`
- `default_mode in ('direct', 'proxy', 'shadow', 'replay')` when present

### 5.2 `api_keys`

Stores API2Agent project key metadata.

Required fields:

- `id`
- `project_id`
- `key_prefix`
- `key_hash`
- `status`
- `created_at`
- `updated_at`

Constraints:

- `id` primary key
- `project_id` references `projects(id)`
- `status in ('active', 'disabled', 'revoked')`
- raw API keys must never be stored

`key_hash` is included in the persistent model even though the current local registry only carries `key_prefix`. Hosted API key verification cannot rely on prefixes alone.

### 5.3 `capabilities`

Stores canonical capability definitions.

Required fields:

- `id`
- `version`
- `name`
- `status`
- `created_at`
- `updated_at`

Constraints:

- primary key: `(id, version)`
- `status in ('active', 'disabled')`

For snapshot v0, only active capabilities should be exported.

### 5.4 `providers`

Stores provider candidates for capabilities.

Required fields:

- `id`
- `capability_id`
- `capability_version`
- `provider_id`
- `provider_version`
- `mapping_version`
- `tool_id`
- `regions`
- `geo_affinity`
- `estimated_cost`
- `metadata`
- `status`
- `created_at`
- `updated_at`

Constraints:

- `id` primary key
- `(capability_id, capability_version)` references `capabilities(id, version)`
- `regions` must be non-empty
- active providers must include `metadata.base_url`
- `status in ('active', 'disabled')`

`metadata` should be stored as JSONB. It must not contain provider secrets.

### 5.5 `credential_metadata`

Stores credential ownership and policy metadata only.

Required fields:

- `credential_id`
- `credential_version`
- `owner_type`
- `owner_id`
- `provider_id`
- `auth_type`
- `injection_mode`
- `source`
- `scope`
- `status`
- `rotation_hint`
- `created_at`
- `updated_at`

Constraints:

- `credential_id` primary key
- `provider_id` references provider logical ids
- `owner_type in ('user', 'project', 'platform', 'provider')`
- `auth_type in ('api_key', 'bearer', 'basic', 'oauth', 'none')`
- `injection_mode in ('header', 'query', 'body', 'none')`
- `source in ('env', 'config', 'inline', 'vault', 'none')`
- `status in ('active', 'disabled', 'expired')`
- no raw secret values

Secret values belong in a future vault, not in this table.

### 5.6 `routing_policies`

Stores routing policy configuration.

Required fields:

- `id`
- `scope_type`
- `scope_id`
- `strategy`
- `routing_mode`
- `routing_seed`
- `failover_policy`
- `status`
- `created_at`
- `updated_at`

Constraints:

- `scope_type in ('global', 'project', 'capability')`
- `strategy in ('first', 'lowest_cost', 'lowest_latency', 'region_aware_latency', 'highest_success_rate', 'balanced')`
- `routing_mode in ('deterministic', 'stochastic')`
- only one active global policy in v0

`failover_policy` should be JSONB to preserve the existing snapshot structure.

### 5.7 `snapshot_configs`

Stores snapshot export settings.

Required fields:

- `id`
- `version`
- `fetched_at`
- `ttl`
- `source`
- `status`
- `created_at`
- `updated_at`

Constraints:

- only one active config in v0
- `source in ('push', 'pull')`
- `ttl` must parse as a Go duration

### 5.8 `registry_revisions`

Records immutable registry export revisions.

Required fields:

- `id`
- `registry_fingerprint`
- `snapshot_version`
- `source_store`
- `source_revision`
- `created_by`
- `created_at`

Purpose:

- audit which registry state produced a snapshot artifact
- support replaying or comparing old exports
- decouple mutable registry tables from immutable snapshot history

### 5.9 `snapshot_artifact_publications`

Records artifact and distribution publication metadata.

Required fields:

- `id`
- `snapshot_version`
- `registry_fingerprint`
- `snapshot_digest`
- `artifact_uri`
- `manifest_uri`
- `distribution_uri`
- `published_by`
- `published_at`
- `status`

Constraints:

- unique active `snapshot_version`
- `status in ('pending', 'published', 'failed', 'replaced')`

For local v0, URIs can be file paths. Hosted storage can later move them to object storage URIs.

### 5.10 `admin_audit_events`

Records Control Plane administrative actions.

Required fields:

- `id`
- `actor_id`
- `action`
- `resource_type`
- `resource_id`
- `request_id`
- `outcome`
- `error_type`
- `metadata`
- `created_at`

Actions should include:

- `registry.validate`
- `snapshot.export_artifact`
- `distribution.publish`
- `distribution.current.read`

This is a design requirement for hosted readiness. It is not implemented in the current local service.

## 6. Transaction Boundaries

### 6.1 Registry Load

Use one read-only transaction.

Isolation target:

```text
REPEATABLE READ
```

Rules:

- read active snapshot config
- read active projects, API keys, capabilities, providers, credential metadata, and routing policy
- sort every collection deterministically
- build `registry.Registry`
- validate before returning

### 6.2 Artifact Export

Use one consistent registry read transaction to build the registry and compute fingerprint.

Then:

1. Export snapshot and manifest using existing code.
2. Write artifact files or future object storage objects.
3. Record a `registry_revisions` row.
4. Record an `admin_audit_events` row.

The exported snapshot must remain valid even if registry tables change immediately after export.

### 6.3 Distribution Publish

For local filesystem v0:

1. Validate artifact content.
2. Publish using the existing atomic local publisher.
3. Insert `snapshot_artifact_publications` with `status='published'`.
4. Insert `admin_audit_events`.

For future remote storage:

1. Insert publication row as `pending`.
2. Write artifact objects.
3. Compare-and-swap distribution pointer.
4. Mark publication as `published` or `failed`.

Do not design remote storage transactions as if the database can atomically control object storage.

## 7. Fingerprint and Versioning Rules

Database-backed fingerprints must be deterministic.

Rules:

- fingerprint input is the canonical `registry.Registry` JSON
- internal database IDs are excluded
- timestamps such as `created_at` and `updated_at` are excluded
- collections are sorted by stable logical keys
- empty optional fields follow the same JSON behavior as the current Go models
- the output prefix remains `sha256:`

Recommended sort keys:

- projects: `id`
- API keys: `id`
- capabilities: `id`, then `version`
- providers: `id`
- credential metadata: `credential_id`
- routing policy: active global policy first

Snapshot version policy remains explicit in v0.

## 8. Migration and Dual-Store Strategy

### Step 1: File Import Design

Load existing `registry.json`, validate it, and map it into the database model.

### Step 2: Dual Export

For the same logical registry state:

```text
FileStore.ExportSnapshot()
PostgresStore.ExportSnapshot()
```

must produce equivalent snapshots.

Allowed differences:

- `registry_store`
- `registry_source`
- export timestamps

Not allowed to differ:

- capabilities
- providers
- routing policy
- snapshot metadata
- registry fingerprint after canonicalization

### Step 3: Service Store Selection

Future service startup should accept:

```text
--registry-store file|postgres
```

File store remains the default until Postgres dogfood passes.

## 9. Implementation Sequence After This Design

Recommended next implementation after this design:

```text
Go Control Plane Persistent Registry Store Schema v0
```

Scope:

1. Add a SQL schema or migration draft.
2. Add a test fixture that imports the existing file registry into the schema.
3. Add deterministic ordering tests for canonical registry export.
4. Keep `FileStore` as the default runtime store.

Do not implement registry mutation APIs before load/export parity is proven.

## 10. Acceptance Criteria

Persistent Registry Store Design v0 is complete when:

- the table model is explicit
- transaction boundaries are explicit
- fingerprint rules are explicit
- migration and dual-store strategy are explicit
- next implementation scope is narrowed to schema/load parity
- Data Plane snapshot contract remains unchanged

## 11. Strategic Judgment

The persistent store is not the product by itself.

Its purpose is to let API2Agent manage real Control Plane state while keeping the Data Plane contract stable:

```text
Control Plane state can change.
Snapshot contract must stay stable.
```

That separation is the core infrastructure discipline for the next stage.
