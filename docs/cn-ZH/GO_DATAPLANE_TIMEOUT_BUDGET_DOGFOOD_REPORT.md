# Go Data Plane Timeout Budget Dogfood 报告

日期：2026-05-30

## 目标

验证 Go Data Plane 是否把 `timeout_budget_ms` 当作 request-level total deadline，而不是每个 provider attempt 都重新获得一份完整 timeout。

这很重要，因为 failover 应该提升可靠性，但不能把 Agent 感知到的最大延迟成倍放大。

## 语义

`timeout_budget_ms` 现在表示：

```text
Agent request 开始
  -> 创建 total deadline
  -> 每个 provider attempt 只能使用剩余预算
  -> 如果预算耗尽，则不再尝试 fallback
```

每条 `UsageEvent.request_metadata` 会记录：

- `total_timeout_budget_ms`
- `attempt_timeout_budget_ms`
- `remaining_timeout_budget_ms`
- `timeout_budget_policy: "total_deadline"`

最终 `DecisionLog.routing_context` 会记录：

- `total_timeout_budget_ms`
- `remaining_timeout_budget_ms`
- `timeout_budget_exhausted`
- `timeout_budget_policy`

## Dogfood 命令

```bash
python scripts/go_dataplane_timeout_budget_dogfood.py \
  --output .dogfood/go-dataplane-timeout-budget/report.json
```

脚本会构建：

- `api2agent-dataplane`
- `api2agent-conformance`

然后运行两个确定性的本地 provider 场景，并基于 Protocol v0.2 校验 emitted JSONL events。

## 场景 1：预算耗尽阻止 Fallback

设置：

- primary provider sleep 时间超过 total request budget
- fallback provider 健康
- total budget 是 `50ms`

观察结果：

- response 以 `TIMEOUT` 失败
- primary provider 被调用一次
- fallback provider 没有被调用
- 写入一条 `UsageEvent`
- `DecisionLog.outcome` 是 `failure`
- `timeout_budget_exhausted` 是 `true`
- Protocol v0.2 conformance 通过

这证明 primary 消耗 request budget 后，failover 不会重新拿到一份完整 timeout。

## 场景 2：快速失败允许 Fallback

设置：

- primary provider 立即返回 HTTP 500
- fallback provider 健康
- total budget 是 `1000ms`

观察结果：

- response 成功
- primary provider 被调用一次
- fallback provider 被调用一次
- 写入两条 `UsageEvent`
- `DecisionLog.outcome` 是 `success`
- fallback provider 被选中
- `timeout_budget_exhausted` 是 `false`
- Protocol v0.2 conformance 通过

这证明当第一个 provider 快速失败且仍有预算时，failover 仍然可用。

## 结果

Timeout Budget Semantics v0 通过。

Go Data Plane 现在具备可预测的 request-level latency 语义，同时保留了有剩余时间时的 retry/failover 能力。

## 非目标

本切片不包含：

- queue-backed event ingestion
- adaptive timeout allocation
- per-provider timeout tuning
- race mode timeout semantics
- hosted control plane policy management
