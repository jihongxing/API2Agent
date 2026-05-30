# API2Agent Data Plane

This is the first Go skeleton for the API2Agent production data plane.

Run tests:

```bash
go test ./...
```

Run locally:

```bash
go run ./cmd/api2agent-dataplane
```

Default endpoint:

```http
POST http://127.0.0.1:8080/v1/execute
```

Example request:

```json
{
  "project_id": "local",
  "capability_id": "network.public_ip.get",
  "capability_version": "0.1-migrated",
  "input": {},
  "execution_mode": "proxy",
  "timeout_budget_ms": 5000
}
```

Environment variables:

- `API2AGENT_DATAPLANE_ADDR`
- `API2AGENT_SNAPSHOT`
- `API2AGENT_EVENT_DIR`
- `API2AGENT_PROJECT_KEY`
