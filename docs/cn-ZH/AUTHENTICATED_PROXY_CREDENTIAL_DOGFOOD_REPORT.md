# Authenticated Proxy Credential Dogfood Report

日期：2026-05-30

## 目的

验证 local proxy 可以通过 credential config 完成真实 provider API 的 authenticated call，同时 usage metadata 保持 redacted。

## Real API

- provider：`httpbin`
- endpoint：`https://httpbin.org/bearer`
- auth：Bearer token
- token 类型：dummy dogfood token，不是真实账号 secret

## Credential Config

```yaml
credentials:
  - credential_id: httpbin_bearer
    provider_id: httpbin
    auth_type: bearer
    injection_mode: header
    injection_name: Authorization
    source: config
    secret_value: dogfood-token
    scope:
      - capability:httpbin.auth.check
    rotation_hint: dogfood-dummy-token
```

## 结果

- proxy call 返回 HTTP 200
- provider response 报告 `authenticated=true`
- usage event 成功记录
- usage event 保存 `credential_reference=config:httpbin_bearer`
- usage credential metadata 保存 owner、source、scope、status 和 rotation hint
- usage metadata 不包含 `dogfood-token`
- `api2agent usage --credential-audit --json` 返回 secret-safe audit event

## Commands

```text
python -m api2agent.cli usage --db .dogfood/authenticated-proxy-credential/usage.sqlite --credential-audit --json
```

## 产品结论

这验证了 local API2Agent loop 可以完整执行：

```text
proxy request -> credential config -> resolver -> auth injection -> real API -> usage ledger -> credential audit CLI
```

这是进入 hosted credential vault 前，本地 BYOK control-plane loop 的核心闭环。
