# Go/Python Dual-Run Dogfood Report

日期：2026-05-30

## 目标

验证 Python reference path 和 Go Data Plane skeleton 是否能执行同一个 capability，并产生语义兼容的结果。

## 设置

Capability：

```text
network.public_ip.get
```

Provider：

```text
ipify
```

Dogfood mode：

- local fake ipify-compatible provider
- deterministic response：`{ "ip": "203.0.113.42" }`
- Python generated package 通过 `execute_capability` 执行
- Go Data Plane 通过 `/v1/execute` 执行

脚本：

```text
python scripts/dual_run_go_python_public_ip.py --output .dogfood/go-python-dual-run/report.json
```

## 结果

```json
{
  "passed": true,
  "comparisons": {
    "same_success": true,
    "same_output": true,
    "same_capability_id": true,
    "same_provider_id": true,
    "go_has_request_context": true,
    "go_has_routing_decision": true,
    "go_has_usage_event": true,
    "go_has_decision_log": true,
    "go_has_snapshot_version": true
  }
}
```

## 证明了什么

- Python 和 Go 可以执行同一个 capability ID。
- 两条路径可以 normalize 成相同 output shape。
- Go 可以输出 v0.2 execution graph seed：
  - RequestContext
  - RoutingDecision
  - UsageEvent
  - DecisionLog
- Go routing decisions 包含 snapshot version metadata。

## 备注

这次 dogfood 使用 local fake provider，避免外部网络波动。此前 Go 进程直接访问真实 `api.ipify.org` 时在本地环境被拒绝，但 PowerShell 可以访问。local dual-run 可以把 protocol compatibility 和 provider network behavior 隔离开。
