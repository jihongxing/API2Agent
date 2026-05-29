# Capability Schema

## 1. 目的

Capability Schema 定义未来可以被比较、路由，并最终市场化的最小单位。

API endpoint 本身不够。Capability 必须描述多个 providers 可以共同 fulfill 的 Agent intent。

## 2. 最小对象

### Capability

```json
{
  "id": "image_generation",
  "name": "Image Generation",
  "description": "Generate an image from a text prompt.",
  "input_schema": {},
  "output_schema": {},
  "safety": "write"
}
```

### Provider Candidate v0.2

```json
{
  "id": "provider_a_image_generation",
  "capability_id": "image_generation",
  "provider_id": "provider_a",
  "tool_id": "generate_image",
  "estimated_cost": 0.02,
  "output_mapping": {}
}
```

### Metrics Snapshot

```json
{
  "capability_id": "image_generation",
  "provider_id": "provider_a",
  "total_calls": 100,
  "successful_calls": 92,
  "failed_calls": 8,
  "success_rate": 0.92,
  "average_latency_ms": 1200,
  "estimated_cost_per_call": 0.02
}
```

## 3. 可比较规则

两个 providers 只有在满足下面条件时，才可以放在同一个 capability 下比较：

- 共享同一个 `capability_id`
- 输入兼容
- 输出兼容
- safety expectation 兼容
- metrics 测量的是同一个 fulfillment intent

不要只因为 endpoints 长得像就比较 providers。

示例：

```text
GET /images/{id}
POST /generate-image
```

它们不自动可比较。前者是 retrieval，后者是 generation。

## 4. Routing 输入

Routing v0 可以使用：

- provider candidates
- usage-derived metrics
- estimated cost
- routing strategy

Routing v0 还不执行被选中的 provider，只做 selection 和 ranking。

## 5. v0 暂不解决什么

Capability Schema 暂不解决：

- arbitrary APIs 的 semantic auto-mapping
- output quality evaluation
- provider onboarding
- pricing contracts
- marketplace trust review
- routing execution

这些要等 schema 稳定并完成 dogfood 后再做。

## 6. v0.2：Output Normalization Metadata

Routing execution 需要稳定的 capability output。不同 providers 可以 fulfill 同一个 capability，但返回不同的 raw response shape。

示例：

```text
Capability: public_ip_lookup
```

ipify 返回：

```json
{
  "ip": "108.174.61.76"
}
```

httpbin 返回：

```json
{
  "origin": "108.174.61.76"
}
```

两者都应该 normalize 成：

```json
{
  "ip": "108.174.61.76"
}
```

所以 provider candidates 需要 `output_mapping`：

```json
{
  "id": "ipify_public_ip",
  "capability_id": "public_ip_lookup",
  "provider_id": "ipify",
  "tool_id": "get",
  "estimated_cost": 0.001,
  "output_mapping": {
    "ip": "$.ip"
  }
}
```

```json
{
  "id": "httpbin_public_ip",
  "capability_id": "public_ip_lookup",
  "provider_id": "httpbin",
  "tool_id": "get_ip",
  "estimated_cost": 0.002,
  "output_mapping": {
    "ip": "$.origin"
  }
}
```

v0.2 支持的 mapping syntax：

- `$` 映射整个 response。
- `$.field` 映射 top-level field。
- `$.a.b.c` 映射 nested field。

v0.2 暂不支持：

- arrays
- filters
- transforms
- type coercion
- fallback expressions

这里刻意保持很小。目标是在不引入 LLM-based response transformation 的情况下，让 routing execution 具备稳定输出。
