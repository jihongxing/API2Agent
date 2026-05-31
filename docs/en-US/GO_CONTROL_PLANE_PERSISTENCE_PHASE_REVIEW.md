# Go Control Plane Persistence Phase Review

Date: 2026-05-31

Status: complete

Decision: API2Agent is ready to plan the first runtime persistence implementation slice, but it is not yet ready for hosted public persistence, registry mutation APIs, vault, billing, or marketplace work.

## 1. Review Scope

This review closes the local Control Plane persistence planning checkpoint:

```text
Control Plane service boundary
  -> persistent registry design
  -> persistent schema/load-parity contract
  -> runtime persistence readiness decision
```

This review does not implement `PostgresStore.Load(ctx)`.

## 2. Completed Primitives

The project now has:

- Go Data Plane local execution and observability primitive
- Protocol v0.2 execution graph conformance checks
- durable local event ingestion
- retry/failover, timeout budget, snapshot freshness, quota, and credential config gates
- Go Control Plane local registry model
- `registry.Store` read boundary
- `registry.FileStore` as the current default store
- snapshot export with version policy and registry fingerprint
- snapshot artifact manifest and digest validation
- local snapshot distribution and atomic publish
- local Control Plane service API with admin auth guard
- persistent registry store design
- Postgres schema draft for persistent registry state
- file registry to persistent row mapping
- canonical registry ordering helper and regression tests

## 3. Code Boundary Evidence

Current code confirms the intended boundary:

- `services/control-plane/internal/registry/store.go` defines only the read-side `Store` interface.
- `FileStore` remains the runtime implementation.
- `services/control-plane/internal/registry/persistent_schema.go` maps registry data into persistent row shapes but does not open a database connection.
- `services/control-plane/schema/postgres/001_persistent_registry_store.sql` defines the first schema draft without wiring it into the service.

This means the project has intentionally stopped at schema/load-parity, not runtime persistence.

## 4. Requirements Review

Confirmed active requirements:

- API2Agent remains API-first.
- Marketplace remains far-term and out of active implementation scope.
- Runtime persistence must preserve the Data Plane snapshot contract.
- `FileStore` remains the default until a Postgres-backed store proves load/export parity.
- Credential secrets must stay out of registry tables.
- Receipt/trust and Edge-Mesh privacy strategy remain future constraints, not current runtime scope.

No new implementation requirement was accepted in this review that would bypass runtime persistence readiness.

## 5. Ready

The project is ready for a narrow `PostgresStore.Load(ctx)` planning/implementation slice because:

- schema shape exists
- deterministic canonical mapping exists
- registry validation already runs on loaded registries
- snapshot export callers depend on `registry.Store`, not `FileStore`
- service API already accepts a `registry.Store`
- schema/load-parity tests pass against the existing fixture

## 6. Not Ready

The project is not ready for broader hosted persistence because these are still missing:

- live Postgres-backed `Store` implementation
- migration runner
- database-backed import fixture or seed command
- transaction-level load tests
- dual-store snapshot parity test against a real database
- persisted `registry_revisions` writes during artifact export
- persisted `snapshot_artifact_publications` writes during publish
- persisted `admin_audit_events`
- per-project hosted authorization
- KMS-backed credential vault
- registry mutation HTTP APIs
- remote artifact storage compare-and-swap protocol

## 7. Readiness Decision

The next engineering task should be:

```text
Go Control Plane PostgresStore Load Parity v0
```

This should be the smallest runtime persistence slice.

## 8. Recommended Next Slice

Scope:

1. Add a Postgres-backed `registry.Store` implementation behind the existing read interface.
2. Keep `FileStore` as the default runtime store.
3. Add a local database test fixture or test container strategy if available in the project environment.
4. Import the existing `network.public_ip.get` registry fixture into the persistent schema.
5. Load the registry from Postgres and build the same in-memory `Registry` shape.
6. Verify `FileStore` and `PostgresStore` produce equivalent snapshots and registry fingerprints after canonicalization.

Exit criteria:

- `PostgresStore.Load(ctx)` can read a valid active registry view.
- The existing fixture can be represented in the persistent schema.
- File and Postgres paths produce equivalent snapshot contract output.
- `FileStore` remains default.
- No registry mutation API, hosted deployment, vault, billing, or marketplace work is included.

## 9. Strategic Judgment

The Control Plane has crossed from local file/service mechanics into durable state readiness.

The next important question is no longer:

```text
Can the Control Plane define a persistent registry schema?
```

That has been proven.

The next question is:

```text
Can the Control Plane load durable registry state without changing the Data Plane contract?
```

That is the correct next engineering slice.
