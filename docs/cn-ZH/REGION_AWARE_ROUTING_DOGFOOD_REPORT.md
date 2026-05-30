# Region-Aware Routing Dogfood Report

日期：2026-05-30

## 目的

验证 API2Agent 可以针对同一个 capability，基于 client-region affinity 选择 provider，而不是只依赖全局 latency、cost 或 success rate。

## 场景

Capability：

- `weather.current.get`

Providers：

- `weather_us`
  - `regions`: `["us-east"]`
  - `geo_affinity`: `regional`
- `weather_cn`
  - `regions`: `["cn"]`
  - `geo_affinity`: `regional`

Routing policy：

- strategy：`region_aware_latency`
- client region：`cn`

预期结果：

- 选择 `weather_cn`
- 在 routing decision 中持久化 `client_region=cn`

## 结果

- `region_aware_latency` 会把 `regions` 命中 client region 的 provider 排在最前。
- 存在 matching client-region latency metrics 时会优先使用它。
- 没有 region-specific metrics 时，会 fallback 到 aggregate latency metrics。
- `api2agent route --client-region cn --strategy region_aware_latency --json` 返回 `weather_cn`。
- 存储后的 routing decision 保留了 `client_region=cn`。
- `api2agent call --client-region` 现在也会把相同 policy 带入 execution decision。

## 测试

```text
pytest tests/test_capability_routing.py tests/test_control_layer.py
36 passed

pytest
139 passed
```

## 产品认知

这验证了 location-aware execution 的第一个可运行步骤。API2Agent 现在可以把 region metadata 和 regional latency observations 转化成可审计的 provider decision，同时保持 v0.1-alpha 足够简单。

下一次 dogfood 应该使用 same-capability registry，通过真实 provider calls 或模拟 regional latency snapshots，对比 selected provider、ranked providers、latency、cost 和 success outcome，并沉淀为 decision dataset record。
