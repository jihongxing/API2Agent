# API2Agent Protocol v0.1

状态：draft

## 1. 目的

API2Agent Protocol 定义 API 如何变成可靠、可审计、可路由的 Agent capabilities。

这不是 marketplace protocol。

当前 protocol 目标是：

```text
API description
  -> capability
  -> provider candidate
  -> routing decision
  -> credential resolution
  -> execution attempt
  -> usage event
  -> ledger row
  -> feedback into future routing
```

## 2. 设计原则

- model-neutral
- provider-neutral
- API-neutral
- local-first
- proxy-ready
- audit-first
- marketplace-later

Protocol 的目标是让 API2Agent 不只是 generator，而是 Agent API access 的标准 execution and audit layer。

## 3. Identity Layer

每一次 controlled 或 auditable call 最终都应该能归属于一个 identity。

最小 identity objects：

- `project_id`
- `user_id`
- `api_key_id`
- `agent_id`

当前本地实现只强制需要：

- `project_id`

Protocol 方向：

```json
{
  "project_id": "proj_123",
  "user_id": "user_123",
  "api_key_id": "key_123",
  "agent_id": "agent_123"
}
```

Identity 必须挂到：

- routing decisions
- usage events
- ledger rows
- quotas
- future billing exports

没有 identity，API2Agent 只是匿名流量管道。

## 3.1 Credential Orchestration Layer

真实 API 大多不是 marketplace-ready。很多 API 有 credentials，但没有按调用付费模型；很多 internal APIs 甚至没有正式 billing system。

因此，API2Agent 需要先做 credential orchestration，而不是先做 payment。

Credential orchestration 回答：

- 谁拥有调用权
- 使用哪个 credential
- credential 如何被注入
- 哪个 project 或 agent 消耗了它
- usage event 如何引用它且不暴露 secrets

Credential 草案：

```json
{
  "credential_id": "cred_123",
  "owner_type": "project",
  "owner_id": "proj_123",
  "provider_id": "github",
  "auth_type": "api_key",
  "injection_mode": "header",
  "injection_name": "Authorization",
  "source": "env",
  "secret_ref": "GITHUB_TOKEN"
}
```

支持的 ownership modes：

- `user`
- `project`
- `platform`
- `provider`

早期支持的 sources：

- `env`
- `config`
- `inline`
- future `vault`

Credential orchestration 不是 billing。它是 permission 和 attribution layer，使未来 billing-ready usage 成立。

详见 `docs/cn-ZH/CREDENTIAL_ORCHESTRATION.md`。

## 4. Capability Layer

Capability 是 Agent routing 的语义单位。

稳定 capability 字段：

- `id`
- `name`
- `description`
- `input_schema`
- `output_schema`
- `safety`

示例：

```json
{
  "id": "public_ip_lookup",
  "name": "Public IP Lookup",
  "description": "Return the caller's public IP address.",
  "input_schema": {},
  "output_schema": {
    "type": "object",
    "properties": {
      "ip": { "type": "string" }
    },
    "required": ["ip"]
  },
  "safety": "read"
}
```

## 5. Capability Taxonomy

Capability ID 不能只是随手写的字符串。

v0.1-alpha 最小命名规则：

```text
<domain>.<resource>.<action>
```

最小 taxonomy shape：

```text
network.public_ip.get
image.text.generate
image.poster.create
commerce.product.search
crm.contact.lookup
payment.charge.create
```

Taxonomy 目标：

- 避免同一 intent 出现重复命名
- 让 providers 可比较
- 减少 routing if/else
- 为未来 discovery 打基础

这一步是未来 marketplace-like behavior 可信的前置条件。

## 6. Provider Candidate

Provider candidate 是 capability 的具体实现。

稳定 provider 字段：

- `id`
- `capability_id`
- `provider_id`
- `tool_id`
- `estimated_cost`
- `output_mapping`
- `metadata`

示例：

```json
{
  "id": "ipify_public_ip",
  "capability_id": "public_ip_lookup",
  "provider_id": "ipify",
  "tool_id": "get",
  "estimated_cost": 0.001,
  "output_mapping": {
    "ip": "$.ip"
  },
  "metadata": {
    "package_dir": ".dogfood/ipify"
  }
}
```

## 7. Provider Onboarding Protocol

Provider onboarding 是 API2Agent 供给侧入口。

最小 onboarding 字段：

- provider identity
- capability ID
- generated package or hosted endpoint
- auth requirements
- output mapping
- cost metadata
- SLA metadata
- test endpoint or smoke test

草案：

```json
{
  "provider_id": "ipify",
  "capability_id": "public_ip_lookup",
  "runtime": {
    "type": "local_package",
    "package_dir": ".dogfood/ipify"
  },
  "pricing": {
    "cost_source": "estimated",
    "estimated_cost": 0.001
  },
  "quality": {
    "declared_sla": null,
    "smoke_test": "get"
  }
}
```

## 8. Cost Source

Cost 必须声明来源。

稳定 cost source values：

- `estimated`
- `provider_declared`
- `observed`
- `contracted`

示例：

```json
{
  "estimated_cost": 0.001,
  "cost_source": "estimated"
}
```

没有 cost source，routing 和 billing-ready ledger 都不可信。

## 9. Routing Contract

Routing 为 capability 选择 provider candidate。

稳定 routing decision 字段：

- `id`
- `project_id`
- `capability_id`
- `strategy`
- `preset`
- `client_region`
- `selected_provider_id`
- `selected_provider_region`
- `ranked_provider_ids`
- `metrics`
- `failover_policy`
- `created_at`

稳定 routing strategies：

- `first`
- `random`
- `lowest_cost`
- `lowest_latency`
- `region_aware_latency`
- `highest_success_rate`
- `balanced`

`client_region` 是 optional。strategy 为 `region_aware_latency` 时，routing 会结合它、provider `regions`、provider `geo_affinity`，以及可用的 client-region latency metrics。

`selected_provider_region` 由确定性规则推导：

1. 如果 selected provider `regions` 包含 `client_region`，使用 `client_region`
2. 使用显式声明的 `global`
3. 使用 `geo_affinity=global`
4. `geo_affinity=cn-only` 时使用 `cn`
5. 使用 provider 声明的第一个 region
6. 否则留空

Routing 必须 policy-driven and auditable。

## 10. Failover Policy

Failover 是显式 policy。

稳定字段：

- `enabled`
- `max_attempts`
- `retry_on_error_types`
- `retry_on_status_codes`

默认可重试 status codes：

- `408`
- `429`
- `500`
- `502`
- `503`
- `504`

SDK-facing 默认可重试 error types：

- `RATE_LIMIT`
- `TIMEOUT`
- `PROVIDER_ERROR`
- `NORMALIZATION_ERROR`
- `UNKNOWN`

SDK-facing 默认不可重试 error types：

- `AUTH_ERROR`
- `INVALID_REQUEST`
- `NOT_FOUND`

当 `status_code` 和 `error_type` 同时存在时，先检查 `retry_on_status_codes`。这样 HTTP 层面的 retry policy 是显式、可审计的。

## 11. Usage Event Contract

Usage event 记录 execution attempt。

稳定字段：

- `id`
- `routing_decision_id`
- `execution_mode`
- `project_id`
- `capability_id`
- `provider_id`
- `tool_id`
- `method`
- `path`
- `status_code`
- `success`
- `latency_ms`
- `estimated_cost`
- `error_type`
- `request_metadata`
- `credential_reference`
- `provider_runtime_reference`
- `is_golden`
- `created_at`

`credential_reference` 绝不能包含 raw secret。它应该指向 resolved credential identity 或 redacted credential source。

稳定 execution modes：

- `direct`
- `proxy`
- `shadow`
- `replay`

计划中的 execution modes：

- `race`：并发执行多个 providers，返回符合条件的最佳结果

`replay` events 是 audit/debug records。默认不进入 routing metrics。

Optional region-aware usage fields：

- `client_region`
- `api2agent_region`
- `provider_region`
- `latency_total_ms`
- `latency_network_ms`
- `latency_provider_ms`
- `latency_overhead_ms`

这些字段在 v0.1 是 optional。它们已经进入 local schema，并为 location-aware routing 和 decision dataset 工作预留。

## 12. Ledger Contract

Ledger rows 聚合 usage events。

稳定 row 字段：

- `project_id`
- `capability_id`
- `provider_id`
- `execution_mode`
- `total_calls`
- `successful_calls`
- `failed_calls`
- `success_rate`
- `average_latency_ms`
- `estimated_cost`

Ledger 是 measurement，不是 billing。

## 12.1 Replay Contract

Replay 把已记录的 execution history 变成 debug 和 regression 工具。

当前命令：

```text
api2agent replay <usage_event_id>
```

当前实现状态：

- replay preflight 已实现
- supported SDK adapters 和 no-credential HTTP events 已支持 exact replay execution
- 当 safe request metadata 和 provider runtime references 存在时，命令会返回 `exact_replay_metadata_ready: true`

最小 replay 数据：

- usage event
- routing decision
- capability ID
- provider ID
- tool ID
- request metadata where safely available
- redacted credential references

如果 credentials、request body 或 provider state 没有保留，导致无法完全 replay，必须给出明确 warning。

当前 preflight 字段：

- `replayable`
- `exact_replay_metadata_ready`
- `missing_for_exact_replay`
- `warnings`

## 12.2 Golden Trace Contract

Golden trace 是已知正确的 execution，可作为 benchmark 或 regression reference。

草案字段：

```json
{
  "is_golden": true
}
```

Golden trace marker 已在 usage events 上实现。

## 13. Error Taxonomy

Error taxonomy 必须 machine-readable，因为 routing 和 failover 依赖它。

当前 execution/proxy error types：

- `http_status`
- `http_error`
- `proxy_error`
- `quota_exceeded`
- `missing_auth`
- `missing_parameters`
- `output_normalization`
- `no_provider`
- `all_providers_failed`

当前 SDK adapter error types：

- `RATE_LIMIT`
- `TIMEOUT`
- `AUTH_ERROR`
- `INVALID_REQUEST`
- `NOT_FOUND`
- `PROVIDER_ERROR`
- `NORMALIZATION_ERROR`
- `UNKNOWN`

后续要定义：

- retriable vs non-retriable
- provider fault vs caller fault
- billing-impacting vs non-billing-impacting

## 14. Routing Feedback Loop

API2Agent 不应该只记录 metrics，还应该使用 metrics。

Feedback loop：

```text
usage event
  -> metrics snapshot
  -> routing policy
  -> next routing decision
```

最小 metrics：

- success rate
- average latency
- estimated cost per call
- failure count
- error type distribution

未来 routing 可以变成 context-aware。v0.1 支持 aggregate provider metrics 和第一版 region-aware latency heuristic。

## 15. 当前实现覆盖

已实现：

- local compiler
- generated runner
- generated MCP server
- proxy
- usage events
- routing decisions
- failover policy
- direct/proxy execution mode
- ledger
- provider registry contract
- decision/usage contract
- SDK `weather.get` core loop
- SDK benchmark helper
- SDK 显式 routing strategy
- SDK failover，并把 attempts 记录到同一个 routing decision 下
- generated package shadow and replay execution
- golden trace listing and ledger filtering
- Credential Schema v0.1 models
- local credential resolver
- generated package execution 的 credential reference attribution
- proxy-side credential injection 和 config-based credential resolution
- credential policy、scope、lifecycle 和 audit reporting
- region-aware usage schema
- provider region metadata
- local decision dataset contract
- 带 optional `client_region` 的 `region_aware_latency` routing strategy
- deterministic selected provider-region semantics

尚未实现：

- full identity layer
- credential vault
- hosted control plane
- provider onboarding workflow
- cost source field
- capability taxonomy registry
- formal error taxonomy document
- routing feedback beyond aggregate metrics

## 16. v0.1 非目标

- marketplace UI
- payment processing
- provider revenue share
- public provider onboarding portal
- hosted SaaS APIs
- settlement

这些后面可能会出现，但 API2Agent v0.1 必须先成为可靠的 capability execution and audit protocol。
