# API2Agent Manual Write Test Path 报告 v0

日期：2026-05-31

状态：已完成

## 总结

Generated packages 现在为 write-like API operations 提供了安全、显式的手动测试路径。

默认 generated smoke tests 仍然只执行 read-only 工具。POST、PUT、PATCH 和 DELETE tools 不会被执行，除非开发者通过 CLI 或环境变量 guard 明确 opt in。

这保持了 Tooling Re-entry 的范围约束：

- API-first only
- 只改 generated package test behavior
- 不做 workflow engine
- 不做 marketplace 或 billing
- 不做 credential vault

## 改动

### Generated Manual Test

Generated packages 现在包含：

```text
manual_write_test.py
```

Generated package 仍然包含 read-only：

```text
smoke_test.py
```

默认行为保持不变：

```bash
api2agent test .
```

这只会运行 read-only smoke test。

### 显式 Opt-in

Write/delete 测试需要：

```bash
api2agent test . --allow-write
```

CLI 随后运行 `manual_write_test.py`，并注入：

```bash
API2AGENT_ALLOW_WRITE_TEST=1
```

如果直接运行 `manual_write_test.py` 但没有 guard，会以退出码 `2` 退出。

### Write-like Selection

Manual test 会选择第一个 safety level 为以下类型的 generated tool：

```text
write
delete
```

Generated request examples 现在支持 object 和 array schemas，因此 required JSON bodies 可以不手改 generated source 就被执行。

## Dogfood

复现命令：

```bash
python scripts/api2agent_manual_write_test_path_dogfood.py
```

产物：

```text
.dogfood/manual-write-test-path/result.json
```

Dogfood flow：

```text
write-only OpenAPI package
  -> default api2agent test
  -> no provider call
  -> api2agent test --allow-write direct
  -> provider POST
  -> api2agent test --allow-write proxy
  -> provider POST
  -> SQLite usage event
```

Dogfood checks：

- default smoke test 成功，且不会调用 provider
- default output 提示不存在 read-only endpoint
- direct `--allow-write` 调用 provider 一次
- proxy `--allow-write` 第二次调用 provider
- 两次 provider calls 都是 `POST /items`
- generated example body 是 `{"name": "example", "quantity": 1}`
- proxy mode 精确记录一条 usage event
- usage event 保留 `tool_id`、`provider_region`、estimated cost 和 no-credential attribution
- scope 保持 API-first 和 no-workflow-engine

## 结果

Dogfood 已通过。

关键观测值：

```json
{
  "default_smoke_test_did_not_call_provider": true,
  "direct_allow_write_called_provider_once": true,
  "provider_called_twice_after_opt_in": true,
  "proxy_usage_event_recorded": true,
  "proxy_usage_event_write_tool": true,
  "proxy_usage_event_provider_region": true,
  "proxy_usage_event_estimated_cost": true,
  "proxy_usage_event_credential_none": true
}
```

## 为什么重要

这降低了 onboarding cost，同时不削弱安全边界：

- 开发者可以不改 generated code 就 dogfood write-only APIs
- accidental generated smoke-test writes 仍然被阻止
- 明确批准的 write tests 仍然能进入 proxy usage data
- credential-safe metadata 和 provider-region attribution 保持完整

它也服务当前 Tooling Layer 目标：

- 更多真实执行数据
- 更低 API/provider onboarding cost
- 从 read-only APIs 安全扩展到真实 operational APIs

## 剩余缺口

下一项 Tooling Re-entry 缺口是 large OpenAPI performance 和 scale control。

下一项任务：

```text
Large Spec Performance v0
```
