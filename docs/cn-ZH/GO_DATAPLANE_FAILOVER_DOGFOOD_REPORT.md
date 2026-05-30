# Go Data Plane Failover Dogfood Report

日期：2026-05-30

## 目标

验证 Go Data Plane 能在 primary provider 失败后切到 fallback provider，并且保留 v0.2 execution graph。

## 设置

Capability：

```text
network.public_ip.get
```

Providers：

- `ipify_primary_v1`：本地 fake provider，返回 HTTP 500
- `ipify_fallback_v1`：本地 fake provider，返回 `{ "ip": "203.0.113.99" }`

脚本：

```text
python scripts/go_dataplane_failover_dogfood.py --output .dogfood/go-dataplane-failover/report.json
```

## 结果

```json
{
  "passed": true,
  "checks": {
    "response_success": true,
    "fallback_output": true,
    "two_usage_events": true,
    "first_attempt_failed": true,
    "first_attempt_provider_error": true,
    "second_attempt_succeeded": true,
    "decision_log_success": true,
    "decision_log_references_both_attempts": true,
    "selected_fallback_provider": true
  }
}
```

## 证明了什么

- Go Data Plane 可以在同一个 `RoutingDecision` 下尝试多个 ranked providers。
- 失败 provider attempt 会写入 `UsageEvent`。
- 成功 fallback attempt 会写入独立的 `UsageEvent`。
- `DecisionLog` 会记录最终 outcome，并引用两个 attempts。
- failover 成功时，最终 observation 中的 selected provider 可以不同于 pre-execution primary plan。

## 备注

这次 dogfood 使用本地 fake providers，以隔离 external network instability 对 failover 行为验证的影响。
