# 真实 Two-Provider Dogfood 计划

## 1. 目标

在实现 routing execution loop 前，API2Agent 需要一个真实 capability + 两个真实 providers 的 dogfood。

这用于验证 capability abstraction 不只是 synthetic demo。

## 2. 候选 Capability

Capability：

```text
public_ip_lookup
```

Agent intent：

> 返回调用者的 public IP address。

为什么选择这个 capability：

- 不需要 API key
- read-only，安全
- 存在两个公开 providers
- 输出 schema 简单但不完全一致，会暴露 normalization design

## 3. Providers

### Provider A：ipify

```text
GET https://api.ipify.org?format=json
```

示例输出：

```json
{
  "ip": "203.0.113.10"
}
```

### Provider B：httpbin

```text
GET https://httpbin.org/ip
```

示例输出：

```json
{
  "origin": "203.0.113.10"
}
```

## 4. 需要的标准化输出

两个 providers 都应该 normalize 成：

```json
{
  "ip": "203.0.113.10"
}
```

这会暴露下一个产品要求：provider candidates 需要 output normalization metadata，routing execution 才能干净。

## 5. Dogfood 步骤

1. 从两个 curl commands 生成 packages。
2. 两个 package 都通过 API2Agent Proxy 调用。
3. 把 usage metrics 记录到 `public_ip_lookup` 下。
4. 创建包含两个 candidates 的 provider registry。
5. 运行 routing strategies。
6. 确认 strategy 会改变 selected provider。

## 6. 预期学习

本轮 dogfood 要回答：

- 两个真实 API 能不能映射到同一个 capability？
- 需要什么 normalization metadata？
- metrics 能不能公平比较真实 providers？
- routing execution loop 前还必须补什么？
