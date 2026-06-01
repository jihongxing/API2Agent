# Go Control Plane Hosted Permission Store Schema Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

The Go Control Plane Postgres schema now includes a durable hosted permission-store boundary.

This slice adds schema artifacts and schema tests only. It does not wire the hosted gateway to Postgres, add public role CRUD, add OAuth/OIDC, add invitation/session lifecycle, deploy a production gateway, add marketplace/provider onboarding, write vault material, add billing, add workflow runtime, trigger automatic propagation, or let the Data Plane read mutable Control Plane tables.

## Implemented

Added hosted permission store tables to:

```text
services/control-plane/schema/postgres/001_persistent_registry_store.sql
```

Tables:

- `hosted_subjects`
- `hosted_project_memberships`
- `hosted_roles`
- `hosted_role_bindings`
- `hosted_permission_grants`
- `hosted_policy_versions`
- `hosted_permission_decisions`

## Schema Boundary

The schema supports the internal read model proven by the contract harness:

```text
hosted_subjects
  -> hosted_project_memberships
  -> hosted_role_bindings
  -> hosted_roles
  -> hosted_permission_grants
  -> hosted_policy_versions
  -> hosted_permission_decisions
```

The gateway still owns permission lookup. The private Control Plane still receives gateway-issued trusted claims and remains the second authorization gate.

## Constraints And Indexes

Added:

- unique external subject reference for non-empty `external_subject_ref`
- one membership per `(subject_id, project_id)`
- project/status membership lookup index
- active unique role binding per `(subject_id, project_id, role_id)`
- project/status role binding lookup index
- active unique permission grant per `(role_id, permission, scope_type)`
- permission/status grant lookup index
- unique `(policy_source, policy_version)`
- one active policy version per `policy_source`
- decision lookup by `(subject_id, project_id, resolved_at DESC)`
- decision lookup by `(policy_source, policy_version)`

State constraints cover:

- subject status: `active`, `suspended`, `disabled`
- membership status: `active`, `suspended`, `revoked`
- role status: `active`, `disabled`
- binding status: `active`, `revoked`
- grant status: `active`, `revoked`
- policy status: `draft`, `active`, `superseded`, `revoked`
- scope type: `project`, `organization`, `platform`
- binding source: `seed`, `system`, `operator`

Policy fingerprints must use a `sha256:` prefix.

## Secret-Safe Evidence

The schema stores:

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

The schema intentionally does not store:

- raw public bearer tokens
- raw session tokens
- OAuth access tokens
- OAuth refresh tokens
- gateway secrets
- plaintext API keys
- vault material

## Tests

Added schema tests for:

- hosted permission store table presence
- key indexes and foreign keys
- state constraints
- policy fingerprint constraints
- decision evidence fields
- absence of raw-token/gateway-secret/plaintext fields

Test file:

```text
services/control-plane/internal/registry/persistent_schema_test.go
```

## Validation

Passed:

```text
go test ./internal/registry -run "TestPersistentRegistrySQLSchemaContainsHostedPermissionStoreBoundary|TestHostedPermissionStoreSchemaDoesNotPersistRawSecrets|TestPersistentRegistrySQLSchemaContainsRequiredTablesAndConstraints"
go test ./...
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-store-schema/report.json
```

Go test directory:

```text
services/control-plane
```

Live dogfood observed:

- `status=passed`
- `missing_membership_status=403`
- `stale_policy_status=503`
- `partition_status=201`
- `import_status=201`
- `audit_counts.admin_audit_events=5`

## Non-Goals Preserved

No public CRUD, public user/project/role management, OAuth/OIDC integration, invitation/login/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic snapshot publish/reload, registry behavior change, or Data Plane mutable table read was added.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Store Schema Closeout + Phase Review v0
```
