# Credential Audit CLI Dogfood Report

日期：2026-05-30

## 目的

验证 local usage reporting 可以展示 credential audit data，同时不泄漏 secrets。

## Command

```bash
api2agent usage --db api2agent-usage.sqlite --credential-audit
api2agent usage --db api2agent-usage.sqlite --credential-audit --json
```

## 结果

- JSON output 包含 `credential_reference`
- JSON output 包含 selected redacted credential metadata
- JSON output 会聚合 credential-related failures
- text output 包含 reference、selected metadata 和 error type
- 即使 stored metadata 中意外出现 `secret_value`，allowlist 也会省略它
- CLI output 不包含 raw secret strings

## 测试

```text
pytest tests/test_cli.py tests/test_control_layer.py
46 passed
```

## 产品结论

Credential audit reporting 是 credential layer 的第一个 operator-facing surface。它让 local proxy behavior 在 hosted dashboards 出现前就可以解释。
