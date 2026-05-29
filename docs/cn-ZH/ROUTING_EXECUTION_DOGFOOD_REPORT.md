# Routing Execution Dogfood 报告

## 1. 目标

验证最小本地 Routing Execution Loop：

```text
capability registry
  -> provider selection
  -> generated provider runner
  -> API2Agent Proxy
  -> third-party API
  -> output normalization
```

这是 local-only，不是 hosted routing service。

## 2. Capability

```text
public_ip_lookup
```

Provider candidates：

- ipify
- httpbin

两个 providers 都配置了 `output_mapping`，因此 raw outputs 都会 normalize 成：

```json
{
  "ip": "108.174.61.76"
}
```

## 3. 执行结果

### ipify via `cost_first`

Selected provider：

```text
ipify
```

Raw provider body：

```json
{
  "ip": "108.174.61.76"
}
```

Normalized body：

```json
{
  "ip": "108.174.61.76"
}
```

### httpbin via `first`

Selected provider：

```text
httpbin
```

Raw provider body：

```json
{
  "origin": "108.174.61.76"
}
```

Normalized body：

```json
{
  "ip": "108.174.61.76"
}
```

## 4. 有效的部分

- `api2agent call` 可以从 registry metadata 选择 provider。
- 被选中的 generated provider runner 可以通过 API2Agent Proxy 执行。
- Proxy 可以记录 usage events。
- Output normalization 可以把 provider-specific raw bodies 转成统一 capability output shape。
- Routing decision output 包含 selected provider、ranked providers、strategy/preset 和 metrics。

## 5. 剩余问题

- Routing decision events 已返回，但还没有持久化。
- Failover path 有选项，但还没有用真实 failing provider dogfood。
- Provider package paths 目前是 local metadata，还不是 registry-managed artifacts。
- Hosted routing 仍然不在范围内。

## 6. 结论

最小本地 Routing Execution Loop 成立。

下一步符合 roadmap 的工作应该是：

1. 持久化 routing decision events
2. 关联 routing decision events 和 usage events
3. 用一个故意失败的 provider dogfood failover
4. 之后再考虑 hosted routing service design
