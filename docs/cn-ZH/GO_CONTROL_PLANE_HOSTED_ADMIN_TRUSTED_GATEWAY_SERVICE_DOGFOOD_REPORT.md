# Go Control Plane Hosted Admin Trusted Gateway Service Dogfood 报告 v0

日期：2026-05-31

状态：complete

## 摘要

Hosted trusted-gateway admin dogfood 已在真实 `api2agent-controlplane serve` process 和 live podman-backed Postgres 上通过。

Service 在不传 `--admin-token` 的情况下用 hosted mode 启动，能用 trusted gateway claims 处理 admin requests；missing gateway auth 返回 `401 AUTH_ERROR`，missing permission 返回 `403 AUTHZ_DENIED`，并持久化 principal-derived audit/idempotency evidence。

## Script

```text
scripts/go_control_plane_hosted_admin_gateway_dogfood.py
```

命令：

```text
python scripts/go_control_plane_hosted_admin_gateway_dogfood.py --output tmp/go_control_plane_hosted_admin_gateway_dogfood.json
```

## Flow

```text
podman Postgres
  -> apply persistent registry schema
  -> seed-postgres from file registry
  -> build api2agent-controlplane
  -> serve with --admin-identity-mode hosted
  -> serve with --admin-authenticator trusted_gateway
  -> serve with --trusted-gateway-secret
  -> no --admin-token flag
  -> public GET /healthz
  -> trusted POST /v1/admin/registry/validate
  -> missing gateway auth POST /v1/admin/registry/validate
  -> missing permission POST /v1/admin/registry/validate
  -> trusted POST /v1/admin/registry/import-replace
  -> query audit and idempotency evidence
```

## 结果

观察到：

```json
{
  "status": "passed",
  "admin_token_flag_used": false,
  "validate_status": 200,
  "missing_gateway_auth_status": 401,
  "missing_gateway_auth_error_type": "AUTH_ERROR",
  "missing_permission_status": 403,
  "missing_permission_error_type": "AUTHZ_DENIED",
  "import_status": 201,
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 2,
    "idempotency_records": 1,
    "providers": 1
  }
}
```

## Principal Evidence

Dogfood 验证了 `registry.validate` 和 `registry.import_replace` audit rows 都使用 trusted gateway identity：

```json
{
  "actor_id": "hosted-admin-actor-dogfood",
  "principal_subject_id": "hosted-admin-subject-dogfood",
  "project_id": "hosted-project-dogfood",
  "organization_id": "hosted-org-dogfood",
  "auth_method": "trusted_gateway",
  "token_id": "gateway-token-dogfood",
  "local_private": "false",
  "metadata_contains_gateway_secret": false
}
```

Dogfood 也验证了 import/replace idempotency record 使用 trusted gateway claims 做 scope：

```json
{
  "project_id": "hosted-project-dogfood",
  "actor_id": "hosted-admin-actor-dogfood",
  "operation": "registry.import_replace",
  "first_request_id": "dogfood-hosted-gateway-import-1",
  "status": "succeeded",
  "response_status_code": 201,
  "has_registry_revision": true,
  "has_admin_audit_event": true,
  "noop": false
}
```

## Dogfood 发现并修复的问题

第一次 dogfood run 发现 HTTP import/replace path 只把 actor/project scope 传给 Postgres mutation layer。mutation audit row 因此缺少 hosted principal metadata，例如 subject、organization、auth method、token id 和 `local_private=false`。

这个 integration gap 已在本 slice 修复：

- `registry.ImportReplaceOptions` 现在携带 admin principal evidence fields。
- `ImportReplaceRegistry` 会把 resolved `AdminPrincipal` evidence 映射进 options。
- Postgres import/replace audit metadata 会在存在时记录 subject、project、organization、auth method、token id 和 local/private status。
- Regression tests 覆盖 hosted 和 trusted-gateway import/replace principal evidence propagation。

## 断言

已通过：

- service 在 hosted/trusted-gateway mode 下不需要 `--admin-token` 即可启动
- `/healthz` 保持 public
- trusted gateway validation 返回 `200`
- public `Authorization` 和 `X-Actor-ID` 不会覆盖 trusted gateway claims
- missing gateway authorization 返回 `401 AUTH_ERROR`
- missing endpoint permission 返回 `403 AUTHZ_DENIED`
- import/replace 返回 `201`
- audit rows 使用 trusted gateway actor 和 principal metadata
- audit metadata 不包含 gateway secret
- idempotency record 使用 trusted gateway project 和 actor scope
- idempotency record 链接到 registry revision 和 admin audit event
- 未增加 public CRUD、vault、billing、marketplace、workflow、provider onboarding 或 automatic propagation

## Validation

已通过：

```text
go test ./...
```

目录：

```text
services/control-plane
```

已通过：

```text
python -m py_compile scripts\go_control_plane_hosted_admin_gateway_dogfood.py
python scripts\go_control_plane_hosted_admin_gateway_dogfood.py --output tmp\go_control_plane_hosted_admin_gateway_dogfood.json
```

## 推荐下一项任务

```text
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Closeout + Phase Review v0
```

closeout 应判断 trusted-gateway hosted admin integration 是否可以暂停，再进入下一个 hosted Control Plane readiness gap。
