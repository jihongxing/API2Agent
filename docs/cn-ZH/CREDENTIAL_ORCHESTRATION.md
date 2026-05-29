# Credential Orchestration Layer

状态：v0.1 本地实现已启动

## 为什么需要这一层

真实世界的大多数 API 并不是天然 marketplace-ready。

它们大致分三类：

- 标准 SaaS API：有 API key，也有 provider 侧 billing
- 有 credentials，但没有按调用付费机制的 API
- 没有正式 credential 或 billing model 的公共 API / 内部 API

如果 API2Agent 要成为 Agent API calls 的执行层，就不能假设每个 provider 都已经有干净的 API key、quota 和 billing system。

真正有用的中间层不是 payment，而是 credential orchestration。

## 产品原则

Marketplace 不是从 payment 开始。

它从这里开始：

```text
谁有权调用
  -> 使用哪个 credential
  -> credential 属于谁
  -> 哪个 project 或 agent 消耗了它
  -> 执行结果是什么
```

Credential orchestration 会把 API access 变成可审计的 execution right。

## 非目标

Credential orchestration 不是：

- payment processing
- provider settlement
- revenue share
- public marketplace
- v0.1 的 hosted secrets vault

这些都应该等 API2Agent 有可靠 execution、identity、usage 和 credential attribution 后再做。

## Credential Object

草案结构：

```json
{
  "credential_id": "cred_123",
  "owner_type": "project",
  "owner_id": "proj_123",
  "provider_id": "github",
  "auth_type": "api_key",
  "injection_mode": "header",
  "injection_name": "Authorization",
  "scope": ["repo.read"],
  "source": "env",
  "secret_ref": "GITHUB_TOKEN"
}
```

稳定字段：

- `credential_id`
- `owner_type`：`user`、`project`、`platform`、`provider`
- `owner_id`
- `provider_id`
- `auth_type`：`api_key`、`bearer`、`basic`、`oauth`、`none`
- `injection_mode`：`header`、`query`、`body`、`none`
- `injection_name`
- `scope`
- `source`：`env`、`config`、`inline`、`vault`
- `secret_ref`

## Credential Resolver

Resolver 只回答一个问题：

```text
在这个 project、agent、provider 和 tool 下，可以使用哪个 credential？
```

函数草案：

```text
resolve_credential(
  project_id,
  agent_id,
  capability_id,
  provider_id,
  tool_id
)
```

Local MVP 的解析顺序：

1. inline override
2. project config file
3. environment variable
4. 当 provider auth 是 `none` 时，不需要 credential

Hosted 之后的解析顺序：

1. explicit request credential binding
2. project credential
3. platform credential
4. provider-managed credential

## Injection Contract

Execution layer 应该拿到 resolved credential reference，而不是把 raw secrets 写进 logs。

注入示例：

```json
{
  "credential_reference": "cred_123",
  "request_patch": {
    "headers": {
      "Authorization": "[INJECTED]"
    }
  }
}
```

规则：

- raw secrets 不能写入 usage events
- request metadata 必须 redacted
- usage events 应该保存 `credential_reference`
- replay 在 credential required but unavailable 时必须 warning

## Usage Event 关联

Usage events 已经有 `credential_reference` 字段。

这个字段最终应该能识别：

- 使用了哪个 credential
- credential 属于谁
- credential 是 user-owned、project-owned、provider-owned 还是 platform-owned
- 这次调用是 billable、quota-only 还是 free

最小 future usage event extension：

```json
{
  "credential_reference": "cred_123",
  "credential_owner_type": "project",
  "credential_source": "env"
}
```

## Cost And Billing 关系

Credential orchestration 支撑 billing-ready measurement，但它不是 billing。

模式：

- `BYOK`：user 或 project 提供 credentials；API2Agent 提供 routing、observability、replay 和 quota
- `platform_key`：API2Agent 提供 credentials，未来可以向用户收费
- `provider_key`：provider 提供 credentials，未来可以 revenue share
- `none`：无 credential 的公共 API 或内部 API

在 payment 存在前，也可以记录 virtual cost：

```json
{
  "estimated_cost": 0.0001,
  "cost_source": "estimated"
}
```

## Phase Plan

### Phase C0：Documented Contract

- 定义 credential schema
- 定义 resolver order
- 定义 injection contract
- 定义 usage event linkage

### Phase C1：Local Credential Resolver

- 从 env/config/inline 解析 credentials - 已实现
- 注入 generated runner execution - 已实现
- redacts request metadata - 已实现
- 把 `credential_reference` 写入 usage events - 已实现
- proxy request injection - 已实现

### Phase C2：Proxy Credential Injection

- generated runners 发送 intent 和 metadata - 已实现
- proxy 负责 resolve 并 inject credentials - 已实现
- proxy mode 下 generated files 不再需要发送 provider secrets - 已实现
- proxy credential 缺失时会记录 failed usage events，且不继续 forward - 已实现

Proxy credential intent 是一个脱敏的 control-plane object：

```json
{
  "credential_id": "github_GITHUB_TOKEN",
  "owner_type": "project",
  "owner_id": "local",
  "provider_id": "github",
  "auth_type": "bearer",
  "injection_mode": "header",
  "injection_name": "Authorization",
  "source": "env",
  "secret_ref": "GITHUB_TOKEN"
}
```

它告诉 proxy 应该解析哪个 credential，但不会包含 raw provider secret。

### Phase C3：Hosted Credential Store

- encrypted credential storage
- project-level credential management
- access policy
- rotation
- audit log

### Phase C4：Economic Integration

- BYOK accounting
- platform-key accounting
- provider-key accounting
- quota and cost policy
- billing-ready exports

## 下一步任务

下一项工程任务应该是：

```text
Credential config loading for local proxy
```

验收标准：

- proxy 可以加载 project-level config credentials
- proxy 可以通过同一套 resolver contract 解析 env 和 config credentials
- config-loaded proxy credentials 在 usage metadata 中保持 redacted
- generated runner proxy mode 继续保持不携带 provider secret
