# API2Agent Protocol v0.2

状态：frozen contract draft

Contract version：`api2agent.protocol.v0.2`

Schema snapshot：`schemas/api2agent/v0.2/protocol.schema.json`

## 1. 目的

API2Agent Protocol v0.2 冻结 production-facing contract，用于把外部能力转化成 Agent 可调用的 execution unit。

Protocol 是 source-neutral 的，但当前 MVP 仍然坚持 API-first。

v0.2 的意义是让未来 production implementation 可以使用 Go、Rust、TypeScript 或其他 runtime，而不被 Python MVP 的实现假设锁死。

## 2. 范围

v0.2 定义：

- identity attribution
- capability definitions
- capability source metadata
- provider candidates
- credential references
- cost profiles
- latency profiles
- network topology metadata
- reliability profiles
- routing decisions
- usage events
- decision logs
- ledger rows

v0.2 不定义：

- marketplace UI
- payment settlement
- provider revenue share
- hosted SaaS APIs
- workflow engine semantics
- 所有 adapter implementation

## 3. Versioning 规则

每个导出的 protocol object 都必须包含：

- `schema_version`
- persisted object 的稳定 object ID
- 表示 event 或 decision 的 object 必须包含 creation timestamp

v0.2 schema version 是：

```text
api2agent.protocol.v0.2
```

未来版本可以增加 optional fields。

未来版本不能在没有新 contract version 的情况下删除或重命名 v0.2 stable fields。

## 4. Identity Reference

Identity 回答谁拥有或发起了这次调用。

稳定字段：

- `project_id`
- `user_id`
- `api_key_id`
- `agent_id`

规则：

- controlled 或 auditable execution 必须包含 `project_id`。
- local execution 中，`user_id`、`api_key_id`、`agent_id` 可以为 null。
- Usage events、routing decisions、decision logs、ledger rows、quota checks 和未来 billing exports 必须携带 identity attribution。

## 5. Execution Class

Execution class 描述外部能力来源的类型。

稳定值：

- `api`
- `workflow`
- `tool`
- `model`
- `human`
- `async_job`

规则：

- v0.2 在 protocol 层保留这些值。
- v0.2 不要求实现所有 execution class。
- 当前 Python MVP generated packages 应该映射为 `api`。

## 6. Capability Definition

Capability 是 Agent 请求和 router 优化的语义单位。

稳定字段：

- `id`
- `name`
- `description`
- `execution_class`
- `input_schema`
- `output_schema`
- `safety`
- `taxonomy`

命名规则：

```text
<domain>.<resource>.<action>
```

示例：

- `weather.current.get`
- `network.public_ip.get`
- `commerce.product.search`
- `payment.charge.create`

## 7. Capability Source Contract

Capability source metadata 描述执行能力来自哪里。

稳定字段：

- `source_id`
- `source_type`
- `execution_class`
- `executor_ref`
- `input_schema`
- `output_schema`
- `auth`
- `region_metadata`

稳定 `source_type` 值：

- `openapi`
- `curl`
- `http_endpoint`
- `workflow_endpoint`
- `local_function`
- `model_endpoint`
- `human_queue`
- `manual`

规则：

- v0.2 在实现上 API-first，但在 contract 上 source-neutral。
- 非 API source 必须先适配为 input -> execution -> output 形态，才能进入 routing。
- API2Agent 不应该成为 workflow engine；workflow 应通过 adapter 或 endpoint 被调用。

## 8. Provider Candidate

Provider candidate 实现一个 capability。

稳定字段：

- `id`
- `capability_id`
- `provider_id`
- `tool_id`
- `source_id`
- `execution_class`
- `estimated_cost`
- `cost_profile`
- `regions`
- `geo_affinity`
- `output_mapping`
- `metadata`

稳定 `geo_affinity` 值：

- `global`
- `regional`
- `cn-only`
- `unknown`

Provider region selection 应尽可能保持确定性。

## 9. Credential Reference

Credential reference 描述使用了哪个调用权，但不暴露 secret。

稳定字段：

- `credential_reference`
- `credential_id`
- `owner_type`
- `owner_id`
- `provider_id`
- `auth_type`
- `injection_mode`
- `source`
- `scope`
- `status`

规则：

- Protocol records 里绝不能出现 raw secret values。
- Usage events 只能存 references 或 redacted metadata。
- Replay 可能需要重新 resolve credential。

## 10. Cost Profile

Cost profile 让 routing 和未来 economic measurement 可审计。

稳定字段：

- `estimated_cost`
- `observed_cost`
- `currency`
- `unit`
- `cost_source`

稳定 `cost_source` 值：

- `estimated`
- `provider_declared`
- `observed`
- `contracted`

规则：

- `estimated_cost` 可以为 0。
- `observed_cost` 可以为 null。
- Billing 不能只从 ledger rows 推断。

## 11. Latency Profile

Latency profile 把 total latency 和组成部分拆开。

稳定字段：

- `latency_ms`
- `latency_p50_ms`
- `latency_p95_ms`
- `latency_p99_ms`
- `latency_cold_start_ms`
- `latency_network_ms`
- `latency_provider_ms`
- `latency_overhead_ms`
- `latency_region`

规则：

- `latency_ms` 是单次 execution 的顶层 observed latency。
- 无法测量时，component fields 可以为 null。
- Aggregate metrics 在 p99 可信之前，应该优先使用 p50 和 p95。

## 12. Network Topology

Network topology 让 region-aware routing 可审计。

稳定字段：

- `client_region`
- `edge_region`
- `api2agent_region`
- `provider_region`
- `selected_provider_region`
- `route_path`

规则：

- `client_region` 描述 caller 或 Agent execution region。
- `provider_region` 描述 provider 实际处理 attempt 的 region，如果可知。
- `selected_provider_region` 描述 router 选择的目标 provider region。
- `route_path` 记录 logical path，不要求记录每个 physical network hop。

## 13. Reliability Profile

Reliability profile 让 routing 能比较稳定性，而不只是 success rate。

稳定字段：

- `reliability_score`
- `success_rate`
- `timeout_rate`
- `error_rate`
- `retry_rate`
- `failover_rate`
- `sla_confidence`

规则：

- 分数字段存在时必须归一化到 0 到 1。
- `sla_confidence` 衡量的是 metric confidence，不是 declared SLA 本身。
- cold-start provider 的 reliability fields 可以为 null。

## 14. Routing Decision

Routing decision 是 provider 为什么被选择的可审计记录。

稳定字段：

- `id`
- `schema_version`
- `identity`
- `capability_id`
- `strategy`
- `preset`
- `topology`
- `candidate_provider_ids`
- `ranked_provider_ids`
- `selected_provider_id`
- `selected_provider_region`
- `metrics`
- `cost_estimate`
- `latency_estimate`
- `reliability_estimate`
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

规则：

- controlled execution 前必须记录 routing decision。
- 除 synthetic failure record 外，selected provider 必须出现在 `candidate_provider_ids` 里。
- `region_aware_latency` 在 `client_region` 可用时必须纳入考虑。

## 15. Usage Event

Usage event 记录 execution attempt。

稳定字段：

- `id`
- `schema_version`
- `routing_decision_id`
- `execution_mode`
- `identity`
- `capability_id`
- `provider_id`
- `tool_id`
- `method`
- `path`
- `status_code`
- `success`
- `latency`
- `topology`
- `cost`
- `error_type`
- `request_metadata`
- `credential_reference`
- `provider_runtime_reference`
- `is_golden`
- `created_at`

稳定 execution modes：

- `direct`
- `proxy`
- `shadow`
- `replay`
- `race`

规则：

- `race` 在 v0.2 中保留，不要求当前 MVP 实现。
- `replay` events 进入 audit ledgers，但默认不进入 routing metrics。
- `shadow` events 默认进入 routing metrics，除非 policy 另有说明。

## 16. Decision Log

Decision log 连接 context、candidates、decision 和 outcome。

稳定字段：

- `id`
- `schema_version`
- `request_id`
- `routing_decision_id`
- `identity`
- `capability_id`
- `input_fingerprint`
- `candidate_provider_ids`
- `candidate_regions`
- `routing_strategy`
- `routing_context`
- `selected_provider_id`
- `selected_provider_region`
- `cost_estimate`
- `latency_estimate`
- `reliability_estimate`
- `outcome`
- `usage_event_ids`
- `created_at`

规则：

- Decision logs 是未来 decision dataset 的种子。
- 默认不应该存储 raw user input。
- `input_fingerprint` 应足够稳定以便 debug，同时足够安全以保护隐私。

## 17. Ledger Row

Ledger row 聚合 usage events，用于 audit 和 measurement。

稳定字段：

- `schema_version`
- `identity`
- `capability_id`
- `provider_id`
- `execution_mode`
- `region`
- `total_calls`
- `successful_calls`
- `failed_calls`
- `success_rate`
- `average_latency_ms`
- `estimated_cost`
- `observed_cost`
- `error_counts`
- `period_start`
- `period_end`

规则：

- Ledger 是 measurement，不是 payment settlement。
- Billing system 未来可以消费 ledger data，但必须增加明确的 billing contracts。

## 18. Error Taxonomy

稳定 error categories：

- `RATE_LIMIT`
- `TIMEOUT`
- `AUTH_ERROR`
- `INVALID_REQUEST`
- `NOT_FOUND`
- `PROVIDER_ERROR`
- `NORMALIZATION_ERROR`
- `QUOTA_EXCEEDED`
- `MISSING_AUTH`
- `NO_PROVIDER`
- `ALL_PROVIDERS_FAILED`
- `UNKNOWN`

规则：

- Error records 应区分 caller fault、provider fault 和 platform fault。
- Failover policies 应使用标准化 error categories。

## 19. v0.1 Compatibility

v0.1 objects 到 v0.2 的映射：

- `project_id` 映射到 `identity.project_id`。
- 缺失的 identity fields 映射为 null。
- `latency_ms` 映射到 `latency.latency_ms`。
- region fields 映射到 `topology`。
- `estimated_cost` 映射到 `cost.estimated_cost`。
- 现有 generated package providers 映射为 `execution_class=api`。
- 缺失的 latency percentile fields 映射为 null。
- 缺失的 reliability fields 映射为 null。
- 现有 `credential_reference` 保持为 redacted credential reference。

v0.2 consumers 在 migration 期间必须容忍 null optional fields。

## 20. Freeze Criteria

该 contract 在以下条件满足时视为冻结：

- 本文档已提交
- schema snapshot 已提交
- roadmap 和 technical design 链接到本文档
- v0.1 compatibility 已文档化
- freeze commit 不包含 Python runtime feature expansion
