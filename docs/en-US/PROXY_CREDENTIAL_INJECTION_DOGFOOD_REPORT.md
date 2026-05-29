# Proxy Credential Injection Dogfood Report

Date: 2026-05-30

## Purpose

Validate that API2Agent proxy mode can keep provider secrets out of generated runners while still forwarding authenticated provider requests.

## Scenario

The generated runner sends a credential intent:

- provider: `github`
- source: `env`
- secret reference: `TEST_API_TOKEN`
- injection: `Authorization` header

The proxy resolves the env credential locally, injects it into the forwarded provider request, and records usage attribution with `credential_reference`.

## Results

- proxy forwarded `Authorization: Bearer secret-token` to the fake provider
- usage event stored `credential_reference=env:TEST_API_TOKEN`
- usage request metadata stored credential metadata with `secret_ref=TEST_API_TOKEN`
- usage request metadata did not contain `secret-token`
- missing env credential produced `missing_credential_secret`
- missing env credential did not call the provider forwarder
- body credential injection did not mutate usage metadata with the raw secret

## Tests

```text
pytest tests/test_control_layer.py tests/test_runner_generation.py
23 passed

pytest
116 passed
```

## Product Learning

Proxy-side credential injection keeps API2Agent aligned with the control-layer strategy:

- generated packages no longer need raw provider secrets in proxy mode
- proxy becomes the credential resolution and usage attribution point
- missing credentials become auditable ledger events instead of silent local failures
