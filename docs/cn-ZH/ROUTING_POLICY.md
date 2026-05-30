# Routing Policy v0

## 1. 目的

Routing Policy v0 定义 API2Agent 如何为一个 capability 选择 provider candidate。

这一阶段只做 provider selection 和 ranking，不执行被选中的 provider。

## 2. Routing Decision Event

每一次 routing selection 都应该可以表示成 routing decision event：

```json
{
  "id": "decision_123",
  "capability_id": "image_generation",
  "strategy": "balanced",
  "preset": "reliability_first",
  "client_region": "cn",
  "selected_provider_id": "provider_a",
  "ranked_provider_ids": ["provider_a", "provider_b"],
  "metrics": [],
  "created_at": "2026-05-30T00:00:00Z"
}
```

这个 event 和 usage event 是分开的。

未来 routing execution 应该可以关联：

```text
routing decision event -> usage event
```

## 3. Strategies

Routing v0 支持：

- `first`
- `random`
- `lowest_cost`
- `lowest_latency`
- `region_aware_latency`
- `highest_success_rate`
- `balanced`

`region_aware_latency` v0 使用 `client_region`、provider `regions` 和 `geo_affinity`。

Ranking order：

1. `regions` 包含 `client_region` 的 providers
2. `geo_affinity=global` 的 providers
3. `geo_affinity=unknown` 的 providers
4. 其他 providers

同一个 region rank 内，策略会优先使用 matching client-region latency metrics，其次使用 aggregate latency metrics，最后是 no-metric fallback。

CLI：

```bash
api2agent route capability-registry.json \
  --capability-id weather.current.get \
  --strategy region_aware_latency \
  --client-region cn \
  --db api2agent-usage.sqlite
```

## 4. Policy Presets

Presets 是建立在 `balanced` 之上的命名权重配置。

| Preset | Success Rate | Latency | Cost | 意图 |
|---|---:|---:|---:|---|
| `balanced` | 0.5 | 0.3 | 0.2 | 通用默认 |
| `reliability_first` | 0.8 | 0.1 | 0.1 | 优先完成 |
| `cost_first` | 0.1 | 0.2 | 0.7 | 优先低成本 |
| `latency_first` | 0.1 | 0.7 | 0.2 | 优先速度 |

CLI：

```bash
api2agent route capability-registry.json \
  --capability-id image_generation \
  --preset reliability_first \
  --db api2agent-usage.sqlite
```

## 5. 当前限制

- success/cost/latency 之外还没有质量评估。
- `region_aware_latency` 是 v0 heuristic，不是 active probing。
- 还没有 safety、compliance、provider allowlists 等 policy constraints。
