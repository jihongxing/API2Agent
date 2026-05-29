# Provider Registry Contract

## 范围

这份文档定义以下本地命令使用的稳定 provider registry 字段：

- `api2agent route`
- `api2agent call`

不定义 hosted registry APIs、provider onboarding APIs、marketplace APIs、payment APIs 或 revenue share mechanics。

## Contract Version

当前 contract version：

- `provider_registry.v0.1`

如果省略 `contract_version`，API2Agent 会为了本地兼容把 registry 当作 `provider_registry.v0.1`。

不支持的 contract version 必须在 routing 前失败。

## Registry Shape

```json
{
  "contract_version": "provider_registry.v0.1",
  "providers": []
}
```

## 稳定 Provider 字段

以下 provider 字段是稳定字段：

- `id`
- `capability_id`
- `provider_id`
- `tool_id`
- `estimated_cost`
- `output_mapping`
- `metadata`

## 稳定 Metadata 字段

以下 `metadata` 字段对本地 execution 稳定：

- `package_dir`

后续可以增加额外 metadata fields。

## Example

```json
{
  "contract_version": "provider_registry.v0.1",
  "providers": [
    {
      "id": "ipify_public_ip",
      "capability_id": "public_ip_lookup",
      "provider_id": "ipify",
      "tool_id": "get",
      "estimated_cost": 0.001,
      "output_mapping": {
        "ip": "$.ip"
      },
      "metadata": {
        "package_dir": ".dogfood/ipify"
      }
    }
  ]
}
```

## 兼容性规则

API2Agent 后续可以增加 optional fields，但不能在没有 documented contract version change 的情况下删除或重命名上述稳定字段。

## Inspection

本地检查 registry：

```bash
api2agent registry capability-registry.json --json
```

稳定 inspection 字段：

- `contract_version`
- `provider_count`
- `capability_counts`
- `warnings`
- `naming_warnings`
- `providers`

Warnings 对 `api2agent registry` 是提示信息。

`naming_warnings` 在 v0.1-alpha 阶段也是提示信息。它会报告不符合以下规则的 capability IDs：

```text
<domain>.<resource>.<action>
```

在 alpha naming rule 逐步采用期间，legacy capability IDs 仍然可以执行。

对于 `api2agent call`，如果请求的 capability 对应 provider 缺少 local package directory 或 `runner.py`，会在 execution 前失败。

Warning shape：

```json
{
  "severity": "error",
  "code": "missing_runner",
  "provider_id": "ipify",
  "message": "runner not found at .dogfood/ipify/runner.py"
}
```

Severity levels：

- `info`: 不影响 execution 的上下文信息
- `warning`: 可疑 metadata，但不阻止 execution
- `error`: 无效 local execution metadata，会阻止 `api2agent call`

`api2agent route --json` 和 `api2agent call --json` 会包含：

- `registry_contract_version`
