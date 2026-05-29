# Credential Scope Dogfood Report

Date: 2026-05-30

## Purpose

Validate that credential `scope` can restrict provider credentials by capability and tool without exposing secrets.

## Scope Syntax

Supported entries:

- `provider:<provider_id>`
- `capability:<capability_id>`
- `tool:<tool_id>`
- `*`
- `*:*`

Empty scope means unrestricted for the matching provider.

## Results

- `capability:demo.get` allowed a credential for `capability_id=demo.get`
- `tool:get` allowed a credential for `tool_id=get`
- `capability:demo.create` denied a credential for `capability_id=demo.get`
- out-of-scope errors used `credential_scope_denied`
- out-of-scope higher-precedence inline credentials did not fall back to config credentials
- redacted metadata preserved the declared scope and did not expose raw secrets

## Tests

```text
pytest tests/test_credentials.py tests/test_control_layer.py
30 passed
```

## Product Learning

Scope checks are the first local access-control primitive for credential orchestration. They make BYOK safer before hosted identity exists and keep the future hosted vault contract compatible with the local resolver.
