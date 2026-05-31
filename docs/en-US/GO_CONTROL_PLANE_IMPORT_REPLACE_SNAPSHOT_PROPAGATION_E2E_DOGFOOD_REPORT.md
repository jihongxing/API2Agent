# Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0

Date: 2026-05-31

Status: complete

## Decision

The import/replace snapshot propagation E2E dogfood passed.

Recommended next task:

```text
Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0
```

## Scope

This dogfood verified the full manual propagation sequence:

```text
HTTP import/replace
  -> snapshot artifact export
  -> distribution publish
  -> Data Plane reload
  -> Data Plane execution uses replaced provider
```

This is still an operator-sequenced dogfood. It does not introduce automatic publish, automatic reload, public CRUD, provider onboarding, credential vault, billing, marketplace, or workflow runtime scope.

## Environment

- Postgres-compatible database started with `podman`
- schema applied from `services/control-plane/schema/postgres/001_persistent_registry_store.sql`
- Control Plane service started with `--registry-store postgres`
- Data Plane started with `API2AGENT_SNAPSHOT=<distribution_dir>`
- Data Plane reload policy set to `API2AGENT_SNAPSHOT_RELOAD_POLICY=manual`
- replacement provider used a local httpbin-like server returning `{"origin": "203.0.113.88"}`

## Dogfood Steps

1. Start live Postgres with podman.
2. Apply persistent registry schema.
3. Seed the initial `network.public_ip.get` registry with `ipify_public_ip_v1`.
4. Start the Go Control Plane service against Postgres.
5. Export and publish the initial snapshot distribution.
6. Start the Go Data Plane from the distribution directory.
7. Verify Data Plane initially loads `snapshot_propagation_ipify_v1`.
8. Call `POST /v1/admin/registry/import-replace` with a replacement registry using `httpbin_public_ip_v1`.
9. Export and publish the replacement snapshot.
10. Call `POST /v1/admin/reload-snapshot` on the Data Plane.
11. Execute `network.public_ip.get` through the Data Plane.
12. Verify the execution output, usage event, decision log, reload event, and persistent audit counts.

## Observed Result

```json
{
  "status": "passed",
  "initial_published_snapshot_version": "snapshot_propagation_ipify_v1",
  "replacement_published_snapshot_version": "snapshot_propagation_httpbin_v2",
  "reload_response": {
    "previous_snapshot_version": "snapshot_propagation_ipify_v1",
    "reloaded": true,
    "snapshot_version": "snapshot_propagation_httpbin_v2"
  },
  "execute_response": {
    "output": {
      "ip": "203.0.113.88"
    },
    "success": true
  },
  "usage_provider_id": "httpbin",
  "usage_snapshot_version": "snapshot_propagation_httpbin_v2",
  "decision_selected_provider_id": "httpbin_public_ip_v1",
  "reload_event_count": 1,
  "audit_counts": {
    "registry_revisions": 4,
    "admin_audit_events": 5,
    "providers": 1,
    "snapshot_artifact_publications": 2
  }
}
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| HTTP import/replace changes the persistent registry provider | passed |
| Control Plane exports the replaced snapshot | passed |
| Control Plane publishes the replaced snapshot distribution | passed |
| Data Plane manually reloads the published distribution | passed |
| Data Plane execution uses the replaced provider | passed |
| Execution output comes from the replacement provider | passed |
| Usage event attributes the replaced provider | passed |
| Decision log selects `httpbin_public_ip_v1` | passed |
| Snapshot reload audit event is emitted | passed |
| Persistent audit counts are asserted | passed |
| Snapshot export/publish/reload remain manually sequenced | passed |
| No public CRUD, vault, billing, marketplace, or workflow scope is introduced | passed |

## Audit Interpretation

Expected persistent evidence:

- `registry_revisions=4`
  - initial seed
  - initial service export
  - successful import/replace
  - replacement service export
- `snapshot_artifact_publications=2`
  - initial distribution publish
  - replacement distribution publish
- `admin_audit_events=5`
  - initial artifact export
  - initial distribution publish
  - successful import/replace
  - replacement artifact export
  - replacement distribution publish
- `providers=1`
  - full replacement leaves one active provider row

Expected Data Plane evidence:

- `snapshot_reload_event`
- `request_context`
- `routing_decision`
- `usage_event`
- `decision_log`

## Validation

Dogfood command:

```text
python scripts/go_control_plane_import_replace_snapshot_propagation_dogfood.py --output tmp/go_control_plane_import_replace_snapshot_propagation_dogfood.json
```

Dogfood status:

```text
passed
```

## Non-Goals Preserved

- no public CRUD registry API
- no provider self-onboarding
- no marketplace
- no billing or settlement
- no credential vault
- no plaintext secret storage
- no workflow engine
- no automatic snapshot publish
- no automatic Data Plane reload
- no Data Plane reads from mutable Control Plane tables
