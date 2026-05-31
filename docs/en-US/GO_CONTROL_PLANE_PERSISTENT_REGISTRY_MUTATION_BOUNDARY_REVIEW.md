# Go Control Plane Persistent Registry Mutation Boundary Review v0

Date: 2026-05-31

Status: complete

## Summary

The persistent registry now has schema, load parity, runtime selection, live Postgres dogfood, persistent audit writes, and hardened failure semantics.

This review decides the mutation boundary before adding any write API.

Decision:

```text
Do not add granular registry CRUD APIs yet.
The next safe write-side step is a controlled full-registry import/replace transaction.
```

The reason is simple: API2Agent needs durable registry writes, but the registry objects are tightly coupled. Updating one provider, credential metadata row, routing policy, or snapshot config independently can produce invalid or unexplained routing snapshots unless the whole registry view is validated and revised atomically.

## Current Write Surface

Current persistent writes are intentionally narrow:

- `seed-postgres` imports a file registry into Postgres for local dogfood.
- artifact export writes `registry_revisions`.
- distribution publish writes `snapshot_artifact_publications`.
- admin operations write `admin_audit_events`.

There is no registry mutation API yet.

## Registry Object Classes

### Mutable Registry State

These tables define the active registry view loaded by `PostgresStore.Load(ctx)`:

- `projects`
- `api_keys`
- `capabilities`
- `providers`
- `credential_metadata`
- `routing_policies`
- `snapshot_configs`

They must be mutated as a validated registry graph, not as unrelated rows.

### Append-Only Control Evidence

These tables are evidence/audit surfaces and should not be directly edited by registry mutation APIs:

- `registry_revisions`
- `snapshot_artifact_publications`
- `admin_audit_events`

They are written as consequences of controlled operations.

## Boundary Decision

### Allowed Next

Implement a controlled full-registry import/replace path.

Recommended shape:

```text
input registry JSON
  -> parse
  -> canonicalize
  -> validate full Registry
  -> compute registry_fingerprint
  -> begin write transaction
  -> acquire registry mutation lock
  -> upsert/replace mutable registry tables
  -> write registry_revisions
  -> write admin_audit_events
  -> commit
```

This may start as a CLI/admin operation, not a public hosted API.

### Not Allowed Yet

Do not implement:

- public CRUD endpoints for individual registry objects
- provider onboarding APIs
- credential vault writes
- API key secret generation or plaintext storage
- marketplace provider submission
- billing or settlement state
- partial mutation APIs that bypass full registry validation

## Object-Level Mutation Rules

### `projects`

Allowed later:

- create/update project metadata
- soft-disable a project
- change `default_mode` only to valid execution modes

Not yet:

- hosted user/org ownership model
- hard delete

Requirement:

- project changes must not orphan active API keys or credential metadata.

### `api_keys`

Allowed later:

- create active key metadata with `key_hash`
- revoke or disable keys
- rotate key material by creating a new key row and revoking the old one

Not yet:

- plaintext key storage
- hosted key issuance UX

Requirement:

- plaintext API keys must never be returned or stored in registry rows.

### `capabilities`

Allowed later:

- add a new capability version
- disable an old version
- update name/status metadata

Not yet:

- destructive delete

Requirement:

- active providers must reference an existing active capability version.

### `providers`

Allowed later:

- add/update provider metadata
- disable providers
- change region/cost/base URL metadata through full validation

Not yet:

- public provider self-onboarding
- marketplace ranking edits

Requirement:

- active providers must have valid capability references, region metadata, mapping versions, and `metadata.base_url`.

### `credential_metadata`

Allowed later:

- add/update credential metadata references
- disable/expire metadata
- update scope and rotation hints

Not yet:

- secret value storage
- vault-backed secret writes
- OAuth delegated credential flows

Requirement:

- this table stores metadata only. Secret material belongs to a future vault boundary.

### `routing_policies`

Allowed later:

- replace the active global policy
- add project/capability scoped policies after resolver semantics exist

Not yet:

- hidden marketplace preference injection
- stochastic policy defaults without explicit seed semantics

Requirement:

- exactly one active global policy must remain valid.

### `snapshot_configs`

Allowed later:

- replace the active snapshot config during registry import/replace

Not yet:

- multi-active snapshot configs
- external snapshot distribution control

Requirement:

- exactly one active snapshot config must remain valid.

## Transaction Requirements

Future write-side operations must:

- run in a single database transaction
- acquire a registry-wide mutation lock
- validate the full registry view before commit
- write `registry_revisions` in the same transaction
- write an `admin_audit_events` row in the same transaction
- return deterministic machine-readable errors
- avoid partial success states

Recommended lock:

```text
pg_advisory_xact_lock(...)
```

Recommended isolation:

```text
SERIALIZABLE for full import/replace
```

## Idempotency Requirements

Full import/replace should be idempotent by registry fingerprint.

If the incoming registry fingerprint matches the current active registry fingerprint, the operation should:

- not rewrite mutable rows unnecessarily
- return success
- record an admin audit event with a no-op marker

Future HTTP mutation APIs must require an idempotency key before they are implemented.

## Audit Requirements

Every accepted mutation must produce:

- `registry_revisions`
- `admin_audit_events`

Every rejected mutation should produce best-effort `admin_audit_events` when the audit sink is available.

Audit metadata should include:

- `registry_store`
- `registry_fingerprint`
- `previous_registry_fingerprint` when available
- `mutation_mode`
- `idempotency_key` when available
- affected object counts

## Failure Semantics

Recommended stable errors for the next implementation:

| Condition | HTTP | error_type | scope | retryable |
| --- | ---: | --- | --- | --- |
| Invalid registry payload | 400 | `REGISTRY_MUTATION_INVALID` | caller | false |
| Persistent read failure | 503 | `PERSISTENT_STORE_READ_FAILED` | platform | true |
| Persistent write failure | 503 | `PERSISTENT_STORE_WRITE_FAILED` | platform | true |
| Concurrent mutation conflict | 409 | `REGISTRY_MUTATION_CONFLICT` | platform | true |
| Required audit write failure | 500 | `AUDIT_WRITE_FAILED` | platform | true |

## Rollback Requirements

If mutable registry writes fail, the transaction must roll back:

- mutable registry rows
- `registry_revisions`
- success `admin_audit_events`

Failure audit can be best-effort outside the failed transaction only when it does not obscure the original failure.

## Recommended Next Task

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```

This should design, but not yet expose as a public API, a single controlled write path for replacing the active persistent registry view from a validated registry document.

## Non-Goals

- No mutation API was implemented in this review.
- No schema migration was added.
- No hosted auth was added.
- No vault was added.
- No billing, settlement, or marketplace work was added.
