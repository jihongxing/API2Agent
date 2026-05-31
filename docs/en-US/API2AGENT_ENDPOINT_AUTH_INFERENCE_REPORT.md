# API2Agent Endpoint-level Auth Inference Report v0

Date: 2026-05-31

Status: complete

## Summary

Generated OpenAPI packages now preserve endpoint-level auth requirements.

This closes a high-friction Tooling Re-entry gap: mixed public/protected APIs no longer force developers to configure credentials before trying public endpoints.

Scope stayed constrained:

- API-first only
- OpenAPI HTTP auth inference only
- no workflow engine
- no marketplace or billing
- no credential vault

## What Changed

### IR

`Tool` now has optional `auth` metadata.

Semantics:

- `null`: inherit `Capability.auth`
- `{"type": "none"}`: explicit public/no-auth operation
- `{"type": "bearer"}` or `{"type": "api_key"}`: operation-level auth override

### OpenAPI Parser

The parser now handles:

- document-level `security` as the default
- operation-level `security` overriding the document default
- operation-level `security: []` as explicit no auth
- bearer HTTP auth
- header API key auth

### Generated Runner

Generated `runner.py` is now tool-aware:

- direct mode requires auth only for the selected tool
- public tools do not fail with `missing_auth`
- proxy mode sends credential intent only when the selected tool needs provider auth

### Credential Resolver

The local credential resolver now selects config credentials by endpoint-relevant request properties:

- provider id
- auth type
- injection mode
- injection name
- scope/tool allowance

This prevents mixed-auth providers from using the wrong credential for an endpoint.

## Dogfood

Repro command:

```bash
python scripts/api2agent_endpoint_auth_inference_dogfood.py
```

Artifact:

```text
.dogfood/endpoint-auth-inference/result.json
```

Dogfood flow:

```text
mixed OpenAPI spec
  -> generated package
  -> direct public call without auth
  -> direct protected call missing auth
  -> direct endpoint apiKey call
  -> local proxy public/bearer/apiKey calls
  -> SQLite usage events with credential references
```

Dogfood checks:

- direct public endpoint succeeds without auth
- direct bearer endpoint fails with `missing_auth` when env is absent
- direct endpoint-level API key endpoint succeeds with only its API key env
- proxy public endpoint records `credential_reference == "none"`
- proxy bearer endpoint records `config:cred_bearer`
- proxy API key endpoint records `config:cred_admin`
- raw provider secrets are not logged
- scope remains API-first and no-workflow-engine

## Result

The dogfood passed.

Key observed values:

```json
{
  "direct_public_without_auth_success": true,
  "direct_secure_missing_auth": true,
  "direct_admin_endpoint_api_key_success": true,
  "proxy_usage_events_recorded": 3,
  "public_credential_reference": "none",
  "secure_credential_reference": "config:cred_bearer",
  "admin_credential_reference": "config:cred_admin"
}
```

## Why This Matters

Endpoint-level auth lowers API/provider onboarding cost without weakening the proxy/control path.

It also improves data quality:

- public calls are not mislabeled as auth failures
- protected calls carry the correct credential intent
- mixed-auth providers can produce trustworthy usage and credential-reference records

## Remaining Gap

The next Tooling Re-entry gap is base URL flexibility for real environments.

Next task:

```text
Base URL Override v0
```
