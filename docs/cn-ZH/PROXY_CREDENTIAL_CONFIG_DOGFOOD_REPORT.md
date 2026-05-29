# Proxy Credential Config Dogfood Report

日期：2026-05-30

## 目的

验证 local proxy 可以加载 project-level credential config，并在每次 proxy payload 不携带 credential intent 的情况下使用这些 credentials。

## 场景

Proxy 启动时加载 JSON/YAML credential config：

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

Proxy request 只标识 provider 和 request target，不包含 `credential` object。

## 结果

- config loader 可以解析 project-level credentials
- proxy resolver 可以通过 `provider_id` 选择 config credential
- forwarded provider request 收到 `api_key=config-secret`
- usage event 保存 `credential_reference=config:cred_example`
- usage request metadata 保存 redacted credential metadata
- usage request metadata 不包含 `config-secret`

## 测试

```text
pytest tests/test_credentials.py tests/test_control_layer.py tests/test_cli.py
51 passed
```

## 产品结论

Config-loaded credentials 是未来 hosted credential vault behavior 的本地版本：

- payload 可以保持小而且不携带 provider secret
- proxy 可以成为统一 credential orchestration point
- 在 hosted identity 和 billing 出现前，config credentials 提供了实用的 BYOK 路径
