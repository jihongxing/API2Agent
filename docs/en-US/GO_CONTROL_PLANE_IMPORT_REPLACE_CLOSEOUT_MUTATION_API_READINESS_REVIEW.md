# Go Control Plane Import/Replace Closeout + Mutation API Readiness Review v0

Date: 2026-05-31

Status: complete

## Decision

The persistent registry import/replace slice is complete.

The local/admin CLI primitive is strong enough to close this implementation slice:

```text
api2agent-controlplane import-replace-postgres
```

Mutation API readiness decision:

```text
Ready for private admin endpoint design.
Not ready for endpoint implementation without a design step.
Not ready for public CRUD APIs.
```

Recommended next task:

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

## What Is Now Complete

### Transaction Design

Completed:

- serializable transaction boundary
- transaction-scoped advisory lock
- full mutable registry replacement
- no-op behavior by registry fingerprint
- same-transaction success audit and registry revision writes
- rollback rules
- snapshot boundary

Reference:

- `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_TRANSACTION_DESIGN.md`

### CLI Implementation

Completed:

- `registry.ReplacePersistentRegistry(ctx, db, reg, opts)`
- `api2agent-controlplane import-replace-postgres`
- structured `RegistryMutationError`
- unit tests for no-op, replacement, lock conflict, audit failure rollback, and transaction options

Reference:

- `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_CLI_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

Completed with podman:

- schema apply
- `seed-postgres`
- changed-registry import/replace
- same-registry no-op
- snapshot export after replacement
- audit count assertions

Observed:

```json
{
  "replace_noop": "false",
  "second_noop": "true",
  "snapshot_version": "snapshot_import_replace_live_v1",
  "provider_id": "httpbin_public_ip_v1",
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 2,
    "providers": 1
  }
}
```

Reference:

- `docs/en-US/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_LIVE_POSTGRES_DOGFOOD_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| Controlled full-registry write path exists | passed |
| Write path is local/admin only | passed |
| No public CRUD API added | passed |
| Serializable transaction used | passed |
| Registry-wide advisory lock used | passed |
| Same-fingerprint no-op behavior exists | passed |
| Non-noop writes registry revision | passed |
| Success writes admin audit | passed |
| Audit failure rolls back mutation | passed |
| Live Postgres replacement verified | passed |
| Live Postgres no-op verified | passed |
| Snapshot export sees replaced registry | passed |

## Readiness Judgment

### Ready

API2Agent is ready to design a private admin service endpoint for the same import/replace operation.

Reason:

- the core operation already exists as a reusable internal function
- persistent transaction behavior is unit-tested
- live Postgres dogfood passed
- existing Control Plane service already has an admin auth boundary
- registry validate/export/publish endpoints already use the same service pattern

### Not Ready

API2Agent is not ready to implement the endpoint without a design step.

The private endpoint design must specify:

- HTTP method and path
- request body shape
- max body size
- idempotency header requirements
- actor/request identity mapping
- admin auth behavior
- error mapping from `RegistryMutationError`
- failure audit behavior
- response shape
- whether the endpoint accepts raw registry JSON or a wrapper object
- whether snapshot export/publish remains separate

### Still Not Allowed

Do not implement:

- public CRUD registry APIs
- provider self-onboarding APIs
- marketplace provider submission
- credential vault writes
- plaintext key storage
- billing or settlement state
- automatic snapshot publish/reload

## Residual Risks

### Failure Audit Timing

Failure audit is best effort and should not obscure original errors. A service endpoint design should make failure audit timing explicit, especially around transaction rollback.

### Request Identity

CLI uses flags for actor/request/idempotency metadata. A service endpoint must derive these from headers and admin identity consistently.

### Large Registry Payloads

Import/replace accepts full registry documents. A service endpoint needs request size limits before implementation.

### Hosted Auth Strength

Current local admin token is enough for local service dogfood. It is not a full hosted auth model.

### Idempotency Key Enforcement

The CLI allows optional idempotency keys. A service endpoint should require an idempotency key.

## Next Task

Proceed to design only:

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

Expected output:

- endpoint contract
- request/response schema
- auth and idempotency rules
- error mapping
- audit mapping
- explicit non-goals

No endpoint implementation should happen before that design is accepted.

