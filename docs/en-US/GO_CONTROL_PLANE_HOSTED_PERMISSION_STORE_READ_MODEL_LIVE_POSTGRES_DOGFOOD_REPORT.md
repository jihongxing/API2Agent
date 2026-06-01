# Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood Report v0

Date: 2026-06-02

Status: complete

## Summary

The hosted permission store read model now has live Postgres dogfood evidence.

This slice starts a real local Postgres container, applies the Control Plane schema, seeds the registry project plus hosted permission rows, and calls the internal Go read model against the real Postgres DSN. It does not wire the gateway runtime, persist permission decisions, add public CRUD, add OAuth/OIDC, add invitation/session lifecycle, deploy a production gateway, add marketplace/provider onboarding, write vault material, add billing, add workflow runtime, trigger automatic propagation, or let the Data Plane read mutable Control Plane tables.

## Implemented

Added a dedicated Go dogfood helper:

```text
services/control-plane/cmd/api2agent-hosted-permission-read-model-dogfood/main.go
```

Added a live Postgres dogfood harness:

```text
scripts/go_control_plane_hosted_permission_read_model_dogfood.py
```

The Python harness:

- starts a local Postgres 16 container with Podman.
- applies `services/control-plane/schema/postgres/001_persistent_registry_store.sql`.
- seeds the harness project through `seed-postgres`.
- inserts hosted subjects, project memberships, roles, role bindings, grants, and active policy version rows.
- runs the Go helper against the real Postgres DSN.
- writes a redacted JSON artifact.

The Go helper:

- opens the real Postgres DSN with pgx.
- calls `registry.NewHostedPermissionReadModel(db).Resolve`.
- proves allowed and fail-closed cases against real SQL.
- asserts secret-safe decision evidence.
- asserts `hosted_permission_decisions` remains empty for v0.

## Dogfood Artifact

Artifact:

```text
.dogfood/go-control-plane-hosted-permission-read-model-live-postgres/report.json
```

Observed:

- `status=passed`
- `hosted_subjects=5`
- `hosted_project_memberships=4`
- `hosted_roles=4`
- `hosted_role_bindings=6`
- `hosted_permission_grants=9`
- `hosted_policy_versions=1` before ambiguous-policy case
- `hosted_policy_versions=2` after ambiguous-policy case
- `hosted_permission_decisions=0`
- `secret_safe_evidence=true`

## Cases Proven

| Case | Result |
| --- | --- |
| admin allowed import/replace | `200`, allowed |
| readonly missing import/replace permission | `403 PUBLIC_AUTHZ_DENIED` |
| missing membership | `403 PUBLIC_AUTHZ_DENIED` |
| suspended membership | `403 PUBLIC_AUTHZ_DENIED` |
| revoked grant | `403 PUBLIC_AUTHZ_DENIED` |
| no active policy | `503 PERMISSION_SOURCE_UNAVAILABLE` |
| ambiguous active policy | `503 PERMISSION_SOURCE_UNAVAILABLE` |

## Evidence Shape

The allowed decision included:

- subject id
- actor id
- project id
- organization id
- token id
- roles
- permissions
- required permission
- policy source
- policy version
- policy fingerprint
- decision id
- resolved time

Denied decisions preserved typed status/error evidence and fail-closed deny reasons.

## Secret-Safe Evidence

The artifact redacts:

- Postgres password
- public bearer tokens
- gateway secret

The Go helper also rejects decision evidence containing raw public token, gateway secret, OAuth token, refresh token, or plaintext markers.

## Validation

Passed:

```text
gofmt -w services/control-plane/cmd/api2agent-hosted-permission-read-model-dogfood/main.go
go test ./cmd/api2agent-hosted-permission-read-model-dogfood ./internal/registry -run HostedPermission
python -m py_compile scripts/go_control_plane_hosted_permission_read_model_dogfood.py
python scripts/go_control_plane_hosted_permission_read_model_dogfood.py --output .dogfood/go-control-plane-hosted-permission-read-model-live-postgres/report.json
```

## Non-Goals Preserved

No gateway runtime wiring, public user/project/role CRUD, OAuth/OIDC integration, invitation/login/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic snapshot publish/reload, decision persistence, or Data Plane mutable table read was added.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood Closeout + Phase Review v0
```
