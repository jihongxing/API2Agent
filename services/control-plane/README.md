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
