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

Health endpoint:

```http
GET http://127.0.0.1:8080/healthz
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
- `API2AGENT_PROJECT_QUOTA`
- `API2AGENT_CREDENTIAL_CONFIG`

Dogfood:

```bash
python ../../scripts/go_dataplane_failover_dogfood.py
python ../../scripts/go_dataplane_credential_dogfood.py
python ../../scripts/go_dataplane_timeout_budget_dogfood.py
python ../../scripts/go_dataplane_snapshot_freshness_dogfood.py
python ../../scripts/go_dataplane_project_quota_dogfood.py
python ../../scripts/go_dataplane_credential_config_dogfood.py
```
