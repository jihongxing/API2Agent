# Credential Scope Dogfood Report

日期：2026-05-30

## 目的

验证 credential `scope` 可以按 capability 和 tool 限制 provider credentials，且不暴露 secrets。

## Scope Syntax

支持的 entries：

- `provider:<provider_id>`
- `capability:<capability_id>`
- `tool:<tool_id>`
- `*`
- `*:*`

空 scope 表示对 matching provider 不做限制。

## 结果

- `capability:demo.get` 允许 `capability_id=demo.get` 的 credential
- `tool:get` 允许 `tool_id=get` 的 credential
- `capability:demo.create` 会拒绝 `capability_id=demo.get` 的 credential
- out-of-scope errors 使用 `credential_scope_denied`
- 高优先级 inline credential out-of-scope 后，不会 fallback 到 config credentials
- redacted metadata 保留声明的 scope，且不暴露 raw secrets

## 测试

```text
pytest tests/test_credentials.py tests/test_control_layer.py
30 passed
```

## 产品结论

Scope checks 是 credential orchestration 的第一个本地 access-control primitive。它让 BYOK 在 hosted identity 出现前更安全，也让未来 hosted vault contract 能兼容当前 local resolver。
