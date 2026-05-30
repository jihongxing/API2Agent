# Go Data Plane 真实外部 Provider Retry Dogfood 报告

日期：2026-05-30

## 目标

验证 Go Data Plane 能否在真实外部 provider endpoints 上做 retry/failover：先失败的 `httpbin` status endpoint，再成功的 `httpbin` IP fallback。

## 设置

Capability：

```text
network.public_ip.get
```

Providers：

- `httpbin_real_500_v1`
  - source: `https://httpbin.org/status/500`
  - 预期结果：HTTP 500
- `httpbin_ip_real_v1`
  - source: `https://httpbin.org/ip`
  - output mapping：`ip <- $.origin`

脚本：

```text
python scripts/go_dataplane_real_external_provider_retry_dogfood.py --output .dogfood/go-dataplane-real-external-retry/report.json
```

## 结果

```json
{
  "passed": true,
  "checks": {
    "response_success": true,
    "normalized_output_has_ip": true,
    "two_usage_events": true,
    "first_attempt_failed": true,
    "first_attempt_provider_error": true,
    "second_attempt_succeeded": true,
    "decision_log_success": true,
    "decision_log_references_both_attempts": true,
    "selected_fallback_provider": true,
    "event_order_is_graph": true
  }
}
```

Attempt summary：

```json
[
  {
    "candidate_id": "httpbin_real_500_v1",
    "provider_id": "httpbin",
    "status_code": 500,
    "success": false,
    "error_type": "PROVIDER_ERROR"
  },
  {
    "candidate_id": "httpbin_ip_real_v1",
    "provider_id": "httpbin",
    "status_code": 200,
    "success": true,
    "error_type": null
  }
]
```

## 证明了什么

- Go Data Plane 可以在真实外部 provider endpoints 之间完成 failover。
- 第一次 provider attempt 会被记录成失败的 `UsageEvent`。
- fallback provider attempt 会被记录成第二条 `UsageEvent`。
- 最终 `DecisionLog` 会引用这两个 attempt。
- 最终输出仍然保持标准化的 `{"ip": ...}` 形态。

## 备注

这是 Go Data Plane 第一次真实外部 retry/failover dogfood。它仍然是本地执行路径，不是 hosted control plane，也不是 billing 路径。

更早一次尝试用 `api.ipify.org` 作为 fallback 时，本地 Go 进程被远端主动断开连接。这个失败本身也有价值：外部 API 的可用性必须从真实 execution runtime 测量，不能只根据文档假设。
