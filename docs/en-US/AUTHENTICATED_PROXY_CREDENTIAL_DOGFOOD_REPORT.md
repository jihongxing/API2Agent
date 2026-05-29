# Authenticated Proxy Credential Dogfood Report

Date: 2026-05-30

## Purpose

Validate that the local proxy can use credential config to authenticate a real provider API call while keeping usage metadata redacted.

## Real API

- provider: `httpbin`
- endpoint: `https://httpbin.org/bearer`
- auth: Bearer token
- token type: dummy dogfood token, not a real account secret

## Credential Config

```yaml
credentials:
  - credential_id: httpbin_bearer
    provider_id: httpbin
    auth_type: bearer
    injection_mode: header
    injection_name: Authorization
    source: config
    secret_value: dogfood-token
    scope:
      - capability:httpbin.auth.check
    rotation_hint: dogfood-dummy-token
```

## Results

- proxy call returned HTTP 200
- provider response reported `authenticated=true`
- usage event succeeded
- usage event stored `credential_reference=config:httpbin_bearer`
- usage credential metadata stored owner, source, scope, status, and rotation hint
- usage metadata did not contain `dogfood-token`
- `api2agent usage --credential-audit --json` returned a secret-safe audit event

## Commands

```text
python -m api2agent.cli usage --db .dogfood/authenticated-proxy-credential/usage.sqlite --credential-audit --json
```

## Product Learning

This confirms the local API2Agent loop can execute:

```text
proxy request -> credential config -> resolver -> auth injection -> real API -> usage ledger -> credential audit CLI
```

That is the core local BYOK control-plane loop needed before hosted credential vault work.
