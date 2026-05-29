# Credential Policy Dogfood Report

Date: 2026-05-30

## Purpose

Validate that credential resolution is deterministic when multiple credentials can satisfy the same provider.

## Policy

Credential source precedence:

```text
inline override -> config credential -> request credential/env intent -> none
```

Config owner precedence:

```text
exact project owner -> local project owner -> first matching config credential
```

## Results

- inline credentials override config and request credentials
- config credentials override request/env intent credentials
- project-owned config credentials override local fallback credentials
- local fallback credentials override unrelated owner credentials
- redacted metadata preserves selected `owner_id`

## Tests

```text
pytest tests/test_credentials.py tests/test_control_layer.py
26 passed
```

## Product Learning

This makes credential orchestration predictable enough for local BYOK:

- the proxy can select a credential without ambiguity
- usage attribution can explain which owner supplied the credential
- future hosted identity can replace local owner matching without changing the basic resolver contract
