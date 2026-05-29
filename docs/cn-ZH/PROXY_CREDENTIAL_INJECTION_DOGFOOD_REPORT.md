# Proxy Credential Injection Dogfood Report

日期：2026-05-30

## 目的

验证 API2Agent 的 proxy mode 可以让 generated runners 不携带 provider secrets，同时仍然能够转发 authenticated provider requests。

## 场景

Generated runner 发送 credential intent：

- provider：`github`
- source：`env`
- secret reference：`TEST_API_TOKEN`
- injection：`Authorization` header

Proxy 在本地解析 env credential，把它注入 forwarded provider request，并通过 `credential_reference` 记录 usage attribution。

## 结果

- proxy 向 fake provider 转发了 `Authorization: Bearer secret-token`
- usage event 保存了 `credential_reference=env:TEST_API_TOKEN`
- usage request metadata 保存了 `secret_ref=TEST_API_TOKEN`
- usage request metadata 不包含 `secret-token`
- env credential 缺失时返回 `missing_credential_secret`
- env credential 缺失时不会调用 provider forwarder
- body credential injection 不会把 raw secret 污染到 usage metadata

## 测试

```text
pytest tests/test_control_layer.py tests/test_runner_generation.py
24 passed

pytest
127 passed
```

## 产品结论

Proxy-side credential injection 让 API2Agent 继续贴合 control-layer strategy：

- proxy mode 下 generated packages 不再需要 raw provider secrets
- proxy 成为 credential resolution 和 usage attribution 的统一入口
- missing credentials 会变成可审计的 ledger events，而不是静默的本地失败
