# Location-Aware Routing Strategy

## 为什么重要

API2Agent 不应该只回答：

- 哪个 provider 更稳定？
- 哪个 provider 更便宜？

它还必须回答：

- 对这个位置的 Agent 来说，哪个 provider 更快？

API 无处不在。运行在中国、美国、欧洲或其他区域的 Agent，访问同一个 provider 时会看到完全不同的网络路径。全局平均 latency 可能掩盖某个区域真正最优的 provider。

## 战略优先级调整

API2Agent 应提高两个目标的权重：

1. 拥有最多真实执行数据。
2. 保持最低 API 接入成本。

这两个目标是同一个飞轮的两端：

```text
最低接入成本
  -> 更多 APIs/providers 接入
  -> 更多真实调用
  -> 更丰富的 decision dataset
  -> 更好的 routing
  -> 更高成功率 / 更低成本 / 更低延迟
  -> 更强 developer pull
  -> 更多 APIs/providers 接入
```

## Latency Model

不要只把速度建模为一个数字。

Total latency 应该拆成：

```text
total_latency =
  network_rtt
  + provider_processing_latency
  + api2agent_overhead
```

v0.1 仍然保留 `latency_ms` 作为稳定 aggregate field。Local schema 现在也支持 optional breakdown fields，为未来 routing 做准备。

## Region Model

最小 region vocabulary：

- `us-east`
- `us-west`
- `eu-west`
- `ap-east`
- `cn`
- `unknown`

Usage events 现在可以包含：

```json
{
  "client_region": "cn",
  "api2agent_region": "ap-east",
  "provider_region": "us-east",
  "latency_total_ms": 320,
  "latency_network_ms": 200,
  "latency_provider_ms": 100,
  "latency_overhead_ms": 20
}
```

## Provider Metadata

Provider registry entries 现在可以包含：

```json
{
  "provider_id": "example_cn",
  "regions": ["cn"],
  "geo_affinity": "regional"
}
```

稳定的 `geo_affinity` values：

- `global`
- `regional`
- `cn-only`
- `unknown`

## Routing Implication

Latency 应变成 region-aware：

```text
latency = f(client_region, provider_region)
```

Balanced routing 应逐步演进成 multidimensional score：

```text
score =
  success_weight * success_score
  + cost_weight * cost_score
  + latency_weight * region_aware_latency_score
```

当前 `lowest_latency` strategy 可以继续作为本地 aggregate strategy。下一版应该引入 region-aware latency strategy。

## Decision Dataset

Usage logs 不够。

真正的战略资产是 decision dataset：

```json
{
  "request_id": "req_123",
  "capability_id": "weather.current.get",
  "client_region": "cn",
  "candidate_providers": ["provider_us", "provider_cn"],
  "selected_provider": "provider_cn",
  "routing_strategy": "balanced",
  "success": true,
  "latency_total_ms": 40,
  "estimated_cost": 0.001
}
```

这是未来 routing learning、marketplace ranking 和 active optimization 依赖的数据资产。

## Active Probing

历史 latency 会过期。

未来 API2Agent 应支持 active probing：

- scheduled health checks
- regional latency probes
- provider availability checks
- stale metric detection

在 local schema 和 routing contract 清晰前，不应该先实现这层。

## Product Direction

长期目标不只是 "API to Agent"。

更强的目标是：

> 面向 Agent 的全球 API routing network。

近期实现应保持聚焦：

1. 定义 region-aware usage fields。已完成。
2. 为 provider metadata 增加 region information。已完成。
3. 定义 decision dataset contract。已完成。
4. 增加 region-aware routing strategy。
5. 用 same capability、different provider regions、different outcomes 做 dogfood。
