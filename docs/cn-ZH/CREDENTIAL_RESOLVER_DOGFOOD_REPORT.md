# Credential Resolver Dogfood 报告

日期：2026-05-30

## 目标

验证 Credential Schema v0.1 和 local resolver 是否可以：

- resolve env credential
- 注入 generated provider package
- 只记录 redacted `credential_reference`
- raw secrets 不进入 usage metadata
- credential 仍可 resolve 时可以 replay

## 方法

在 `.dogfood/credential-resolver/secure` 下创建了一个本地 authenticated provider package。

这个 generated-style runner 需要 injected `Authorization` header：

```text
Authorization: Bearer dogfood-secret
```

secret 通过 env 提供：

```powershell
$env:DOGFOOD_API_TOKEN='dogfood-secret'
```

调用命令：

```bash
python -m api2agent.cli call .dogfood/credential-resolver/registry.json \
  --capability-id secure.data.get \
  --db .dogfood/credential-resolver/usage.sqlite \
  --strategy first \
  --json
```

Replay 命令：

```bash
python -m api2agent.cli replay d25e4ca5-7903-45f6-add3-128902889b81 \
  --db .dogfood/credential-resolver/usage.sqlite \
  --execute \
  --json
```

## 结果

Call result：

- `ok`：`true`
- provider：`secure`
- normalized output：`{ "authorized": true }`
- credential reference：`env:DOGFOOD_API_TOKEN`

Usage event：

```json
{
  "credential_reference": "env:DOGFOOD_API_TOKEN",
  "request_metadata": {
    "credential": {
      "credential_id": "secure_DOGFOOD_API_TOKEN",
      "owner_type": "project",
      "owner_id": "local",
      "provider_id": "secure",
      "auth_type": "bearer",
      "injection_mode": "header",
      "injection_name": "Authorization",
      "source": "env",
      "secret_ref": "DOGFOOD_API_TOKEN"
    }
  }
}
```

Raw secret 状态：

- `dogfood-secret` 没有写入 usage event
- `dogfood-secret` 没有写入 replay metadata
- `dogfood-secret` 没有写入 ledger output

Replay result：

- `replayable`：`true`
- `exact_replay_metadata_ready`：`true`
- `executed`：`true`
- replay body：`{ "authorized": true }`

## 证明了什么

API2Agent 现在可以把 credentials 当作本地 execution rights 处理：

```text
provider auth metadata
  -> local credential resolver
  -> injected request patch
  -> provider execution
  -> credential_reference in usage event
  -> replay with redacted metadata
```

这完成了 Credential Schema v0.1 + Local Resolver 的第一版本地实现。

## 当前限制

- resolver API 已支持 config credentials，但还没有接 CLI config file
- proxy-side credential injection 尚未实现
- hosted vault 明确不在当前范围内
- OAuth 已建模，但未实现
