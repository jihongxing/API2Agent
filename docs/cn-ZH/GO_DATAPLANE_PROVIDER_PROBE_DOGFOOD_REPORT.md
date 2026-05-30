# Go Data Plane Provider Probe Dogfood 报告

日期：2026-05-30

## 目标

从 Go Data Plane runtime 自身测量 provider reachability。

这一步不做 provider ranking，也不做 marketplace 行为。它只证明 availability 必须从真实 execution runtime 观测。

## 脚本

```text
python scripts/go_dataplane_provider_probe_dogfood.py --output .dogfood/go-dataplane-provider-probe/report.json
```

## 结果

```json
{
  "passed": true,
  "probe_count": 2,
  "reachable_count": 1,
  "checks": {
    "at_least_one_provider_reachable": true,
    "all_results_from_go_runtime": true,
    "all_results_have_events": true
  }
}
```

Provider observations：

```json
[
  {
    "candidate_id": "httpbin_ip_probe_v1",
    "provider_id": "httpbin",
    "reachable": true,
    "status_code": 200
  },
  {
    "candidate_id": "ipify_probe_v1",
    "provider_id": "ipify",
    "reachable": false,
    "status_code": 0,
    "error_type": "PROVIDER_ERROR"
  }
]
```

## 证明了什么

- Provider availability 会因为 execution runtime 不同而不同。
- Go Data Plane 可以记录成功和失败的 provider reachability attempts。
- Provider probe 应先属于 observability，不应该直接进入 marketplace ranking。
