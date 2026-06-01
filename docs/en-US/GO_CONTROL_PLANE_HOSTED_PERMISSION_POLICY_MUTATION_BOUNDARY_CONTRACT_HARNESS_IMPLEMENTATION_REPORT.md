# Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness Implementation Report v0

Date: 2026-06-02

Status: complete

## Summary

The Control Plane registry package now has a local/private hosted permission policy mutation contract harness.

This proves draft, validation, review, promotion, rollback, idempotency, conflict, audit, and gateway read-model compatibility semantics for hosted permission policy rows without exposing public role CRUD, OAuth/OIDC, invitation/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, customer-facing decision history, public policy write APIs, or Data Plane reads from mutable Control Plane tables.

## Implemented

Added:

```text
services/control-plane/internal/registry/hosted_permission_policy_mutation.go
services/control-plane/internal/registry/hosted_permission_policy_mutation_test.go
```

The harness models:

- hosted subjects
- hosted project memberships
- hosted roles
- hosted role bindings
- hosted permission grants
- hosted policy versions
- policy drafts
- policy mutation audit events
- idempotency records

## Contract Helpers

Added local/private helper:

```text
HostedPermissionPolicyMutationHarness
```

It supports:

- `BeginDraft`
- `BeginStaleDraftForContract`
- `ValidateDraft`
- `RequestReview`
- `PromoteDraft`
- `RollbackPolicy`
- `ResolvePermission`
- `RunHostedPermissionPolicyMutationBoundaryDogfood`

These are local Go contract helpers, not public endpoint paths.

## Proven Semantics

The harness proves:

- draft changes do not affect read decisions before promotion
- promotion activates a new policy version
- prior active policy versions become superseded
- policy fingerprints are deterministic over the effective permission graph
- gateway-compatible permission decisions observe promoted grants
- rollback creates a new active rollback version instead of rewriting historical policy evidence
- persisted permission decisions remain outside mutation scope
- stale-base promotion returns `POLICY_VERSION_CONFLICT`
- duplicate active grant validation returns `POLICY_GRANT_CONFLICT`
- platform-scope escape returns `POLICY_SCOPE_VIOLATION`
- same idempotency key plus same canonical request returns replay evidence
- same idempotency key plus different canonical request returns `IDEMPOTENCY_KEY_CONFLICT`
- audit metadata keeps raw idempotency keys, raw tokens, gateway secrets, OAuth tokens, plaintext API keys, and vault material out of evidence

## Dogfood Report Helper

Added in-process report helper:

```text
RunHostedPermissionPolicyMutationBoundaryDogfood()
```

It reports:

- active policy version before promotion
- active policy fingerprint before promotion
- draft validation status
- promotion status
- idempotency replay count
- idempotency conflict status
- scope-violation status
- stale-base conflict status
- rollback status
- gateway decision before promotion
- gateway decision after promotion
- gateway decision after rollback
- audit row count
- secret leakage checks

Observed in tests:

- `status=passed`
- `draft_validation_status=passed`
- `promotion_status=passed`
- `rollback_status=passed`
- `idempotency_replay_count=1`
- `idempotency_conflict_status=IDEMPOTENCY_KEY_CONFLICT`
- `scope_violation_status=POLICY_SCOPE_VIOLATION`
- `stale_base_conflict_status=POLICY_VERSION_CONFLICT`
- `gateway_decision_before_promotion=denied`
- `gateway_decision_after_promotion=allowed`
- `gateway_decision_after_rollback=denied`
- no raw idempotency key, raw token, or gateway secret leakage

## Tests

Added tests for:

- promotion updates read-model-compatible decision evidence
- idempotency replay does not create a second mutation/audit outcome
- idempotency conflict does not mutate active policy rows
- scope-escape validation fails
- duplicate active grant validation fails
- stale-base promotion fails deterministically
- rollback creates a new active version and removes promoted grant access
- dogfood report passes and remains secret-safe

## Validation

Passed:

```text
go test ./internal/registry -run "TestHostedPermissionPolicyMutation"
go test ./internal/registry
go test ./...
```

Go test directory:

```text
services/control-plane
```

## Non-Goals Preserved

No public CRUD, public user/project/role management, OAuth/OIDC integration, invitation/login/session lifecycle, production gateway deployment, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, public policy write APIs, customer-facing decision history, legal-hold customer API, customer export/delete API, or Data Plane mutable table read was added.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness Closeout + Phase Review v0
```

That closeout should decide whether the local/private mutation contract proof is sufficient before a later durable/private implementation slice.
