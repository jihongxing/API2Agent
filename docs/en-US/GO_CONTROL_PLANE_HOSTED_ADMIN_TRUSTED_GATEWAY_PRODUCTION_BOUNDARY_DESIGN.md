# Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0

Date: 2026-05-31

Status: complete

## Decision

Define the production trusted-gateway boundary before implementing a real hosted public edge.

The Control Plane already supports and has dogfooded this internal request shape:

```text
trusted gateway secret
  -> trusted X-API2Agent-* claims
  -> AdminPrincipal
  -> endpoint permission check
  -> audit and idempotency evidence
```

This design defines the contract that a production gateway must satisfy before it forwards hosted admin requests to the Control Plane.

Recommended next task after this design is accepted by the user:

```text
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Implementation v0
```

## Why This Is Next

The Control Plane-side hosted admin path is now implemented and dogfooded, but the production boundary is still implicit:

- no real gateway exists
- gateway header stripping is an assumption
- gateway secret rotation is not defined
- permission claim issuance is external
- deployment and observability behavior is not specified

The next safest move is a design pass. It should not add public CRUD, OAuth/OIDC, provider onboarding, vault, billing, marketplace, workflow runtime, or automatic propagation.

## Goals

- define the gateway-to-Control-Plane trust boundary
- define ingress header stripping and trusted header rewrite rules
- define gateway authentication and secret rotation policy
- define hosted admin identity and permission claim issuance assumptions
- define request/audit evidence contract
- define failure semantics for gateway and auth-service outages
- define deployment and observability expectations
- name implementation tests for a later slice
- name dogfood requirements for a later slice

## Non-Goals

- no OAuth/OIDC provider implementation
- no end-user signup, login, invitation, or admin UI
- no real public gateway deployment
- no public registry CRUD APIs
- no provider self-onboarding
- no marketplace provider submission
- no credential vault writes
- no plaintext secret storage
- no billing or settlement state
- no workflow engine
- no automatic snapshot export, publish, or Data Plane reload
- no Data Plane reads from mutable Control Plane tables

## Boundary Model

The production boundary is:

```text
public admin client
  -> production trusted gateway
  -> private Control Plane admin HTTP endpoint
```

The Control Plane must never trust public client identity headers directly.

The gateway owns:

- public caller authentication
- public session/token validation
- tenant/project membership lookup
- admin permission derivation
- trusted header stripping
- trusted claim injection
- gateway-to-Control-Plane authentication
- request correlation propagation

The Control Plane owns:

- gateway authentication
- trusted claim parsing
- endpoint permission enforcement
- admin mutation semantics
- audit evidence
- idempotency scope and replay behavior
- stable error envelope

## Gateway Ingress Rules

Before forwarding to the Control Plane, the gateway must remove all caller-supplied internal headers:

```text
X-API2Agent-*
```

The gateway must also remove or withhold public credentials from the forwarded request unless a later design explicitly requires them:

```text
Authorization
Cookie
Set-Cookie
Proxy-Authorization
X-Actor-ID
X-Project-ID
X-Organization-ID
```

The Control Plane already ignores public identity headers in trusted-gateway mode. The gateway still must strip them so logs, proxies, and future middleware do not confuse public identity with trusted internal identity.

## Gateway-To-Control-Plane Authentication

The gateway authenticates to the Control Plane with:

```text
X-API2Agent-Gateway-Authorization: Bearer <gateway-secret>
```

Rules:

- gateway auth is required for every `/v1/admin/*` request in hosted/trusted-gateway mode
- the gateway secret must be generated with at least 256 bits of entropy
- the gateway secret must be stored only in deployment secret storage
- the gateway secret must not appear in audit metadata, idempotency metadata, logs, metrics labels, errors, traces, or dogfood reports
- comparison remains constant-time over hashes
- `GET /healthz` remains public and does not require gateway auth

## Secret Rotation Design

Current implementation supports one gateway secret. The production boundary design requires a rotation-compatible model.

Recommended v0 implementation shape:

```text
TrustedGatewaySecrets = active secret set
TrustedGatewayKeyID   = optional non-secret key identifier
```

Configuration should support:

| Purpose | Recommended Config |
| --- | --- |
| active gateway secrets | `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRETS` |
| optional primary key id | `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_KEY_ID` |
| legacy single secret | `API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET` |

Rotation policy:

1. Add the new secret to the active set.
2. Deploy the Control Plane with old and new secrets accepted.
3. Deploy the gateway to use the new secret.
4. Confirm all gateway traffic uses the new key id or deployment version.
5. Remove the old secret from the active set.

The Control Plane should fail startup or fail authenticator construction when hosted/trusted-gateway mode has no active secret.

The optional key id is not a secret. It may be useful for diagnostics, but it must not be sufficient for authentication.

## Trusted Header Rewrite Rules

After authenticating the public caller and deriving authorization, the gateway injects:

| Header | Required | Source |
| --- | --- | --- |
| `X-API2Agent-Gateway-Authorization` | yes | gateway deployment secret |
| `X-API2Agent-Gateway-Key-ID` | optional | active gateway key id |
| `X-API2Agent-Principal-ID` | yes | authenticated user or service principal |
| `X-API2Agent-Actor-ID` | optional | acting user, defaults to principal at Control Plane |
| `X-API2Agent-Project-ID` | yes | selected project or tenant context |
| `X-API2Agent-Organization-ID` | optional | selected organization context |
| `X-API2Agent-Token-ID` | optional | public auth token/session id, never raw token |
| `X-API2Agent-Roles` | optional | derived roles |
| `X-API2Agent-Permissions` | yes | derived endpoint permissions |

The gateway must rewrite these headers from scratch. It must not preserve caller-supplied values.

## Identity Claim Contract

Required claims:

- `PrincipalID`
- `ProjectID`
- `Permissions`

Recommended rules:

- `PrincipalID` is stable and non-human-readable when possible.
- `ActorID` represents the effective actor and defaults to `PrincipalID`.
- `ProjectID` is the tenant/project scope for audit and idempotency.
- `OrganizationID` is included when a project belongs to an organization.
- `TokenID` identifies the public session/token record without exposing raw credentials.
- role strings are informational for now.
- permission strings are authoritative for endpoint access.
- wildcard permissions are not part of v0.

## Permission Issuance Contract

The gateway or its auth backend derives endpoint permissions from authenticated identity, project membership, and admin policy.

Current endpoint permissions:

| Permission | Endpoint |
| --- | --- |
| `control_plane.registry.validate` | `POST /v1/admin/registry/validate` |
| `control_plane.registry.import_replace` | `POST /v1/admin/registry/import-replace` |
| `control_plane.snapshot.export_artifact` | `POST /v1/admin/snapshots/export-artifact` |
| `control_plane.distribution.publish` | `POST /v1/admin/distribution/publish` |
| `control_plane.distribution.read_current` | `GET /v1/admin/distribution/current` |

Rules:

- permissions must be least-privilege per request
- missing permission returns `403 AUTHZ_DENIED`
- unknown permissions may be passed through as strings but do not grant access
- permission issuance failures should stop at the gateway and not call the Control Plane

## Audit And Evidence Contract

The Control Plane audit record must preserve:

- actor id
- principal subject id
- project id
- organization id when present
- auth method
- token id when present
- local/private status
- request id when supplied
- action, resource, outcome, and error type

The Control Plane idempotency scope remains:

```text
project_id + actor_id + operation + idempotency_key_hash
```

Do not store:

- gateway secret
- raw public bearer token
- raw cookies
- raw session material
- raw authorization headers

## Failure Semantics

Gateway behavior:

- unauthenticated public caller: gateway returns public `401`
- authenticated caller missing admin policy: gateway returns public `403`
- auth backend unavailable: gateway returns public `503` or equivalent platform error
- gateway cannot derive project context: gateway returns public `403` or `400` depending on caller actionability
- gateway cannot reach Control Plane: gateway returns public platform error and does not synthesize mutation success

Control Plane behavior:

- missing/malformed/wrong gateway auth: `401 AUTH_ERROR`
- missing trusted required claim: `401 AUTH_ERROR`
- malformed trusted claim: `401 AUTH_ERROR`
- missing endpoint permission: `403 AUTHZ_DENIED`
- trusted-gateway mode without active secret: `503 AUTH_SERVICE_UNAVAILABLE`
- mutation/idempotency/persistence failures keep existing stable error envelope

## Deployment Expectations

Production deployment should satisfy:

- Control Plane admin endpoints are not directly public
- only the gateway can reach hosted `/v1/admin/*` endpoints
- gateway and Control Plane communicate over private networking or equivalent transport protection
- gateway secret is injected by secret manager, not source control
- gateway strips and rewrites trusted headers on every request
- gateway forwards or creates a request id for correlation
- deployment can rotate gateway secrets without downtime

## Observability Expectations

Metrics/logs/traces should expose:

- gateway auth success/failure counts without secret values
- authz denial counts by endpoint and permission
- trusted-gateway mode startup configuration state without secret values
- active key id or deployment version when safe
- request id correlation between gateway and Control Plane
- audit write failures and idempotency store failures

Metrics/logs/traces must not expose:

- raw gateway secret
- raw public bearer token
- cookies
- raw trusted header values that contain sensitive identifiers unless explicitly approved

## Implementation Test Requirements

The later implementation slice should add tests for:

- multiple active gateway secrets accepted
- old secret removed after rotation is rejected
- optional gateway key id is parsed only as metadata
- no active gateway secret fails closed
- public `X-API2Agent-*` headers are ignored without gateway auth
- forwarded public `Authorization` does not become principal evidence
- audit/idempotency metadata never contains gateway secret
- permission issuance remains exact-match and least-privilege
- local/private authenticator remains compatible

## Dogfood Requirements

The later dogfood should:

- start hosted/trusted-gateway service with multiple active secrets
- validate old and new secrets during overlap
- validate old secret rejection after removal
- verify `X-API2Agent-Gateway-Key-ID` appears only as non-secret evidence if implemented
- verify public identity headers cannot override gateway claims
- verify audit and idempotency evidence still use trusted claims
- verify no raw secret appears in output artifacts

## Open Questions

- Should gateway key id be persisted in audit metadata, or only logs/metrics?
- Should active secrets be configured as raw secret values, secret references, or both?
- Should permission issuance live in the gateway process or a separate identity/policy service?
- Should the gateway eventually sign structured claims instead of forwarding headers?

## Acceptance Criteria For This Design

- production gateway trust boundary is explicit
- trusted header strip/rewrite rules are explicit
- gateway secret rotation approach is explicit
- permission issuance assumptions are explicit
- audit and idempotency evidence contract is explicit
- deployment and observability expectations are explicit
- implementation tests and dogfood requirements are named
- no public CRUD, OAuth implementation, provider onboarding, vault, billing, marketplace, workflow, or automatic propagation is introduced
