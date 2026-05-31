# API2Agent Control Plane

This is the minimum Go Control Plane for API2Agent Phase 6.

Build:

```bash
go test ./...
```

Registry source:

- `registry.Store` is the Control Plane state boundary.
- `registry.FileStore` remains the default local implementation.
- `registry.PostgresStore` can be selected explicitly for read-side load parity.
- Postgres runtime wiring is experimental and should be dogfooded before it becomes a default path.

Export a routing snapshot:

```bash
go run ./cmd/api2agent-controlplane export-snapshot \
  --registry testdata/registry/network.public_ip.get.json \
  --output snapshot.json
```

To read from Postgres instead of a file registry, first apply the schema in `schema/postgres/001_persistent_registry_store.sql`, then seed the registry:

```bash
go run ./cmd/api2agent-controlplane seed-postgres \
  --registry testdata/registry/network.public_ip.get.json \
  --postgres-dsn "$API2AGENT_CONTROL_PLANE_POSTGRES_DSN"
```

Then select the store explicitly:

```bash
go run ./cmd/api2agent-controlplane export-snapshot \
  --registry-store postgres \
  --postgres-dsn "$API2AGENT_CONTROL_PLANE_POSTGRES_DSN" \
  --output snapshot.json
```

The exported snapshot is compatible with the existing Go Data Plane snapshot loader.

Replace the active persistent registry view from a validated registry document:

```bash
go run ./cmd/api2agent-controlplane import-replace-postgres \
  --registry testdata/registry/network.public_ip.get.json \
  --postgres-dsn "$API2AGENT_CONTROL_PLANE_POSTGRES_DSN" \
  --actor-id local-admin \
  --request-id local-import-replace
```

This command is a local/admin write path. It uses a serializable transaction, a registry-wide advisory lock, full mutable-table replacement, same-transaction revision/audit writes, and idempotent no-op behavior by registry fingerprint. It does not publish or reload snapshots.

Export a snapshot artifact:

```bash
go run ./cmd/api2agent-controlplane export-artifact \
  --registry testdata/registry/network.public_ip.get.json \
  --output-dir artifact
```

The artifact contains:

- `snapshot.json`
- `manifest.json`

The manifest records the artifact version, registry source, snapshot version policy, registry fingerprint, snapshot content digest, and validation summary.

Exported snapshots include `metadata.schema_version=api2agent.protocol.v0.2` so Data Plane can reject incompatible snapshots before startup or reload.
Artifact export and publish validate that `manifest.json` agrees with `snapshot.json` metadata and file content before distribution state is advanced.
Artifact file references must stay inside the artifact directory; absolute paths and `..` traversal are rejected.
Publish writes versioned artifacts through a temporary directory and rejects duplicate snapshot versions before advancing `current.json`.

Publish a snapshot artifact to a local distribution directory:

```bash
go run ./cmd/api2agent-controlplane publish-artifact \
  --artifact-dir artifact \
  --distribution-dir distribution
```

The distribution contains:

- `current.json`
- `artifacts/<snapshot_version>/snapshot.json`
- `artifacts/<snapshot_version>/manifest.json`

The Go Data Plane can load the distribution by setting `API2AGENT_SNAPSHOT` to the distribution directory.

Run the local Control Plane service:

```bash
go run ./cmd/api2agent-controlplane serve \
  --registry testdata/registry/network.public_ip.get.json \
  --admin-token local-dev-token \
  --distribution-dir distribution \
  --addr 127.0.0.1:8081
```

Postgres store selection for the service:

```bash
go run ./cmd/api2agent-controlplane serve \
  --registry-store postgres \
  --postgres-dsn "$API2AGENT_CONTROL_PLANE_POSTGRES_DSN" \
  --admin-token local-dev-token \
  --distribution-dir distribution \
  --addr 127.0.0.1:8081
```

When the service runs with `--registry-store postgres`, successful admin operations also write persistent audit rows:

- `POST /v1/admin/registry/validate` writes `admin_audit_events`.
- `POST /v1/admin/snapshots/export-artifact` writes `registry_revisions` and `admin_audit_events`.
- `POST /v1/admin/distribution/publish` writes `snapshot_artifact_publications` and `admin_audit_events`.
- `GET /v1/admin/distribution/current` writes `admin_audit_events`.

Successful operations fail closed with `AUDIT_WRITE_FAILED` if a required persistent audit write fails. File-store mode does not configure a persistent audit sink.

Persistent-store read failures are reported as platform-side retryable errors:

- `--registry-store postgres` load failures return `PERSISTENT_STORE_READ_FAILED` with HTTP 503.
- file-store load/validation failures continue to return `REGISTRY_INVALID` with HTTP 400.

Service endpoints:

- `GET /healthz` is public and reports service, protocol, registry source, and distribution metadata.
- `POST /v1/admin/registry/validate` validates the configured registry and returns a registry fingerprint.
- `POST /v1/admin/registry/import-replace` replaces the Postgres-backed registry graph from a full registry document.
- `POST /v1/admin/snapshots/export-artifact` writes a snapshot artifact to `output_dir`.
- `POST /v1/admin/distribution/publish` publishes an artifact directory to the configured local distribution.
- `GET /v1/admin/distribution/current` reads the configured distribution `current.json`.

By default, `/v1/admin/*` endpoints run in `local_private` identity mode and require `Authorization: Bearer <admin-token>`. Local/private mode maps `X-Actor-ID` to the audit/idempotency actor when present, defaults the actor to `admin`, and scopes mutations to project `control_plane`.

The HTTP layer now resolves admin requests into `registry.AdminPrincipal` before running endpoint logic. Hosted mode is fail-closed unless an `AdminAuthenticator` is injected by the embedding service; caller-supplied identity headers such as `X-Actor-ID` are not trusted in hosted mode.

Trusted gateway hosted mode can be enabled with `--admin-identity-mode hosted --admin-authenticator trusted_gateway --trusted-gateway-secret <secret>` or rotation-compatible `--trusted-gateway-secrets <old,new>`. In that mode, the service validates `X-API2Agent-Gateway-Authorization: Bearer <secret>` before reading trusted `X-API2Agent-*` principal, project, role, permission, and optional gateway key-id claims.

Hosted/trusted-gateway mode has been dogfooded against a real service process and live Postgres without `--admin-token`.

Private admin import/replace endpoint:

- It is Postgres mutation only and reuses `ReplacePersistentRegistry`.
- It requires `X-Request-ID` and `Idempotency-Key`.
- It persists scoped idempotency records for committed mutations.
- Same-key same-request replay returns the cached response without a second mutation.
- Same-key different-request reuse returns `409 IDEMPOTENCY_KEY_CONFLICT`.
- It accepts a wrapper request body with `registry`, optional `source`, and reserved `dry_run=false`.
- It does not export, publish, or reload snapshots.

See `../../docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`.
Implementation report: `../../docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_IMPLEMENTATION_REPORT.md`.
Live dogfood report: `../../docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_LIVE_POSTGRES_DOGFOOD_REPORT.md`.
Closeout review: `../../docs/en-US/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_CLOSEOUT_PHASE_REVIEW.md`.
Idempotency design: `../../docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_DESIGN.md`.
Idempotency implementation report: `../../docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_IMPLEMENTATION_REPORT.md`.
Idempotency live dogfood report: `../../docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_LIVE_POSTGRES_DOGFOOD_REPORT.md`.
Idempotency closeout review: `../../docs/en-US/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_CLOSEOUT_PHASE_REVIEW.md`.
Hosted admin identity design: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_DESIGN.md`.
Hosted admin identity implementation report: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_IMPLEMENTATION_REPORT.md`.
Hosted admin identity closeout review: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`.
Hosted admin authenticator integration design: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_DESIGN.md`.
Hosted admin authenticator integration implementation report: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_IMPLEMENTATION_REPORT.md`.
Hosted admin authenticator integration closeout review: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_CLOSEOUT_PHASE_REVIEW.md`.
Hosted admin trusted gateway service dogfood report: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`.
Hosted admin trusted gateway service dogfood closeout review: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_CLOSEOUT_PHASE_REVIEW.md`.
Hosted admin trusted gateway production boundary design: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_DESIGN.md`.
Hosted admin trusted gateway production boundary implementation report: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`.
Hosted admin trusted gateway production boundary closeout review: `../../docs/en-US/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`.
