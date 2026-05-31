# Go Control Plane Hosted Admin Gateway Contract Harness Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Hosted admin gateway contract harness 已作为 dogfood-only local tooling 实现。

Dogfood 现在证明了完整请求边界：

```text
public dogfood request
  -> local gateway harness
  -> strip caller-supplied trusted headers
  -> inject static trusted claims
  -> authenticate to Control Plane with a gateway secret
  -> private Control Plane admin endpoint
```

本 slice 未增加 OAuth/OIDC、public registry CRUD、provider onboarding、marketplace、vault、billing、workflow runtime、automatic snapshot propagation，或 Data Plane 从 mutable Control Plane tables 读取。

## Script

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
```

命令：

```text
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output tmp/go_control_plane_hosted_admin_gateway_contract_dogfood.json
```

## 实现

脚本会启动：

```text
podman Postgres
  -> apply persistent registry schema
  -> seed-postgres from file registry
  -> build api2agent-controlplane
  -> serve with hosted/trusted_gateway admin mode
  -> local ThreadingHTTPServer gateway harness
  -> public dogfood HTTP requests to the harness
  -> query Postgres evidence
```

Harness 会：

- forward `GET /healthz`
- forward `POST /v1/admin/registry/validate`
- forward `POST /v1/admin/registry/import-replace`
- 对 unsupported paths 本地返回 `404`
- 对 unsupported methods 本地返回 `405`
- 本地消费 public bearer auth
- 只保留 `Content-Type`、`X-Request-ID` 和 `Idempotency-Key`
- strip caller-supplied `X-API2Agent-*`、public `Authorization`、public identity headers、`Cookie` 和 `Proxy-Authorization`
- 注入 trusted gateway authorization、gateway key id、principal、actor、project、organization、token、roles 和 permissions

## 结果

观察到：

```json
{
  "status": "passed",
  "admin_token_flag_used": false,
  "unsupported_path_status": 404,
  "unsupported_method_status": 405,
  "missing_public_auth_status": 401,
  "audit_rows_before_missing_public_auth": 0,
  "audit_rows_after_missing_public_auth": 0,
  "validate_status": 200,
  "readonly_validate_status": 403,
  "readonly_import_status": 403,
  "import_status": 201,
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 2,
    "idempotency_records": 1,
    "providers": 1
  }
}
```

## Evidence

Audit rows 使用 harness-injected identity：

```json
{
  "actor_id": "gateway-harness-actor",
  "principal_subject_id": "gateway-harness-principal",
  "project_id": "gateway-harness-project",
  "organization_id": "gateway-harness-org",
  "auth_method": "trusted_gateway",
  "token_id": "gateway-harness-token-admin",
  "gateway_key_id": "dogfood-gateway-key-contract",
  "local_private": "false",
  "metadata_contains_spoofed_identity": false,
  "metadata_contains_gateway_secret": false,
  "metadata_contains_public_token": false
}
```

Import/replace idempotency record 使用 harness-injected project 和 actor scope：

```json
{
  "project_id": "gateway-harness-project",
  "actor_id": "gateway-harness-actor",
  "operation": "registry.import_replace",
  "first_request_id": "dogfood-gateway-contract-import-1",
  "status": "succeeded",
  "response_status_code": 201,
  "has_registry_revision": true,
  "has_admin_audit_event": true,
  "noop": false,
  "row_contains_gateway_secret": false,
  "row_contains_public_token": false
}
```

## 断言

已通过：

- 通过 harness 调用 `/healthz` 返回 `200`
- valid public admin auth 加 spoofed trusted headers 调用 registry validation 返回 `200`
- audit metadata 使用 harness-injected identity，而不是 spoofed caller headers
- caller-supplied gateway authorization 被 strip 并替换
- missing public auth 返回 gateway-local `401`，且没有创建 Control Plane audit rows
- readonly public auth 调用 validate 和 import/replace 返回 `403 AUTHZ_DENIED`
- full admin public auth import/replace 返回 `201`
- import/replace idempotency evidence 使用 harness-injected project 和 actor
- audit metadata 包含 harness gateway key id
- raw public bearer tokens 和 raw gateway secret 未出现在 audit/idempotency evidence 或 dogfood report artifact 中

## Validation

已通过：

```text
python -m py_compile scripts\go_control_plane_hosted_admin_gateway_contract_dogfood.py
```

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
python scripts\go_control_plane_hosted_admin_gateway_contract_dogfood.py --output tmp\go_control_plane_hosted_admin_gateway_contract_dogfood.json
```

## 推荐下一项任务

```text
Go Control Plane Hosted Admin Gateway Contract Harness Closeout + Phase Review v0
```

Closeout 应判断 local gateway contract proof 是否足以暂停，然后再决定是否进入真实 hosted public gateway 或 permission-source integration 设计。
