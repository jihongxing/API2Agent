# Capability Metrics 与 Routing Dogfood 报告

## 1. 目标

本轮 dogfood 验证 Control Layer 之后的 roadmap 阶段：

```text
usage events
  -> provider metrics
  -> capability comparison
  -> routing decision
```

本轮还不执行被选中的 provider。Routing execution loop 是后续 roadmap phase。

## 2. 设置

Capability：

```text
image_generation
```

Provider candidates：

| Provider | Intent | Estimated Cost |
|---|---|---:|
| `fast_cheap` | lower latency and lower cost | 0.01 |
| `reliable_expensive` | higher success rate | 0.04 |

本轮向 local SQLite usage store 写入 synthetic usage events。

## 3. Metrics

| Provider | Total Calls | Success Rate | Avg Latency | Estimated Cost / Call |
|---|---:|---:|---:|---:|
| `fast_cheap` | 5 | 60% | 740 ms | 0.01 |
| `reliable_expensive` | 5 | 100% | 1560 ms | 0.04 |

## 4. Routing 结果

| Strategy | Selected Provider | 原因 |
|---|---|---|
| `lowest_cost` | `fast_cheap` | observed cost 更低 |
| `lowest_latency` | `fast_cheap` | observed latency 更低 |
| `highest_success_rate` | `reliable_expensive` | observed success rate 更高 |
| `balanced` | `fast_cheap` | 默认权重下 latency/cost 优势足以超过 reliability |

## 5. 观察

### 有效的部分

- Usage events 可以聚合成 provider-level metrics。
- 两个 providers 可以在同一个 capability 下比较。
- Routing strategy 会改变 provider selection。
- `api2agent route` 可以使用 registry + metrics 给 providers 排序。

### 需要产品设计的部分

- 当前默认 `balanced` strategy 会明显偏向低成本和低延迟，因此成功率较低的 provider 也可能胜出。
- 这不一定错误，但必须显式说明。
- 未来 routing policies 需要 named presets，例如：
  - `reliability_first`
  - `cost_first`
  - `latency_first`
  - `balanced`
- Capability comparability 不能只靠相同 `capability_id`，还需要定义 input/output compatibility 和 output quality。

## 6. 结论

Capability Metrics MVP 和 Routing v0 作为 selection primitives 是成立的。

在实现 routing execution loop 前，不要继续写执行逻辑，必须先完成：

1. 定义 routing decision event
2. 文档化 routing policy presets
3. 设计至少一个真实 two-provider capability dogfood
