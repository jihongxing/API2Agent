# Credential Lifecycle Dogfood Report

日期：2026-05-30

## 目的

验证在 hosted vault 出现前，credential lifecycle metadata 可以支撑本地 rotation 和 audit behavior。

## Lifecycle Fields

- `status`：`active` 或 `disabled`
- `expires_at`：可选 ISO timestamp
- `rotation_hint`：可选 rotation note

## 结果

- disabled credentials 返回 `credential_disabled`
- expired credentials 返回 `credential_expired`
- active 且未过期的 credentials 可以正常 resolve
- redacted metadata 保留 `status`、`expires_at` 和 `rotation_hint`
- raw credential secrets 不会出现在 error payloads 或 metadata 中

## 测试

```text
pytest tests/test_credentials.py tests/test_control_layer.py
33 passed
```

## 产品结论

Lifecycle metadata 让 credential orchestration 成为可审计的 control layer，而不只是 secret injection。它让本地 BYOK 用户可以在 hosted credential storage 出现前表达 rotation 和 expiry。
