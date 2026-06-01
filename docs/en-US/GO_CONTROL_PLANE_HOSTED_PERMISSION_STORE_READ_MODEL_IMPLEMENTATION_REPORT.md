# Go Control Plane Hosted Permission Store Read Model Implementation Report v0

Date: 2026-06-01

Status: complete

## Summary

The Go Control Plane now has an internal hosted permission-store read model over the Postgres hosted permission tables.

This slice keeps the read model private to `internal/registry`. It does not wire the hosted gateway runtime to Postgres, add public CRUD, add OAuth/OIDC, add invitation/session lifecycle, deploy a production gateway, add marketplace/provider onboarding, write vault material, add billing, add workflow runtime, trigger automatic propagation, or let the Data Plane read mutable Control Plane tables.

## Implemented

Added:

```text
services/control-plane/internal/registry/hosted_permission_store.go
```

The read model:

- starts a repeatable-read, read-only transaction.
- reads exactly one active hosted policy version.
- resolves a hosted subject by external subject reference.
- resolves project membership for the requested project.
- resolves active role bindings and active hosted roles.
- resolves active permission grants.
- returns a gateway-compatible local decision shape with status, error type, deny reason, identity evidence, role evidence, permission evidence, policy source/version/fingerprint, decision id, and resolved time.
- generates deterministic `decision-*` ids from subject, project, required permission, policy version, and resolved time.

## Fail-Closed Behavior

Covered fail-closed cases:

- missing membership -> `403 PUBLIC_AUTHZ_DENIED`
- suspended membership -> `403 PUBLIC_AUTHZ_DENIED`
- revoked grant -> `403 PUBLIC_AUTHZ_DENIED`
- missing required permission -> `403 PUBLIC_AUTHZ_DENIED`
- no active policy -> `503 PERMISSION_SOURCE_UNAVAILABLE`
- ambiguous active policy view -> `503 PERMISSION_SOURCE_UNAVAILABLE`

The read model does not write `hosted_permission_decisions` in v0. Decision persistence remains a future wiring/lifecycle task.

## Secret-Safe Evidence

Decision evidence includes stable identifiers only:

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

Regression coverage verifies raw public tokens, gateway secrets, OAuth tokens, refresh tokens, and plaintext material are not carried in the decision evidence.

## Tests

Added:

```text
services/control-plane/internal/registry/hosted_permission_store_test.go
```

The test harness uses a scripted SQL driver and verifies:

- repeatable-read/read-only transaction options.
- allowed decision evidence for active subject, membership, roles, grants, and active policy.
- fail-closed missing membership, suspended membership, revoked grant, missing permission, no active policy, and ambiguous active policy.
- no write queries are issued by the v0 read model.
- decision evidence remains raw-secret safe.

## Validation

Passed:

```text
gofmt -w services/control-plane/internal/registry/hosted_permission_store.go services/control-plane/internal/registry/hosted_permission_store_test.go
go test ./internal/registry -run HostedPermission
go test ./...
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
git diff --check
```

Go test directory:

```text
services/control-plane
```

Python test and diff-check directory:

```text
repository root
```

## Non-Goals Preserved

No public user/project/role CRUD, OAuth/OIDC integration, invitation/login/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic snapshot publish/reload, gateway runtime wiring, or Data Plane mutable table read was added.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Store Read Model Closeout + Phase Review v0
```
