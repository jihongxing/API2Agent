# API2Agent Control Plane

This is the minimum Go Control Plane for API2Agent Phase 6.

Build:

```bash
go test ./...
```

Registry source:

- `registry.Store` is the Control Plane state boundary.
- `registry.FileStore` is the current local implementation.
- Future hosted phases can add a Postgres-backed store without changing snapshot export semantics.

Export a routing snapshot:

```bash
go run ./cmd/api2agent-controlplane export-snapshot \
  --registry testdata/registry/network.public_ip.get.json \
  --output snapshot.json
```

The exported snapshot is compatible with the existing Go Data Plane snapshot loader.

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
