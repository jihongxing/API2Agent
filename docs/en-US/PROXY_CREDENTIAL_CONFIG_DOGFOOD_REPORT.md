# Proxy Credential Config Dogfood Report

Date: 2026-05-30

## Purpose

Validate that the local proxy can load project-level credential config and use it without requiring credential intent in each proxy payload.

## Scenario

The proxy starts with a JSON/YAML credential config:

```yaml
credentials:
  - credential_id: cred_example
    provider_id: example
    auth_type: api_key
    injection_mode: query
    injection_name: api_key
    source: config
    secret_value: config-secret
```

A proxy request only identifies the provider and request target. It does not include a `credential` object.

## Results

- the config loader parsed project-level credentials
- proxy resolver selected the config credential by `provider_id`
- forwarded provider request received `api_key=config-secret`
- usage event stored `credential_reference=config:cred_example`
- usage request metadata stored redacted credential metadata
- usage request metadata did not contain `config-secret`

## Tests

```text
pytest tests/test_credentials.py tests/test_control_layer.py tests/test_cli.py
51 passed
```

## Product Learning

Config-loaded credentials are the local version of future hosted credential vault behavior:

- payloads can stay small and provider-secret-free
- proxy can become the single credential orchestration point
- config credentials provide a practical BYOK path before hosted identity and billing exist
