# Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0

Date: 2026-05-31

Status: complete

## Decision

The private admin import/replace endpoint passed live Postgres dogfood.

Recommended next task:

```text
Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0
```

## Scope

This dogfood verified the real service path:

```text
HTTP admin endpoint
  -> Go Control Plane service
  -> registry.ReplacePersistentRegistry
  -> live Postgres persistent registry tables
  -> validation/export after replacement
  -> persistent audit evidence
```

It did not test public CRUD, provider onboarding, credential vault, billing, marketplace, or automatic snapshot reload.

## Environment

- Postgres-compatible database started with `podman`
- schema applied from `services/control-plane/schema/postgres/001_persistent_registry_store.sql`
- service started with `--registry-store postgres`
- admin auth used `Authorization: Bearer dogfood-token`
- endpoint under test:

```text
POST /v1/admin/registry/import-replace
```

## Dogfood Steps

1. Start live Postgres with podman.
2. Apply persistent registry schema.
3. Seed the baseline `network.public_ip.get` registry.
4. Build and start the Go Control Plane service against Postgres.
5. Call `POST /v1/admin/registry/import-replace` with a changed registry.
6. Call the same endpoint again with the same registry to verify no-op behavior.
7. Call service registry validation after replacement.
8. Export a snapshot artifact through the service after replacement.
9. Verify the exported snapshot contains the replaced provider.
10. Assert persistent audit counts.

## Observed Result

```json
{
  "status": "passed",
  "replace_status": 201,
  "replace_noop": false,
  "noop_status": 200,
  "second_noop": true,
  "snapshot_version": "snapshot_http_import_replace_live_v1",
  "provider_id": "httpbin_public_ip_v1",
  "provider_base_url": "https://httpbin.org",
  "audit_counts": {
    "registry_revisions": 3,
    "admin_audit_events": 4,
    "providers": 1
  }
}
```

Registry fingerprint after replacement:

```text
sha256:3aa1851fde7accf093721be5a10f43229d54894625962c364fbd603a880a5cf5
```

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| Live Postgres service starts with Postgres registry store | passed |
| Endpoint accepts changed registry through HTTP | passed |
| Changed registry returns `201` | passed |
| Changed registry returns `noop=false` | passed |
| Repeated same registry returns `200` | passed |
| Repeated same registry returns `noop=true` | passed |
| Service validation sees replaced registry | passed |
| Service export sees replaced registry | passed |
| Exported snapshot provider is `httpbin_public_ip_v1` | passed |
| Persistent registry revisions are asserted | passed |
| Persistent admin audit events are asserted | passed |
| No public CRUD API is introduced | passed |

## Audit Interpretation

Expected counts:

- `registry_revisions=3`
  - seed
  - successful import/replace
  - service export after replacement
- `admin_audit_events=4`
  - successful import/replace
  - successful import/replace no-op
  - registry validation
  - artifact export
- `providers=1`
  - full replacement leaves one active provider row

## Validation

Dogfood command:

```text
python scripts/go_control_plane_import_replace_endpoint_dogfood.py --output tmp/go_control_plane_import_replace_endpoint_dogfood.json
```

Unit tests:

```text
go test ./...
```

from:

```text
services/control-plane
```

## Non-Goals Preserved

- no public CRUD registry API
- no provider self-onboarding
- no marketplace
- no billing or settlement
- no credential vault
- no plaintext secret storage
- no workflow engine
- no automatic snapshot publish or Data Plane reload
- no Data Plane reads from mutable Control Plane tables

