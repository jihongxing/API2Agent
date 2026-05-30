# Go Data Plane Credential Dogfood Report

日期：2026-05-30

## 目标

验证 Go Data Plane 可以解析 env-backed credential intent，把 credential 注入 provider request，并且只记录脱敏后的 credential attribution。

## 设置

Capability：

```text
network.public_ip.get
```

Provider：

- 本地 fake ipify-compatible provider
- 要求 `Authorization: Bearer local-dogfood-secret`
- 只有 header 注入成功时才返回 `{ "ip": "203.0.113.120" }`

脚本：

```text
python scripts/go_dataplane_credential_dogfood.py --output .dogfood/go-dataplane-credential/report.json
```

## 结果

```json
{
  "passed": true,
  "checks": {
    "response_success": true,
    "provider_output": true,
    "usage_success": true,
    "credential_reference": true,
    "redacted_metadata_has_secret_ref": true,
    "raw_secret_not_recorded": true
  }
}
```

## 证明了什么

- Go Data Plane 可以接收 request-level credential intent。
- local resolver 可以读取 env-backed secret。
- adapter path 可以把 resolved credential 注入 provider request。
- Usage events 会保留 `credential_reference` 和 redacted metadata。
- raw credential values 不会写入 event records。

## 备注

这仍然是本地骨架，不包含 hosted vault、OAuth、credential config files 或 delegated credentials。
