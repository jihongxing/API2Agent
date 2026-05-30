# Go Data Plane Credential Config Dogfood 报告

日期：2026-05-30

## 目标

验证 Go Data Plane 是否可以加载本地 project credential config，并在 `/v1/execute` request 不携带 credential intent 的情况下完成 provider credential 注入。

这是进入 hosted credential vault 前的本地 BYOK 步骤。

## 语义

Credential config 在这个切片中：

- 只支持本地 JSON
- 通过 `API2AGENT_CREDENTIAL_CONFIG` 在 Data Plane 启动时加载
- 在 provider execution 前 resolve
- 可以注入 headers、query params 或 body patches
- 只以 redacted metadata 写入 `UsageEvent`

解析顺序：

```text
request credential intent -> config credential -> none
```

Config credential matching 使用：

- `provider_id`
- exact `owner_id == project_id`
- fallback project owner `owner_id == local`
- 第一个 matching config credential

Scope 和 lifecycle checks 仍然生效。

## Dogfood 命令

```bash
python scripts/go_dataplane_credential_config_dogfood.py \
  --output .dogfood/go-dataplane-credential-config/report.json
```

脚本会构建：

- `api2agent-dataplane`
- `api2agent-conformance`

## 观察结果

Dogfood 使用以下环境启动 Go Data Plane：

```bash
API2AGENT_CREDENTIAL_CONFIG=<temp>/credentials.json
API2AGENT_CONFIG_TOKEN=config-secret
```

请求不包含 `credential` object。

观察行为：

- provider 被调用一次
- provider 收到 `api_key=config-secret`
- response 成功
- `UsageEvent.credential_reference` 是 `config:cred_config_ipify`
- `resolution_strategy` 是 `static`
- credential metadata source 是 `config`
- raw secret 没有出现在 emitted events 中
- Protocol v0.2 conformance 通过

## 结果

Go Data Plane Credential Config v0 通过。

Go Data Plane 现在可以用本地 config credentials 作为未来 project-owned vault credentials 的替代物。

## 非目标

本切片不包含：

- hosted vault
- encrypted credential storage
- YAML config loading
- OAuth / delegated credentials
- UI credential management
