# Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood 报告 v0

日期：2026-06-02

状态：complete

## 摘要

hosted permission store read model 现在有了 live Postgres dogfood evidence。

本 slice 会启动真实 local Postgres container，应用 Control Plane schema，seed registry project 和 hosted permission rows，并用真实 Postgres DSN 调用 internal Go read model。它没有接入 gateway runtime，没有持久化 permission decisions，没有增加 public CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault material writes、billing、workflow runtime、automatic propagation，也没有让 Data Plane 读取 mutable Control Plane tables。

## 已实现

新增专用 Go dogfood helper：

```text
services/control-plane/cmd/api2agent-hosted-permission-read-model-dogfood/main.go
```

新增 live Postgres dogfood harness：

```text
scripts/go_control_plane_hosted_permission_read_model_dogfood.py
```

Python harness 会：

- 用 Podman 启动 local Postgres 16 container。
- 应用 `services/control-plane/schema/postgres/001_persistent_registry_store.sql`。
- 通过 `seed-postgres` seed harness project。
- 插入 hosted subjects、project memberships、roles、role bindings、grants 和 active policy version rows。
- 使用真实 Postgres DSN 运行 Go helper。
- 写入 redacted JSON artifact。

Go helper 会：

- 使用 pgx 打开真实 Postgres DSN。
- 调用 `registry.NewHostedPermissionReadModel(db).Resolve`。
- 在真实 SQL 上证明 allowed 和 fail-closed cases。
- 断言 secret-safe decision evidence。
- 断言 v0 中 `hosted_permission_decisions` 仍为空。

## Dogfood Artifact

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-read-model-live-postgres/report.json
```

观察结果：

- `status=passed`
- `hosted_subjects=5`
- `hosted_project_memberships=4`
- `hosted_roles=4`
- `hosted_role_bindings=6`
- `hosted_permission_grants=9`
- ambiguous-policy case 前 `hosted_policy_versions=1`
- ambiguous-policy case 后 `hosted_policy_versions=2`
- `hosted_permission_decisions=0`
- `secret_safe_evidence=true`

## 已证明 Cases

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

allowed decision 包含：

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

Denied decisions 保留 typed status/error evidence 和 fail-closed deny reasons。

## Secret-Safe Evidence

artifact 会 redacts：

- Postgres password
- public bearer tokens
- gateway secret

Go helper 也会拒绝包含 raw public token、gateway secret、OAuth token、refresh token 或 plaintext markers 的 decision evidence。

## 验证

已通过：

```text
gofmt -w services/control-plane/cmd/api2agent-hosted-permission-read-model-dogfood/main.go
go test ./cmd/api2agent-hosted-permission-read-model-dogfood ./internal/registry -run HostedPermission
python -m py_compile scripts/go_control_plane_hosted_permission_read_model_dogfood.py
python scripts/go_control_plane_hosted_permission_read_model_dogfood.py --output .dogfood/go-control-plane-hosted-permission-read-model-live-postgres/report.json
```

## Non-Goals Preserved

没有新增 gateway runtime wiring、public user/project/role CRUD、OAuth/OIDC integration、invitation/login/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic snapshot publish/reload、decision persistence，或 Data Plane mutable table read。

## 下一项建议任务

```text
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood Closeout + Phase Review v0
```
