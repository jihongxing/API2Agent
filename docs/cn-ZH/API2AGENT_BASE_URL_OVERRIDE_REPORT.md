# API2Agent Base URL Override 报告 v0

日期：2026-05-31

状态：已完成

## 总结

Generated packages 现在可以在 runtime 覆盖 provider base URLs，不需要手改 generated source。

这补齐了 local、staging、regional 和 self-hosted API environments 的真实 onboarding 缺口，同时保持当前 Tooling Re-entry 范围克制：

- API-first only
- 只改 generated package runner behavior
- 不做 workflow engine
- 不做 marketplace 或 billing
- 不做 credential vault

## 改动

### Runtime Overrides

Generated `runner.py` 现在支持：

```bash
API2AGENT_BASE_URL=http://127.0.0.1:9001
```

作为 package-wide base URL override。

也支持 tool-specific override：

```bash
API2AGENT_TOOL_BASE_URL_GET_ITEMS=http://127.0.0.1:9002
```

优先级：

```text
tool-specific env
  -> API2AGENT_BASE_URL
  -> tool.base_url
  -> capability.base_url
```

### Fail-fast Validation

Overrides 必须以 `http://` 或 `https://` 开头。

非法 override 会在任何 direct/proxy provider call 前返回：

```text
invalid_base_url_override
```

### Base Path Preservation

Generated runner 现在拼接 base URLs 和 paths 时会保留 base path prefixes。

示例：

```text
base_url = http://127.0.0.1:9001/staging
path     = /items
result   = http://127.0.0.1:9001/staging/items
```

这避免丢掉 OpenAPI server prefixes，例如 `/v1`。

### Generated README

Generated package READMEs 现在会说明：

- package-wide base URL override
- tool-specific base URL override
- provider-region override 保持不变

## Dogfood

复现命令：

```bash
python scripts/api2agent_base_url_override_dogfood.py
```

产物：

```text
.dogfood/base-url-override/result.json
```

Dogfood flow：

```text
generated OpenAPI package
  -> default direct provider
  -> global base URL override direct provider
  -> tool-specific base URL override direct provider
  -> invalid override fail-fast
  -> proxy call with global override
  -> SQLite usage event with override URL
```

Dogfood checks：

- default direct execution 使用 generated OpenAPI server URL
- `API2AGENT_BASE_URL` 不改源码即可改变 direct provider target
- `API2AGENT_TOOL_BASE_URL_GET_ITEMS` 优先于 global override
- invalid override 在 provider forwarding 前 fail-fast
- proxy execution forward 到 override URL
- proxy usage event 记录 override URL
- provider region 和 no-credential metadata 保持完整
- scope 保持 API-first 和 no-workflow-engine

## 结果

Dogfood 已通过。

关键观测值：

```json
{
  "direct_default_success": true,
  "direct_global_override_success": true,
  "direct_tool_override_success": true,
  "invalid_override_fails_fast": true,
  "proxy_override_success": true,
  "usage_event_url_uses_override": true,
  "provider_region_preserved": true,
  "credential_reference_none": true
}
```

## 为什么重要

Base URL override 降低了真实 API onboarding cost：

- generated packages 可以指向 local mocks、staging、regional hosts 或 self-hosted endpoints
- 开发者不需要在 generation 后 patch generated source
- proxy-mode usage data 保持准确，因为 event 记录的是实际执行 URL

它也服务当前项目优先级：

- 更多真实执行数据
- 更低 API/provider onboarding cost
- 测试 regional 或 local providers 时迭代更快

## 剩余缺口

本报告当时的下一项 Tooling Re-entry 缺口是 write-like operations 的安全手动测试路径。该 slice 现在已完成；详见 `docs/cn-ZH/API2AGENT_MANUAL_WRITE_TEST_PATH_REPORT.md`。

下一项任务：

```text
Large Spec Performance v0
```
