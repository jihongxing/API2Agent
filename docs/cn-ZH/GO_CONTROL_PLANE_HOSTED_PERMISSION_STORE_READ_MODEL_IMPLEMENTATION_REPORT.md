# Go Control Plane Hosted Permission Store Read Model Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Go Control Plane 现在有了基于 Postgres hosted permission tables 的 internal hosted permission-store read model。

本 slice 保持 read model 仅位于 `internal/registry`。它没有把 hosted gateway runtime 接到 Postgres，没有增加 public CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault material writes、billing、workflow runtime、automatic propagation，也没有让 Data Plane 读取 mutable Control Plane tables。

## 已实现

新增：

```text
services/control-plane/internal/registry/hosted_permission_store.go
```

read model 会：

- 启动 repeatable-read、read-only transaction。
- 读取且只接受一个 active hosted policy version。
- 通过 external subject reference 解析 hosted subject。
- 为请求 project 解析 project membership。
- 解析 active role bindings 和 active hosted roles。
- 解析 active permission grants。
- 返回 gateway-compatible local decision shape，包括 status、error type、deny reason、identity evidence、role evidence、permission evidence、policy source/version/fingerprint、decision id 和 resolved time。
- 从 subject、project、required permission、policy version、resolved time 生成 deterministic `decision-*` id。

## Fail-Closed 行为

已覆盖的 fail-closed cases：

- missing membership -> `403 PUBLIC_AUTHZ_DENIED`
- suspended membership -> `403 PUBLIC_AUTHZ_DENIED`
- revoked grant -> `403 PUBLIC_AUTHZ_DENIED`
- missing required permission -> `403 PUBLIC_AUTHZ_DENIED`
- no active policy -> `503 PERMISSION_SOURCE_UNAVAILABLE`
- ambiguous active policy view -> `503 PERMISSION_SOURCE_UNAVAILABLE`

v0 read model 不写入 `hosted_permission_decisions`。decision persistence 仍保留给后续 wiring/lifecycle 任务。

## Secret-Safe Evidence

decision evidence 只包含稳定标识：

- subject id
- actor id
- project id
- organization id
- token id
- roles
- permissions
- required permission
- policy source/version/fingerprint
- decision id
- resolved time

回归覆盖会验证 raw public tokens、gateway secrets、OAuth tokens、refresh tokens 和 plaintext material 不会进入 decision evidence。

## 测试

新增：

```text
services/control-plane/internal/registry/hosted_permission_store_test.go
```

test harness 使用 scripted SQL driver，验证：

- repeatable-read/read-only transaction options。
- active subject、membership、roles、grants 和 active policy 的 allowed decision evidence。
- fail-closed missing membership、suspended membership、revoked grant、missing permission、no active policy 和 ambiguous active policy。
- v0 read model 不发出 write queries。
- decision evidence 保持 raw-secret safe。

## 验证

已通过：

```text
gofmt -w services/control-plane/internal/registry/hosted_permission_store.go services/control-plane/internal/registry/hosted_permission_store_test.go
go test ./internal/registry -run HostedPermission
go test ./...
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
git diff --check
```

Go test 工作目录：

```text
services/control-plane
```

Python test 和 diff-check 工作目录：

```text
repository root
```

## Non-Goals Preserved

没有增加 public user/project/role CRUD、OAuth/OIDC integration、invitation/login/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic snapshot publish/reload、gateway runtime wiring，或 Data Plane mutable table read。

## 下一项建议任务

```text
Go Control Plane Hosted Permission Store Read Model Closeout + Phase Review v0
```
