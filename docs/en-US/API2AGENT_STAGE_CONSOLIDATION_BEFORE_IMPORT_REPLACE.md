# API2Agent Stage Consolidation Before Import/Replace v0

Date: 2026-05-31

Status: complete

## Decision

API2Agent can proceed to:

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```

But this next task must start from a consolidated phase boundary, not from a blank design surface.

The goal of this review is to harden the handoff from Tooling Re-entry back into Go Control Plane write-side design.

## Current Stage

The project has three stable local foundations:

1. API-first Tooling Layer
2. Go Data Plane local production primitive
3. Go Control Plane persistent registry read/audit primitive

These are enough to design the first controlled persistent registry mutation path.

They are not a signal to expand into hosted product, marketplace, billing, vault, workflow runtime, or granular provider onboarding APIs.

## Consolidated State

### Tooling Layer

Status: stable enough to pause.

Evidence:

- curl and OpenAPI onboarding paths are dogfooded.
- generated packages support direct and proxy execution.
- generated packages preserve provider region, credential intent, cost hints, and selected tool metadata.
- large OpenAPI specs now have parse-time filters, inspect summaries, and targeted test paths.
- write/delete testing is guarded by explicit opt-in.
- Python remains the Tooling reference implementation and local dogfood harness.

Hardening implication:

The next Control Plane write-side design must not require Tooling to become hosted-only, Go-only, or workflow-native.

### Go Data Plane

Status: local production primitive is stable enough to depend on snapshots.

Evidence:

- Protocol v0.2 execution graph records are emitted and validated.
- timeout budget, quota, credential config, snapshot freshness, snapshot reload, retry/failover, and attempt correlation semantics are dogfooded.
- event ingestion is durable JSONL with sequence recovery.
- snapshot reload keeps the previous snapshot active on failure.

Hardening implication:

The next registry mutation path must preserve snapshot compatibility, deterministic registry fingerprints, strict metadata, content digest validation, and reload-safe failure behavior.

### Go Control Plane

Status: persistent read/audit primitive is stable; write-side registry mutation is not implemented yet.

Evidence:

- file-backed registry store remains the default.
- PostgresStore load parity is implemented through the existing Store interface.
- live Postgres dogfood with podman proves schema apply, seed import, snapshot parity, CLI export, service validation, and service export.
- persistent audit writes exist for registry revisions, artifact publications, and admin audit events.
- persistent store failure semantics are fail-closed and machine-readable.
- mutation boundary review rejects granular CRUD and recommends full-registry import/replace.

Hardening implication:

The next task must design one controlled full-registry replacement transaction before any public write API exists.

## Entry Gate for Import/Replace Design

The next design must explicitly define:

- input registry document shape
- parse and schema validation order
- canonicalization rules
- full registry graph validation
- registry fingerprint computation
- idempotent no-op behavior
- transaction isolation
- registry-wide mutation lock
- replacement strategy for mutable registry tables
- same-transaction `registry_revisions` write
- same-transaction success `admin_audit_events` write
- best-effort failure audit behavior
- rollback semantics
- stable machine-readable error taxonomy

## Invariants

These must not regress:

- `FileStore` remains the default runtime store.
- Postgres remains explicit opt-in through runtime selection.
- registry tables store credential metadata only, never secret material.
- snapshots remain the Data Plane handoff unit.
- Data Plane does not read mutable Control Plane tables directly.
- full registry validation happens before publishable snapshot export.
- generated packages remain API-first.
- Python tooling remains a reference implementation, not the production Data Plane.
- no workflow engine is introduced.
- no marketplace, billing, settlement, or credential vault is introduced.

## Risks to Watch

### Partial Registry Mutation

The import/replace path must not turn into individual row CRUD. Registry objects are coupled and must be validated as one graph.

### Hidden Snapshot Drift

Import/replace must produce deterministic fingerprints and export-compatible registry state. If file and persistent registries diverge semantically, Data Plane reload behavior becomes difficult to explain.

### Audit as Best Effort Only

Successful persistent mutations must require audit writes. Failure audits can be best effort only when preserving the original error matters.

### Credential Boundary Creep

Credential metadata can move through the registry. Secret values cannot. Vault design remains outside this phase.

### Product Scope Creep

This phase is not the moment to add marketplace provider onboarding, workflow adapters, billing, or hosted user/org product surfaces.

## Recommended Next Task

The recommended task from this review was completed:

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```

Current next task:

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

The completed design produced:

- a design document, not a runtime write API
- transaction and rollback rules
- idempotency and audit requirements
- failure taxonomy
- explicit non-goals

## Validation Baseline

Last known validation baseline:

```text
python -m pytest
169 passed

go test ./...   # services/data-plane
go test ./...   # services/control-plane
```

For this consolidation review, docs-only validation is sufficient after pointer updates.
