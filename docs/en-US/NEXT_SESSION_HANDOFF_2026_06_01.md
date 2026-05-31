# Next Session Handoff - 2026-06-01

Prepared on: 2026-05-31

## Current State

The current milestone is closed:

```text
Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0
```

The project has proven this local production-shaped chain:

```text
private admin HTTP import/replace
  -> persistent Postgres registry replacement
  -> snapshot artifact export
  -> distribution publish
  -> manual Data Plane reload
  -> Data Plane execution with replaced provider
```

Key closeout references:

- `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`
- `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/en-US/ROADMAP.md`
- `docs/en-US/IMPLEMENTATION_PLAN.md`

## Tomorrow's First Task

Start with:

```text
Go Control Plane Admin Mutation Idempotency Store Design v0
```

This is a design task first. Do not implement before the design is accepted.

## Why This Is Next

The private admin import/replace endpoint already requires `Idempotency-Key`, but the system does not persist idempotency records yet.

The current fingerprint no-op behavior is enough for local dogfood, but hosted/private admin mutations need explicit semantics for:

- same key + same request replay
- same key + different request conflict
- client timeout after server success
- response replay
- audit linkage
- retention and cleanup

## Suggested First Reading

Read these files before designing:

- `services/control-plane/internal/httpapi/service.go`
- `services/control-plane/internal/httpapi/service_test.go`
- `services/control-plane/internal/registry/postgres_import_replace.go`
- `services/control-plane/internal/registry/postgres_audit.go`
- `services/control-plane/schema/postgres/001_persistent_registry_store.sql`
- `docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`
- `docs/en-US/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`

## Design Scope

The design should define:

- persistent idempotency record schema
- key scope: actor/project/operation/key
- request fingerprint semantics
- response replay semantics
- conflict behavior for same key with a different request
- transaction boundary with `ReplacePersistentRegistry`
- linkage to registry revision and admin audit event evidence
- expiration/retention policy
- failure semantics
- tests required for the later implementation slice

## Do Not Start

Do not start:

- public registry CRUD APIs
- provider self-onboarding
- marketplace provider submission
- credential vault writes
- plaintext secret storage
- billing or settlement state
- workflow engine support
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables

## Validation Baseline

The latest completed validation before handoff:

```text
python scripts/go_control_plane_import_replace_snapshot_propagation_dogfood.py --output tmp/go_control_plane_import_replace_snapshot_propagation_dogfood.json
go test ./...
```

Go test directories:

```text
services/control-plane
services/data-plane
```

## Suggested Tomorrow Flow

1. Re-read the closeout doc.
2. Inspect the current import/replace endpoint and Postgres mutation code.
3. Draft `Go Control Plane Admin Mutation Idempotency Store Design v0`.
4. Update roadmap and implementation plan only after the design is written.
5. Wait for design acceptance before implementation.
