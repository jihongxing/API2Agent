# Go Control Plane Hosted Admin Trusted Gateway Production Boundary Implementation 报告 v0

日期：2026-05-31

状态：complete

## 摘要

Go Control Plane 已实现 hosted trusted-gateway admin path 的 production boundary support。

该实现保持 legacy single-secret configuration 兼容，同时增加 rotation-compatible active secret set 和 optional non-secret gateway key-id evidence。

## 已实现

### Rotation-Compatible Gateway Secrets

新增：

- `--trusted-gateway-secrets`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRETS`
- `Handler.TrustedGatewaySecrets`
- `TrustedGatewayAuthenticator.GatewaySecrets`

行为：

- comma-separated active secrets 会 trim 并 de-duplicate
- legacy `--trusted-gateway-secret` / `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET` 继续支持
- hosted/trusted-gateway mode 没有 active secret 时 fail closed
- rotation overlap 期间任一 active secret 都能认证
- 已移除 secret 会返回 `401 AUTH_ERROR`

### Gateway Key-ID Evidence

新增：

- `--trusted-gateway-key-id`
- `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_KEY_ID`
- `X-API2Agent-Gateway-Key-ID`
- `registry.AdminPrincipal.GatewayKeyID`
- `registry.ImportReplaceOptions.GatewayKeyID`

行为：

- gateway auth 通过后，request header key id 会作为 optional trusted claim 解析
- request header 缺失时使用 configured key id
- key id 只是 non-secret evidence
- audit metadata 在存在时包含 `gateway_key_id`
- import/replace Postgres audit metadata 在存在时包含 `gateway_key_id`
- gateway secrets 不写入 audit/idempotency metadata

### Secret-Safe Matching

Authenticator 会将 presented gateway bearer token 与所有 active secrets 比较，比较方式是 fixed hashes 上的 per-candidate constant-time comparison。

## Dogfood

已更新：

```text
scripts/go_control_plane_hosted_admin_gateway_dogfood.py
```

Live dogfood 现在验证：

- hosted/trusted-gateway service 不传 `--admin-token` 即可启动
- overlap 期间 old/new active secrets 都可用
- service 仅用 new secret 重启
- 已移除 old secret 返回 `401 AUTH_ERROR`
- new secret 仍可执行 import/replace
- audit metadata 包含 `gateway_key_id`
- audit metadata 不包含 old/new raw gateway secrets
- idempotency scope 仍是 trusted project + trusted actor

观察到：

```json
{
  "status": "passed",
  "old_secret_overlap_status": 200,
  "old_secret_removed_status": 401,
  "old_secret_removed_error_type": "AUTH_ERROR",
  "validate_status": 200,
  "missing_gateway_auth_status": 401,
  "missing_permission_status": 403,
  "import_status": 201,
  "audit_counts": {
    "registry_revisions": 2,
    "admin_audit_events": 3,
    "idempotency_records": 1,
    "providers": 1
  }
}
```

## Tests

已新增或更新 tests：

- comma-separated gateway secret parsing
- multiple active gateway secrets accepted
- removed old gateway secret rejected
- request key id 缺失时使用 configured key id
- request key id 出现在 audit metadata
- import/replace 将 gateway key id 传入 Postgres audit metadata
- no active gateway secret fails closed
- local/private behavior 保持兼容

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

## 未实现

本 slice 刻意不增加：

- real public gateway deployment
- OAuth/OIDC provider implementation
- public registry CRUD
- provider onboarding
- automatic publish/reload
- credential vault
- billing
- marketplace
- workflow runtime

## 推荐下一项任务

```text
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0
```

closeout 应判断这个 production-boundary support 是否足够，再进入下一个 hosted Control Plane readiness gap。
