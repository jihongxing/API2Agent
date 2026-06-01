# Go Control Plane Hosted Permission Store Schema Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Go Control Plane Postgres schema 现在包含 durable hosted permission-store boundary。

这一片只新增 schema artifacts 和 schema tests。它不会把 hosted gateway 接到 Postgres，不新增 public role CRUD，不新增 OAuth/OIDC，不新增 invitation/session lifecycle，不部署 production gateway，不新增 marketplace/provider onboarding，不写入 vault material，不新增 billing，不新增 workflow runtime，不触发 automatic propagation，也不允许 Data Plane 读取 mutable Control Plane tables。

## 已实现

在以下文件中新增 hosted permission store tables：

```text
services/control-plane/schema/postgres/001_persistent_registry_store.sql
```

Tables：

- `hosted_subjects`
- `hosted_project_memberships`
- `hosted_roles`
- `hosted_role_bindings`
- `hosted_permission_grants`
- `hosted_policy_versions`
- `hosted_permission_decisions`

## Schema Boundary

schema 支持 contract harness 已证明的 internal read model：

```text
hosted_subjects
  -> hosted_project_memberships
  -> hosted_role_bindings
  -> hosted_roles
  -> hosted_permission_grants
  -> hosted_policy_versions
  -> hosted_permission_decisions
```

gateway 仍拥有 permission lookup。private Control Plane 仍只接收 gateway-issued trusted claims，并继续作为第二道 authorization gate。

## Constraints And Indexes

已新增：

- 非空 `external_subject_ref` 的 unique external subject reference
- 每个 `(subject_id, project_id)` 只允许一条 membership
- project/status membership lookup index
- 每个 `(subject_id, project_id, role_id)` 只允许一条 active role binding
- project/status role binding lookup index
- 每个 `(role_id, permission, scope_type)` 只允许一条 active permission grant
- permission/status grant lookup index
- unique `(policy_source, policy_version)`
- 每个 `policy_source` 只允许一个 active policy version
- 按 `(subject_id, project_id, resolved_at DESC)` 查询 decision
- 按 `(policy_source, policy_version)` 查询 decision

State constraints 覆盖：

- subject status：`active`、`suspended`、`disabled`
- membership status：`active`、`suspended`、`revoked`
- role status：`active`、`disabled`
- binding status：`active`、`revoked`
- grant status：`active`、`revoked`
- policy status：`draft`、`active`、`superseded`、`revoked`
- scope type：`project`、`organization`、`platform`
- binding source：`seed`、`system`、`operator`

Policy fingerprints 必须使用 `sha256:` prefix。

## Secret-Safe Evidence

schema 存储：

- `external_subject_ref`
- `subject_id`
- `actor_id`
- `project_id`
- `organization_id`
- `token_id`
- roles
- permissions
- `required_permission`
- `policy_source`
- `policy_version`
- `policy_fingerprint`
- `decision_id`
- `resolved_at`

schema 有意不存储：

- raw public bearer tokens
- raw session tokens
- OAuth access tokens
- OAuth refresh tokens
- gateway secrets
- plaintext API keys
- vault material

## Tests

新增 schema tests 覆盖：

- hosted permission store table presence
- key indexes and foreign keys
- state constraints
- policy fingerprint constraints
- decision evidence fields
- raw-token/gateway-secret/plaintext fields absence

Test file：

```text
services/control-plane/internal/registry/persistent_schema_test.go
```

## 验证

已通过：

```text
go test ./internal/registry -run "TestPersistentRegistrySQLSchemaContainsHostedPermissionStoreBoundary|TestHostedPermissionStoreSchemaDoesNotPersistRawSecrets|TestPersistentRegistrySQLSchemaContainsRequiredTablesAndConstraints"
go test ./...
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-store-schema/report.json
```

Go test 目录：

```text
services/control-plane
```

Live dogfood 观测结果：

- `status=passed`
- `missing_membership_status=403`
- `stale_policy_status=503`
- `partition_status=201`
- `import_status=201`
- `audit_counts.admin_audit_events=5`

## 保持不做的事项

未新增 public CRUD、public user/project/role management、OAuth/OIDC integration、invitation/login/session lifecycle、production gateway deployment、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic snapshot publish/reload、registry behavior change 或 Data Plane mutable table read。

## 下一项建议任务

```text
Go Control Plane Hosted Permission Store Schema Closeout + Phase Review v0
```
