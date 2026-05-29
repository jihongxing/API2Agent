# Decision and Usage Contract

## 范围

这份文档定义 routing decision inspection 和 usage audit 的稳定本地 API 字段。

覆盖 API2Agent 本地输出：

- `api2agent decision --json`
- routing decision records
- correlated usage events

不定义 hosted SaaS APIs、billing APIs、payment APIs 或 marketplace APIs。

## 稳定 Decision 字段

以下 `decision` 字段是稳定字段：

- `id`
- `project_id`
- `capability_id`
- `strategy`
- `preset`
- `selected_provider_id`
- `ranked_provider_ids`
- `metrics`
- `failover_policy`
- `created_at`

## 稳定 Failover Policy 字段

当 `failover_policy` 存在时，以下字段稳定：

- `enabled`
- `max_attempts`
- `retry_on_error_types`
- `retry_on_status_codes`

## 稳定 Usage Event 字段

以下 `usage_events[]` 字段是稳定字段：

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
- `created_at`

稳定 `execution_mode` values：

- `direct`
- `proxy`
- `shadow`
- `replay`

## 稳定顶层 Inspection 字段

以下 `api2agent decision --json` 顶层字段稳定：

- `contract_version`
- `decision`
- `usage_events`
- `usage_event_count`

当前 contract version：

- `decision_usage.v0.1`

## 兼容性规则

API2Agent 后续可以增加新字段，但不能在没有 contract version change 文档的情况下删除或重命名上述稳定字段。

## 为什么重要

API2Agent 经济层必须先有可审计性，之后才能谈 billing：

```text
routing decision
  -> provider attempts
  -> usage events
  -> ledger rows
  -> future billing-ready measurement
```

稳定字段让这条链路可以被测试。

## Ledger Mode Grouping

`api2agent ledger --group-by-mode` 会在 project、capability、provider 之外继续按 `execution_mode` 分组。

这样本地报表可以区分：

- direct local execution
- proxy-controlled execution
- shadow benchmark execution
- replay debug execution

Replay rows 会进入 ledger，但默认不进入 provider routing metrics。

## 稳定 Ledger Row 字段

`api2agent ledger --json` 返回 ledger rows array。

支持的 filters：

- `--project-id`
- `--capability-id`
- `--provider-id`
- `--month`

以下 row fields 是稳定字段：

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

不使用 `--group-by-mode` 时，`execution_mode` 为 `null`。
