# Credential Orchestration Layer

Status: v0.1 local implementation started

## Why This Exists

Most real-world APIs are not marketplace-ready.

They fall into three broad groups:

- standard SaaS APIs with API keys and provider-side billing
- APIs with credentials but no per-call payment mechanism
- public or internal APIs with no formal credential or billing model

If API2Agent wants to become the execution layer for Agent API calls, it cannot assume every provider already has a clean API key, quota, and billing system.

The useful intermediate layer is not payment. It is credential orchestration.

## Product Principle

Marketplace does not start with payment.

It starts with:

```text
who has permission to call
  -> which credential is used
  -> who owns that credential
  -> which project or agent consumed it
  -> what happened during execution
```

Credential orchestration turns API access into an auditable execution right.

## Non-Goal

Credential orchestration is not:

- payment processing
- provider settlement
- revenue share
- a public marketplace
- a hosted secrets vault in v0.1

Those come later, after API2Agent has reliable execution, identity, usage, and credential attribution.

## Credential Object

Draft shape:

```json
{
  "credential_id": "cred_123",
  "owner_type": "project",
  "owner_id": "proj_123",
  "provider_id": "github",
  "auth_type": "api_key",
  "injection_mode": "header",
  "injection_name": "Authorization",
  "scope": ["repo.read"],
  "source": "env",
  "secret_ref": "GITHUB_TOKEN"
}
```

Stable fields:

- `credential_id`
- `owner_type`: `user`, `project`, `platform`, `provider`
- `owner_id`
- `provider_id`
- `auth_type`: `api_key`, `bearer`, `basic`, `oauth`, `none`
- `injection_mode`: `header`, `query`, `body`, `none`
- `injection_name`
- `scope`
- `source`: `env`, `config`, `inline`, `vault`
- `secret_ref`

## Credential Resolver

The resolver answers one question:

```text
For this project, agent, provider, and tool, which credential may be used?
```

Draft function:

```text
resolve_credential(
  project_id,
  agent_id,
  capability_id,
  provider_id,
  tool_id
)
```

Resolution order for the local MVP:

1. inline override
2. project config file
3. environment variable
4. no credential when provider auth is `none`

Hosted order later:

1. explicit request credential binding
2. project credential
3. platform credential
4. provider-managed credential

## Injection Contract

The execution layer should receive a resolved credential reference, not raw secrets in logs.

Example injection:

```json
{
  "credential_reference": "cred_123",
  "request_patch": {
    "headers": {
      "Authorization": "[INJECTED]"
    }
  }
}
```

Rules:

- raw secrets must not be written to usage events
- request metadata must be redacted
- usage events should store `credential_reference`
- replay must warn when a credential is required but unavailable

## Usage Event Link

Usage events already have a `credential_reference` field.

This field should eventually identify:

- which credential was used
- who owns the credential
- whether the credential is user-owned, project-owned, provider-owned, or platform-owned
- whether the call is billable, quota-only, or free

Minimum future usage event extension:

```json
{
  "credential_reference": "cred_123",
  "credential_owner_type": "project",
  "credential_source": "env"
}
```

## Cost And Billing Relationship

Credential orchestration enables billing-ready measurement, but it is not billing.

Modes:

- `BYOK`: user or project supplies credentials; API2Agent provides routing, observability, replay, and quota
- `platform_key`: API2Agent supplies credentials and may later charge users
- `provider_key`: provider supplies credentials and may later receive revenue share
- `none`: public or internal API with no credential

Virtual cost can be recorded before payment exists:

```json
{
  "estimated_cost": 0.0001,
  "cost_source": "estimated"
}
```

## Phase Plan

### Phase C0: Documented Contract

- define credential schema
- define resolver order
- define injection contract
- define usage event linkage

### Phase C1: Local Credential Resolver

- resolve credentials from env/config/inline - implemented
- inject into generated runner execution - implemented
- redact request metadata - implemented
- write `credential_reference` into usage events - implemented
- proxy request injection - implemented

### Phase C2: Proxy Credential Injection

- generated runners send intent and metadata - implemented
- proxy resolves and injects credentials - implemented
- generated files no longer need to send provider secrets in proxy mode - implemented
- missing proxy credentials are recorded as failed usage events without forwarding - implemented
- proxy can load project-level JSON/YAML credential config - implemented
- proxy can resolve config credentials even when payloads do not include credential intent - implemented

Proxy credential intent is a redacted control-plane object:

```json
{
  "credential_id": "github_GITHUB_TOKEN",
  "owner_type": "project",
  "owner_id": "local",
  "provider_id": "github",
  "auth_type": "bearer",
  "injection_mode": "header",
  "injection_name": "Authorization",
  "source": "env",
  "secret_ref": "GITHUB_TOKEN"
}
```

It tells the proxy which credential to resolve, but it does not contain the raw provider secret.

### Credential Resolution Policy

Resolver precedence is deterministic:

```text
inline override -> config credential -> request credential/env intent -> none
```

Config credential owner matching is also deterministic:

1. exact `owner_id == project_id`
2. project credential with `owner_id == local`
3. first matching credential in config order

This keeps local BYOK predictable before hosted identity and policy enforcement exist.

### Credential Scope Policy

`scope` is optional. An empty scope means unrestricted use for the matching provider.

Supported scope entries:

- `provider:<provider_id>`
- `capability:<capability_id>`
- `tool:<tool_id>`
- `*`
- `*:*`

Bare `capability_id` and `tool_id` values are also accepted for local compatibility.

If the highest-precedence credential is out of scope, resolution fails with `credential_scope_denied`. The resolver does not silently fall back to a lower-precedence credential, because that would bypass the declared access policy.

### Credential Lifecycle Policy

Credential metadata can express local lifecycle state:

- `status`: `active` or `disabled`
- `expires_at`: optional ISO timestamp
- `rotation_hint`: optional human-readable rotation note

Disabled credentials fail with `credential_disabled`.
Expired credentials fail with `credential_expired`.

Lifecycle checks run before scope checks and secret resolution. Redacted metadata preserves lifecycle fields so usage and audit records can explain why a credential was accepted or rejected without storing the secret.

### Credential Audit Reporting

Local usage reporting can surface credential audit events:

```bash
api2agent usage --db api2agent-usage.sqlite --credential-audit
api2agent usage --db api2agent-usage.sqlite --credential-audit --json
```

Audit output includes:

- `credential_reference`
- selected redacted credential metadata
- credential-related failure counts

Audit output uses an allowlist and never prints `secret_value`.

### Real Authenticated Dogfood

The local BYOK loop has been verified against a real authenticated API:

```text
proxy request -> credential config -> resolver -> auth injection -> real API -> usage ledger -> credential audit CLI
```

See `docs/en-US/AUTHENTICATED_PROXY_CREDENTIAL_DOGFOOD_REPORT.md`.

### Phase C3: Hosted Credential Store

- encrypted credential storage
- project-level credential management
- access policy
- rotation
- audit log

### Phase C4: Economic Integration

- BYOK accounting
- platform-key accounting
- provider-key accounting
- quota and cost policy
- billing-ready exports

## Next Task

The next engineering task should be:

```text
Credential orchestration milestone closeout and Phase 6 readiness review
```

Acceptance criteria:

- summarize current credential orchestration capabilities and limits
- identify which parts are ready for hosted control plane work
- decide whether to move next into hosted identity, vault, or more local hardening
