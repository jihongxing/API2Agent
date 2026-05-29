# Credential Audit CLI Dogfood Report

Date: 2026-05-30

## Purpose

Validate that local usage reporting can surface credential audit data without leaking secrets.

## Command

```bash
api2agent usage --db api2agent-usage.sqlite --credential-audit
api2agent usage --db api2agent-usage.sqlite --credential-audit --json
```

## Results

- JSON output includes `credential_reference`
- JSON output includes selected redacted credential metadata
- JSON output groups credential-related failures
- text output includes reference, selected metadata, and error type
- `secret_value` is omitted by allowlist even if it appears in stored metadata
- raw secret strings did not appear in CLI output

## Tests

```text
pytest tests/test_cli.py tests/test_control_layer.py
46 passed
```

## Product Learning

Credential audit reporting is the first operator-facing surface for the credential layer. It makes local proxy behavior explainable before hosted dashboards exist.
