# Go Control Plane Hosted Admin Gateway Permission Source Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 Go Control Plane hosted-readiness implementation slice 应是：

```text
Go Control Plane Hosted Admin Gateway Permission Source Implementation v0
```

这一 slice 应为 hosted admin gateway harness 定义并实现一个窄的 local permission-source contract。Gateway 应在转发到 private Control Plane 之前，基于 authenticated public principal 和 project-scoped policy source 推导 trusted `X-API2Agent-*` role and permission claims。

Control Plane 应继续把 trusted gateway headers 当作 gateway-issued claims 处理，前提是 gateway authentication 已通过。新的 permission source 属于 gateway boundary，而不是 public Control Plane CRUD。

## 为什么现在做

Hosted admin path 已证明：

- local/private admin identity
- hosted admin principal shape
- trusted-gateway authenticator
- trusted gateway secret rotation and key-id evidence
- local gateway contract harness
- public trusted-header stripping
- trusted claim injection
- request id and idempotency propagation
- audit and idempotency evidence using trusted gateway principal claims

剩余缺口是 permission issuance。Harness 目前使用 static dogfood policy。下一步设计应定义 permission source，未来可以接 durable hosted policy，同时不启动 public CRUD、OAuth/OIDC、marketplace、vault、billing、workflow runtime 或 automatic propagation。

## Current Baseline

现有 permission constants：

```text
control_plane.registry.validate
control_plane.registry.import_replace
control_plane.snapshot.export_artifact
control_plane.distribution.publish
control_plane.distribution.read_current
```

现有 trusted gateway headers：

```text
X-API2Agent-Gateway-Authorization
X-API2Agent-Gateway-Key-ID
X-API2Agent-Principal-ID
X-API2Agent-Actor-ID
X-API2Agent-Project-ID
X-API2Agent-Organization-ID
X-API2Agent-Token-ID
X-API2Agent-Roles
X-API2Agent-Permissions
```

现有 Control Plane 行为：

- 在读取 trusted headers 前验证 gateway authorization
- 解析 trusted identity、roles 和 permissions
- 使用 `AdminPrincipal.HasPermission` 检查 endpoint required permission
- permissions 缺失时返回 `403 AUTHZ_DENIED`
- 在 audit rows 中记录 project/auth/token/gateway metadata
- idempotency 按 trusted project 和 actor 做 scope

## Goals

- 定义 gateway-side permission source boundary
- 将 public authenticated principals 映射为 trusted admin principal claims
- deterministic 地推导 project-scoped roles and permissions
- permission lookup 失败或拒绝时，在 forwarding 前 fail closed
- 保持 Control Plane endpoint permission checks 作为第二道 authoritative gate
- 在 trusted headers 和 audit metadata 中记录 non-secret permission evidence
- 保持当前 trusted-gateway authenticator 行为
- 支持 local dogfood，不实现真实 OAuth/OIDC
- 为未来 persistent hosted permission store 留出空间

## Non-Goals

不实现：

- OAuth/OIDC provider integration
- login/session/user lifecycle
- invitation management
- public project/user/role CRUD
- provider onboarding
- marketplace/provider submission
- credential vault writes
- billing or settlement
- workflow runtime
- production gateway deployment
- automatic snapshot publish/reload
- Data Plane reads from mutable Control Plane tables

## Permission Source Contract

引入 gateway-local contract，概念形状为：

```text
ResolveGatewayAdminPrincipal(public_request, endpoint_permission)
  -> GatewayPermissionDecision
```

Decision fields：

```text
allowed
deny_reason
subject_id
actor_id
project_id
organization_id
token_id
roles
permissions
policy_source
policy_version
permission_source
resolved_at
```

Implementation 可以先把它保留为 Python harness data，或根据 gateway harness 所在位置做小型 Go/Python struct。v0 不要求 database。

## Static v0 Policy Shape

v0 使用 gateway harness 中的 local static policy file 或 in-memory map。

建议 shape：

```json
{
  "principals": [
    {
      "public_token": "dogfood-admin-token",
      "subject_id": "user_admin",
      "actor_id": "user_admin",
      "project_id": "project_alpha",
      "organization_id": "org_alpha",
      "token_id": "token_admin",
      "roles": ["admin"],
      "permissions": [
        "control_plane.registry.validate",
        "control_plane.registry.import_replace",
        "control_plane.snapshot.export_artifact",
        "control_plane.distribution.publish",
        "control_plane.distribution.read_current"
      ],
      "policy_version": "static-v1"
    }
  ]
}
```

Public token 只用于 dogfood，不得 forward 到 Control Plane，也不得写入 evidence artifacts。

## Trust Boundary

Gateway 必须：

1. authenticate the public request locally
2. strip caller-supplied `X-API2Agent-*` trusted headers
3. resolve permissions from the permission source
4. check the requested endpoint permission before forwarding
5. inject only gateway-issued trusted headers
6. forward request id and idempotency key
7. replace public `Authorization` with private gateway authorization

Control Plane 必须：

1. authenticate the private gateway secret
2. parse trusted headers
3. perform its existing endpoint required-permission check
4. persist audit/idempotency evidence using trusted claims

这形成两道 gates：

```text
gateway permission source
Control Plane endpoint permission check
```

两者都必须 fail closed。

## Endpoint Permission Mapping

Gateway harness 应将 public paths and methods 映射到 Control Plane handlers 使用的同一组 permission constants：

| Method / Path | Required Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |

未知 public admin paths 应在 gateway 本地以 `404` 或 `405` 失败，不应到达 Control Plane。

## Header Evidence Contract

继续注入现有 trusted headers。如有必要，可增加 optional non-secret evidence headers：

```text
X-API2Agent-Permission-Source
X-API2Agent-Policy-Version
```

如果增加，Control Plane 应仅将其记录为 audit metadata，在明确实现前不得用它做 authorization。Source of truth 仍是 `X-API2Agent-Permissions` 加 endpoint required-permission checks。

v0 可以接受把 policy evidence 保留在 harness dogfood report 中，而不是新增 Control Plane headers。

## Failure Semantics

Gateway-local failures：

| Condition | HTTP | Error Type | Forward? |
| --- | --- | --- | --- |
| missing public auth | `401` | `PUBLIC_AUTH_REQUIRED` | no |
| invalid public token | `401` | `PUBLIC_AUTH_INVALID` | no |
| permission source unavailable | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| principal missing project scope | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| principal lacks endpoint permission | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| unknown admin route | `404` | `PUBLIC_ROUTE_NOT_FOUND` | no |
| unsupported method | `405` | `PUBLIC_METHOD_NOT_ALLOWED` | no |

Control Plane failures 保持：

- `401 AUTH_ERROR` for invalid trusted gateway auth
- `403 AUTHZ_DENIED` for missing trusted permissions
- `503 AUTH_SERVICE_UNAVAILABLE` for platform auth configuration failure

## Audit And Idempotency Evidence

Dogfood report 应断言：

- raw public token absent
- raw gateway secret absent
- actor/project/organization/token id 是 trusted gateway outputs
- permission source id 或 policy version 在 safe metadata 或 report evidence 中可见
- successful admin audit rows 使用 trusted actor/project
- idempotency rows 使用 trusted project/actor scope
- denied gateway-local requests 不产生 Control Plane audit/idempotency rows
- Control Plane denied requests 保持现有 `AUTHZ_DENIED` behavior

## Implementation Plan

1. Extend the local hosted admin gateway harness with a permission source abstraction.
2. Add a static dogfood permission policy.
3. Resolve public bearer tokens into principal/project/role/permission claims.
4. Derive endpoint required permission from public method/path.
5. Fail locally before forwarding when auth or permission source denies.
6. Inject trusted claims only after permission source approval.
7. Preserve existing trusted header stripping and gateway secret/key-id behavior.
8. Add dogfood assertions for allowed, denied, missing, and spoofed cases.
9. Keep the Control Plane trusted-gateway authenticator unchanged unless optional safe policy evidence headers are added.

## Test Plan

增加或更新 tests/dogfood checks：

- admin public token resolves to expected trusted claims
- readonly public token can validate registry but cannot import/replace
- missing public token fails locally and does not reach Control Plane
- invalid public token fails locally and does not reach Control Plane
- permission source denial fails before forwarding
- caller-supplied trusted permissions are stripped before policy resolution
- gateway-injected permissions match the static policy
- Control Plane still denies if the gateway injects insufficient permission
- audit metadata and idempotency scope use trusted claims
- raw public token and raw gateway secret are absent from report artifacts

## Dogfood Plan

运行 local hosted admin gateway contract dogfood，覆盖：

1. admin token -> registry validate succeeds
2. admin token -> import/replace succeeds
3. readonly token -> registry validate succeeds
4. readonly token -> import/replace fails locally with `403 PUBLIC_AUTHZ_DENIED`
5. spoofed trusted headers from public caller are stripped
6. missing public token fails locally with `401 PUBLIC_AUTH_REQUIRED`
7. broken permission source fails locally with `503 PERMISSION_SOURCE_UNAVAILABLE`
8. forced insufficient trusted permission reaches Control Plane and returns `403 AUTHZ_DENIED`
9. Postgres audit/idempotency evidence remains trusted-claim based

## Acceptance Criteria

- permission-source contract is documented and implemented in the local gateway harness
- static dogfood policy maps public principals to trusted roles and permissions
- gateway derives endpoint required permissions before forwarding
- gateway denies unauthorized public requests before Control Plane forwarding
- Control Plane endpoint permission check remains the second authoritative gate
- audit and idempotency evidence remains secret-safe and trusted-claim based
- 未新增 OAuth/OIDC、public CRUD、marketplace、provider onboarding、vault、billing、workflow runtime、automatic propagation 或 Data Plane mutable-table reads

## 推荐下一项任务

```text
Go Control Plane Hosted Admin Gateway Permission Source Implementation v0
```
