# Go Control Plane Hosted Admin Identity Boundary Implementation Report v0

日期：2026-05-31

状态：complete

## Summary

已经为现有 private Go Control Plane admin endpoints 实现 hosted-ready admin identity boundary。

本实现保持 local/private bearer-token 行为兼容，同时引入 resolved admin principal、endpoint permission checks、hosted authenticator seam、audit identity mapping，以及 principal-derived idempotency scope。

它不增加 public CRUD、hosted login、OAuth/OIDC verification、trusted gateway deployment、vault、billing、marketplace、workflow runtime、provider onboarding 或 automatic snapshot propagation。

## What Changed

- 增加 `registry.AdminPrincipal`。
- 为现有 admin endpoints 增加稳定 permission constants。
- 增加 `httpapi.AdminAuthenticator`：

```go
type AdminAuthenticator interface {
    ResolveAdminPrincipal(r *http.Request, requiredPermission string) (registry.AdminPrincipal, error)
}
```

- 增加显式 admin identity modes：
  - `local_private`
  - `hosted`
- 保持 local/private compatibility：
  - 仍然要求 `Authorization: Bearer <admin-token>`。
  - `X-Actor-ID` 只在 local/private mode 被接受。
  - 空白 `X-Actor-ID` 默认是 `admin`。
  - local/private project scope 是 `control_plane`。
  - local/private auth method 是 `local_admin_token`。
- 增加 hosted-ready fail-closed 行为：
  - hosted mode 没有 authenticator 时返回 `503 AUTH_SERVICE_UNAVAILABLE`。
  - 缺少 permission 时返回 `403 AUTHZ_DENIED`。
  - malformed hosted identity 可以返回 `401 AUTH_ERROR`。
- admin audit writes 改为使用 `principal.ActorID`，不再硬编码 `admin`。
- 增加 audit metadata：
  - `principal_subject_id`
  - `project_id`
  - `organization_id`
  - `auth_method`
  - `token_id`
  - `local_private`
- HTTP import/replace 改为把 principal-derived `ProjectID` 和 `ActorID` 传入 `registry.ImportReplaceOptions`。
- 为 service entry point 增加 `--admin-identity-mode` / `API2AGENT_CONTROL_PLANE_ADMIN_IDENTITY_MODE` wiring。

## Endpoint Permissions

| Endpoint | Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |

## Security Semantics

Hosted mode 不会从 public `X-Actor-ID`、`X-Project-ID` 或 `X-Organization-ID` headers 推导 actor/project identity。

v0 的 hosted identity source 只有注入的 `AdminAuthenticator` seam。这个 seam 现在可测试，并为之后的 hosted verifier 或 trusted gateway integration 留出位置。

## Tests Added

- local/private audit 仍走 bearer-token identity path，并记录 project/auth metadata
- local/private import/replace 仍接受 `X-Actor-ID`，project 映射为 `control_plane`
- hosted import/replace 会忽略 caller-controlled `X-Actor-ID`，使用 resolved principal actor/project
- hosted permission denial 在 mutation 前返回 `403 AUTHZ_DENIED`
- hosted mode 没有 authenticator 时返回 `503 AUTH_SERVICE_UNAVAILABLE`
- malformed hosted identity 返回 `401 AUTH_ERROR`
- hosted audit actor 和 metadata 来自 resolved principal

## Validation

已通过：

```text
go test ./...
```

目录：

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Hosted Admin Identity Boundary Closeout + Phase Review v0
```

closeout 应确认 local/private compatibility、hosted trust boundaries 和剩余 gaps，再继续增加更多 admin write surfaces。
