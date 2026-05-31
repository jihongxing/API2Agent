# API2Agent Endpoint-level Auth Inference 报告 v0

日期：2026-05-31

状态：已完成

## 总结

Generated OpenAPI packages 现在会保留 endpoint-level auth requirements。

这补齐了一个高摩擦的 Tooling Re-entry 缺口：当一个 API 同时包含 public/protected endpoints 时，开发者不需要先配置 credential 才能试跑 public endpoint。

本次范围保持克制：

- API-first only
- 只做 OpenAPI HTTP auth inference
- 不做 workflow engine
- 不做 marketplace 或 billing
- 不做 credential vault

## 改动

### IR

`Tool` 现在有可选的 `auth` metadata。

语义：

- `null`：继承 `Capability.auth`
- `{"type": "none"}`：operation 明确 public/no-auth
- `{"type": "bearer"}` 或 `{"type": "api_key"}`：operation-level auth override

### OpenAPI Parser

Parser 现在支持：

- document-level `security` 作为默认值
- operation-level `security` 覆盖 document 默认值
- operation-level `security: []` 表示明确 no auth
- bearer HTTP auth
- header API key auth

### Generated Runner

Generated `runner.py` 现在是 tool-aware：

- direct mode 只对当前 tool 要求 auth
- public tools 不会再因为 capability 默认 auth 返回 `missing_auth`
- proxy mode 只在当前 tool 需要 provider auth 时发送 credential intent

### Credential Resolver

Local credential resolver 现在会按 endpoint-relevant request properties 选择 config credential：

- provider id
- auth type
- injection mode
- injection name
- scope/tool allowance

这避免了 mixed-auth provider 在不同 endpoint 上选错 credential。

## Dogfood

复现命令：

```bash
python scripts/api2agent_endpoint_auth_inference_dogfood.py
```

产物：

```text
.dogfood/endpoint-auth-inference/result.json
```

Dogfood flow：

```text
mixed OpenAPI spec
  -> generated package
  -> direct public call without auth
  -> direct protected call missing auth
  -> direct endpoint apiKey call
  -> local proxy public/bearer/apiKey calls
  -> SQLite usage events with credential references
```

Dogfood checks：

- direct public endpoint 无 auth 成功
- direct bearer endpoint 在缺少 env 时返回 `missing_auth`
- direct endpoint-level API key endpoint 只配置自己的 API key env 即可成功
- proxy public endpoint 记录 `credential_reference == "none"`
- proxy bearer endpoint 记录 `config:cred_bearer`
- proxy API key endpoint 记录 `config:cred_admin`
- raw provider secrets 未进入日志
- scope 保持 API-first 和 no-workflow-engine

## 结果

Dogfood 已通过。

关键观测值：

```json
{
  "direct_public_without_auth_success": true,
  "direct_secure_missing_auth": true,
  "direct_admin_endpoint_api_key_success": true,
  "proxy_usage_events_recorded": 3,
  "public_credential_reference": "none",
  "secure_credential_reference": "config:cred_bearer",
  "admin_credential_reference": "config:cred_admin"
}
```

## 为什么重要

Endpoint-level auth 降低了 API/provider onboarding cost，同时不削弱 proxy/control path。

它也提升了数据质量：

- public calls 不会被误标为 auth failures
- protected calls 会携带正确 credential intent
- mixed-auth providers 能产生可信的 usage 和 credential-reference records

## 剩余缺口

下一项 Tooling Re-entry 缺口是面向真实环境的 base URL flexibility。

下一项任务：

```text
Base URL Override v0
```
