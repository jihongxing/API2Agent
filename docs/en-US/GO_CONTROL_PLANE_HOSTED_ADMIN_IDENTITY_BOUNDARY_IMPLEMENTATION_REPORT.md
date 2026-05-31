# Go Control Plane Hosted Admin Identity Boundary Implementation Report v0

Date: 2026-05-31

Status: complete

## Summary

Implemented the hosted-ready admin identity boundary for the existing private Go Control Plane admin endpoints.

This implementation keeps local/private bearer-token behavior compatible while introducing a resolved admin principal, endpoint permission checks, hosted authenticator seam, audit identity mapping, and principal-derived idempotency scope.

It does not add public CRUD, hosted login, OAuth/OIDC verification, trusted gateway deployment, vault, billing, marketplace, workflow runtime, provider onboarding, or automatic snapshot propagation.

## What Changed

- Added `registry.AdminPrincipal`.
- Added stable permission constants for the existing admin endpoints.
- Added `httpapi.AdminAuthenticator`:

```go
type AdminAuthenticator interface {
    ResolveAdminPrincipal(r *http.Request, requiredPermission string) (registry.AdminPrincipal, error)
}
```

- Added explicit admin identity modes:
  - `local_private`
  - `hosted`
- Preserved local/private compatibility:
  - `Authorization: Bearer <admin-token>` is still required.
  - `X-Actor-ID` is still accepted only by local/private mode.
  - blank `X-Actor-ID` defaults to `admin`.
  - local/private project scope is `control_plane`.
  - local/private auth method is `local_admin_token`.
- Added hosted-ready fail-closed behavior:
  - hosted mode without an authenticator returns `503 AUTH_SERVICE_UNAVAILABLE`.
  - missing permission returns `403 AUTHZ_DENIED`.
  - malformed hosted identity can return `401 AUTH_ERROR`.
- Changed admin audit writes to use `principal.ActorID` instead of hard-coded `admin`.
- Added audit metadata for:
  - `principal_subject_id`
  - `project_id`
  - `organization_id`
  - `auth_method`
  - `token_id`
  - `local_private`
- Changed HTTP import/replace to pass principal-derived `ProjectID` and `ActorID` into `registry.ImportReplaceOptions`.
- Added `--admin-identity-mode` / `API2AGENT_CONTROL_PLANE_ADMIN_IDENTITY_MODE` wiring for the service entry point.

## Endpoint Permissions

| Endpoint | Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |

## Security Semantics

Hosted mode does not derive actor or project identity from public `X-Actor-ID`, `X-Project-ID`, or `X-Organization-ID` headers.

The only hosted identity source in v0 is the injected `AdminAuthenticator` seam. That seam is intentionally testable now and ready for a later hosted verifier or trusted gateway integration.

## Tests Added

- local/private audit still uses the bearer-token identity path and records project/auth metadata
- local/private import/replace still accepts `X-Actor-ID` and maps project to `control_plane`
- hosted import/replace ignores caller-controlled `X-Actor-ID` and uses resolved principal actor/project
- hosted permission denial returns `403 AUTHZ_DENIED` before mutation
- hosted mode without an authenticator returns `503 AUTH_SERVICE_UNAVAILABLE`
- malformed hosted identity returns `401 AUTH_ERROR`
- hosted audit actor and metadata come from the resolved principal

## Validation

Passed:

```text
go test ./...
```

Directory:

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Hosted Admin Identity Boundary Closeout + Phase Review v0
```

The closeout should confirm local/private compatibility, hosted trust boundaries, and remaining gaps before adding more admin write surfaces.
