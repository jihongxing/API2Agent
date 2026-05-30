# Location-Aware Schema Dogfood Report

日期：2026-05-30

## 目的

验证 API2Agent 可以持久化 region-aware usage data，并表示 provider region metadata，同时不改变当前 routing behavior。

## Implemented Contract

Usage events 现在支持：

- `client_region`
- `api2agent_region`
- `provider_region`
- `latency_total_ms`
- `latency_network_ms`
- `latency_provider_ms`
- `latency_overhead_ms`

Provider candidates 现在支持：

- `regions`
- `geo_affinity`

Decision dataset contract：

- `DecisionDatasetRecord`

## 结果

- usage store 可以持久化并读取 region fields
- proxy calls 可以从 proxy payloads 记录 region fields
- provider candidates 接受 `regions` 和 `geo_affinity`
- decision dataset records 可以表示 candidates、selected provider、region、latency、cost 和 outcome
- 现有 routing behavior 保持不变

## 测试

```text
pytest tests/test_control_layer.py tests/test_capability_routing.py
33 passed
```

## 产品结论

这是进入 region-aware routing 前正确的第一步。API2Agent 现在可以采集 location-aware execution 所需字段，而不会过早改变 provider selection。
