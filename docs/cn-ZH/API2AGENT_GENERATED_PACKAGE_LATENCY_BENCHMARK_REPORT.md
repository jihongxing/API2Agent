# API2Agent Generated Package Latency Benchmark Helper 报告 v0

日期：2026-05-31

状态：已完成

## 总结

Generated packages 现在有了可复用的 latency benchmark helper 和 CLI command，可以重复测量 direct/proxy timing。

这补齐了当前 Tooling Re-entry 的 speed-readiness 缺口，而且不扩大范围：

- API-first only
- 不做 workflow engine
- 不做 marketplace 或 billing
- 不做 credential vault
- 不新增 provider runtime

## 改动

### Python Helper

新增：

```python
from api2agent.benchmark import run_generated_package_latency_benchmark
```

Helper 接受 generated package directory、tool name、params、iteration count 和可选 proxy URL。它会返回：

- direct-mode run stats
- 提供 `proxy_url` 时的 proxy-mode run stats
- success rate
- p50 latency
- p95 latency
- 每次运行的 status、error type、latency 和 usage event id
- generated capability provider-region metadata

### CLI Command

新增：

```bash
api2agent benchmark-package ./api2agent-output \
  --tool get_items \
  --iterations 3 \
  --proxy-url http://127.0.0.1:8765 \
  --provider-region local \
  --json
```

该命令可以跑 direct mode、proxy mode，或两者同时跑。

## Dogfood

复现命令：

```bash
python scripts/api2agent_generated_package_latency_benchmark_dogfood.py
```

产物：

```text
.dogfood/generated-package-latency-benchmark/result.json
```

Dogfood flow：

```text
generated curl package
  -> direct benchmark loop
  -> local API2Agent proxy benchmark loop
  -> SQLite proxy usage events
  -> p50/p95 report
```

Dogfood checks：

- direct mode 跑了 3 次成功调用
- proxy mode 跑了 3 次成功调用
- direct 和 proxy stats 都包含 p50/p95 latency
- proxy results 包含 usage event ids
- proxy usage events 记录 `provider_region == "local"`
- scope 保持 API-first 和 no-workflow-engine

## 结果

Dogfood 已通过。

关键观测值：

```json
{
  "direct_successful_runs": 3,
  "proxy_successful_runs": 3,
  "proxy_usage_event_count": 3,
  "provider_region": "local"
}
```

## 为什么重要

Tooling Layer 现在有了 first-class generated package latency measurement，而不是把这段逻辑藏在临时 audit scripts 里。

这直接服务当前 API2Agent 目标：

- 更多真实调用数据：proxy benchmark runs 会产生 usage events
- 更低接入成本：generated packages 不需要手改源码就能 benchmark
- 更快响应：每个 generated tool 都能看到 direct/proxy p50 和 p95

## 剩余缺口

下一项 Tooling Re-entry 缺口回到 onboarding cost：endpoint-level auth inference。

下一项任务：

```text
Endpoint-level Auth Inference v0
```
