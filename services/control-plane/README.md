# API2Agent Control Plane

This is the minimum Go Control Plane for API2Agent Phase 6.

Build:

```bash
go test ./...
```

Export a routing snapshot:

```bash
go run ./cmd/api2agent-controlplane export-snapshot \
  --registry testdata/registry/network.public_ip.get.json \
  --output snapshot.json
```

The exported snapshot is compatible with the existing Go Data Plane snapshot loader.
