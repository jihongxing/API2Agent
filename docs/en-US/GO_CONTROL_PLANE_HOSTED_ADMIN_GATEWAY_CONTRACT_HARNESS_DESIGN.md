# Go Control Plane Hosted Admin Gateway Contract Harness Design v0

Date: 2026-05-31

Status: complete

## Decision

Add a local hosted admin gateway contract harness before building any real public gateway.

The harness is a dogfood-only gateway process that proves this boundary:

```text
public dogfood request
  -> local gateway harness
  -> strip caller-supplied trusted headers
  -> inject static trusted claims
  -> authenticate to Control Plane with gateway secret
  -> private Control Plane admin endpoint
```

Recommended next task after this design is accepted by the user:

```text
Go Control Plane Hosted Admin Gateway Contract Harness Implementation v0
```

## Why This Is Next

The Control Plane-side trusted-gateway mechanics are complete:

- hosted/trusted-gateway authenticator
- active gateway secret set
- gateway key-id evidence
- audit/idempotency identity propagation
- live direct-to-Control-Plane dogfood

The remaining unproven boundary is the gateway behavior itself. Current dogfood sends trusted headers directly to the Control Plane. The next proof should run a local gateway process that receives public requests, strips spoofed headers, injects trusted claims, and forwards to the Control Plane.

## Goals

- define local gateway harness responsibilities
- define public auth stubs without implementing OAuth/OIDC
- define static identity and permission policy
- define public header stripping matrix
- define trusted claim injection rules
- define gateway secret and key-id forwarding rules
- define request id and idempotency header propagation
- define negative spoofing cases
- define dogfood evidence and acceptance criteria

## Non-Goals

- no real public gateway deployment
- no OAuth/OIDC provider implementation
- no signup, login, invitation, or user lifecycle
- no public registry CRUD APIs
- no provider onboarding
- no marketplace provider submission
- no credential vault writes
- no plaintext secret storage
- no billing or settlement state
- no workflow engine
- no automatic snapshot export, publish, or Data Plane reload
- no Data Plane reads from mutable Control Plane tables

## Harness Shape

Recommended implementation:

```text
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
```

The script should start:

```text
podman Postgres
  -> api2agent-controlplane serve
  -> local gateway harness HTTP server
  -> public dogfood HTTP requests to gateway
```

The harness can be implemented in Python using standard library HTTP server and forwarding. It is not production code. It is a contract harness that exercises production boundary rules with real HTTP hops.

## Public Gateway Endpoints

The harness should forward only the current admin endpoints needed for the dogfood:

| Public Harness Endpoint | Forwarded Control Plane Endpoint |
| --- | --- |
| `GET /healthz` | `GET /healthz` |
| `POST /v1/admin/registry/validate` | `POST /v1/admin/registry/validate` |
| `POST /v1/admin/registry/import-replace` | `POST /v1/admin/registry/import-replace` |

Other paths should return a local `404` or `405` from the harness.

## Static Public Auth

The harness should use static dogfood bearer tokens only:

| Public Token | Meaning |
| --- | --- |
| `dogfood-public-admin-token` | full hosted admin test identity |
| `dogfood-public-readonly-token` | authenticated identity without registry mutation permission |

Rules:

- missing public `Authorization` returns gateway-local `401`
- wrong public token returns gateway-local `401`
- valid token maps to a static identity and permissions
- no OAuth/OIDC, cookies, sessions, database, or user lifecycle is added

## Static Identity Policy

Full admin token maps to:

```text
principal_id = gateway-harness-principal
actor_id = gateway-harness-actor
project_id = gateway-harness-project
organization_id = gateway-harness-org
token_id = gateway-harness-token-admin
roles = control-plane-admin,dogfood
permissions =
  control_plane.registry.validate
  control_plane.registry.import_replace
```

Readonly token maps to:

```text
principal_id = gateway-harness-readonly-principal
actor_id = gateway-harness-readonly-actor
project_id = gateway-harness-project
organization_id = gateway-harness-org
token_id = gateway-harness-token-readonly
roles = control-plane-readonly,dogfood
permissions =
  control_plane.distribution.read_current
```

The readonly token can be used to prove the Control Plane still returns `403 AUTHZ_DENIED` when the gateway forwards a request with insufficient endpoint permission.

## Header Stripping Matrix

The harness must remove caller-supplied versions of these headers before forwarding:

| Header Pattern | Action |
| --- | --- |
| `X-API2Agent-*` | strip all caller values |
| `X-API2Agent-Gateway-Authorization` | strip caller value and inject harness secret |
| `X-API2Agent-Gateway-Key-ID` | strip caller value and inject harness key id |
| `X-API2Agent-Principal-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Actor-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Project-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Organization-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Token-ID` | strip caller value and inject static policy value |
| `X-API2Agent-Roles` | strip caller value and inject static policy value |
| `X-API2Agent-Permissions` | strip caller value and inject static policy value |
| `X-Actor-ID` | strip |
| `X-Project-ID` | strip |
| `X-Organization-ID` | strip |
| `Cookie` | strip |
| `Proxy-Authorization` | strip |
| public `Authorization` | consume locally, do not forward |

The harness should forward safe request headers needed for body handling, such as `Content-Type`, after normalization.

## Trusted Header Injection

After public auth succeeds, the harness injects:

```text
X-API2Agent-Gateway-Authorization: Bearer <gateway-secret>
X-API2Agent-Gateway-Key-ID: <gateway-key-id>
X-API2Agent-Principal-ID: <principal-id>
X-API2Agent-Actor-ID: <actor-id>
X-API2Agent-Project-ID: <project-id>
X-API2Agent-Organization-ID: <organization-id>
X-API2Agent-Token-ID: <token-id>
X-API2Agent-Roles: <comma-separated roles>
X-API2Agent-Permissions: <comma-separated permissions>
```

The harness should use the same gateway secret and key id that the Control Plane service is configured to accept.

## Propagated Request Headers

The harness should preserve:

| Header | Reason |
| --- | --- |
| `X-Request-ID` | audit/request correlation |
| `Idempotency-Key` | import/replace idempotency |
| `Content-Type` | request body parsing |

The harness should not synthesize mutation success. Control Plane responses should be proxied back to the public dogfood caller.

## Dogfood Scenarios

The later implementation dogfood should verify:

1. `GET /healthz` through the harness returns `200`.
2. Valid public admin token plus spoofed trusted headers returns `200` for registry validate.
3. Audit metadata uses harness-injected identity, not spoofed caller headers.
4. Caller-supplied `X-API2Agent-Gateway-Authorization` is stripped and replaced.
5. Missing public token returns gateway-local `401` and does not create Control Plane audit rows.
6. Readonly public token calling registry validate or import/replace returns `403 AUTHZ_DENIED` from the Control Plane.
7. Full admin token import/replace through the harness returns `201`.
8. Import/replace idempotency row uses harness-injected project and actor.
9. Audit metadata includes harness gateway key id.
10. Raw public bearer token and raw gateway secret do not appear in audit/idempotency evidence or report artifacts.

## Evidence Queries

If Postgres is available, dogfood should query:

- `admin_audit_events`
- `admin_mutation_idempotency_records`
- `registry_revisions`

Expected evidence:

- audit actor equals harness-injected actor
- audit metadata principal/project/org/token/key id equals harness policy
- spoofed public actor/project/principal values are absent
- idempotency project/actor equals harness policy
- raw gateway secret is absent
- raw public token is absent

## Failure Semantics

Gateway-local failures:

- missing public auth: `401`
- wrong public auth: `401`
- unsupported path: `404`
- unsupported method: `405`
- invalid request body forwarding failure: `502` or `500` in the dogfood harness

Control Plane propagated failures:

- insufficient trusted permissions: `403 AUTHZ_DENIED`
- missing idempotency headers after gateway forwarding: existing Control Plane `400 INVALID_REQUEST`
- mutation/persistence failures: existing Control Plane stable error envelope

## Implementation Test Requirements

The later implementation should include tests for:

- header stripping function removes all `X-API2Agent-*` caller headers
- public `Authorization` is consumed and not forwarded
- static full-admin policy injects expected claims
- static readonly policy injects limited permissions
- `X-Request-ID` and `Idempotency-Key` are preserved
- unsupported paths/methods fail locally

## Acceptance Criteria For This Design

- local gateway harness responsibilities are explicit
- static public auth and identity policy are explicit
- public header stripping matrix is explicit
- trusted claim injection rules are explicit
- request id and idempotency propagation are explicit
- negative spoofing cases are named
- dogfood evidence requirements are explicit
- no OAuth/OIDC, public CRUD, provider onboarding, vault, billing, marketplace, workflow, or automatic propagation is introduced
