# API2Agent Tooling Re-entry Closeout + Phase Review v0

日期：2026-05-31

状态：已完成

## 判断

Tooling Re-entry phase 可以阶段性暂停。

当前 Tooling Layer 已经足够强，可以回到下一项 infrastructure task，或者在你补充新产品需求前暂停实现，不会留下未收口的 hardening backlog。

当时建议的下一项工程任务是：

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```

该 design、CLI implementation、live Postgres dogfood 和 readiness review 现在都已完成。当前下一项工程任务：

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

如果接下来要补充新的产品需求，应先暂停实现并更新 PRD/roadmap，再启动该任务。

## 阶段目标

本次 re-entry 的目标是：

```text
带着 Control/Data Plane 约束回到 API2Agent Tooling，
增加真实执行数据，
降低 API/provider onboarding cost，
提升 response-speed readiness，
同时不变成 workflow engine。
```

对当前 API-first scope 来说，这个目标已经达成。

## 已完成能力

### Baseline and Scope

- Tooling Re-entry Review + Expansion Plan 记录了带约束回到 Tooling Layer 的判断。
- Tooling implementation language decision 确认 Python 是 reference tooling implementation，Go 是 production Data/Control Plane 方向。
- Tooling Baseline Audit 记录了真实 curl/OpenAPI onboarding behavior。

证据：

- 4/4 curl inputs generation 成功。
- 4/4 curl inputs 第一次 direct execution 成功。
- 3/3 no-auth proxy paths 第一次 proxy execution 成功。
- GitHub REST OpenAPI 仍然暴露 large-spec 风险：未过滤 1186 tools，过滤后 3 tools。

### Lower Onboarding Cost

已完成：

- OpenAPI filtering + curl tool naming hardening
- endpoint-level auth inference
- base URL override
- manual write test path
- curl naming residual review

影响：

- mixed public/protected APIs 不再要求先配置 auth 才能测试 public endpoints
- local/staging/regional/self-hosted APIs 可以不 patch generated source 直接测试
- write/delete tests 显式且有 guard
- `api.*` 和 `www.*` 这类 common host 默认不再生成 `api` 这种过泛 capability name
- root-path curl tools 携带 capability intent

### More Real Execution Data

已完成：

- proxy-mode credential dogfood expansion
- generated runner credential intent propagation
- credential、provider region、cost、selected tool 等 proxy usage metadata preservation
- manual write proxy dogfood path

影响：

- generated packages 可以进入 observable proxy execution，且不泄露 raw provider secret
- usage events 保留稳定 tool/provider/capability identity
- write-like tools 可以被有意测试，同时仍然产生 usage evidence

### Faster Response Readiness

已完成：

- generated package provider-region metadata
- generated package latency benchmark helper
- p50/p95 generated package benchmark output
- local/staging/regional endpoints 的 base URL override
- large spec performance 和 inspect/test usability

影响：

- generated packages 现在具备支撑未来 location-aware routing 的 region 和 latency metadata
- 开发者可以比较 direct vs proxy execution timing
- large OpenAPI packages 不再只有 raw endpoint dump，而是有 summary、filtering 和 targeted test paths

## 验收标准复盘

| 标准 | 状态 |
| --- | --- |
| 至少 5 个真实 API onboarding attempts 被文档化 | 通过 |
| generated packages 能不改源码运行 safe read paths | 通过 |
| credentials 允许时 generated packages 能通过 proxy mode | 通过 |
| usage events 包含稳定 identity 和 credential-safe metadata | 通过 |
| benchmark output 包含 latency data | 通过 |
| API-first 和 no-workflow-engine 约束保持明确 | 通过 |

## 验证

最近一次完整验证：

```text
python scripts/api2agent_curl_naming_residual_review.py
python scripts/api2agent_tooling_baseline_audit.py
python -m pytest
169 passed

go test ./...   # services/data-plane
go test ./...   # services/control-plane
```

本阶段新增或复跑的 dogfood scripts：

- `scripts/api2agent_tooling_baseline_audit.py`
- `scripts/api2agent_generated_region_metadata_dogfood.py`
- `scripts/api2agent_proxy_credential_dogfood.py`
- `scripts/api2agent_generated_package_latency_benchmark_dogfood.py`
- `scripts/api2agent_endpoint_auth_inference_dogfood.py`
- `scripts/api2agent_base_url_override_dogfood.py`
- `scripts/api2agent_manual_write_test_path_dogfood.py`
- `scripts/api2agent_large_spec_performance_dogfood.py`
- `scripts/api2agent_curl_naming_residual_review.py`

## 剩余风险

这些不阻塞阶段收口，但需要保持可见：

- Large OpenAPI specs 默认仍允许 unfiltered generation；API2Agent 会 warning 和引导，但不会自动切片。
- Generated package UX 仍然是 CLI/docs-first，不是 polished hosted onboarding UI。
- Real API dogfood coverage 有价值，但规模仍然小。
- Generated package runtime 仍然是 Python reference tooling；production neutrality 依赖 JSON/YAML artifacts 和 Go plane compatibility。
- Tooling 按设计仍不支持 workflow、function、database、human task 等 non-API sources。
- Hosted Control Plane write-side mutation 仍然暂停，直到 import/replace transaction design 完成。

## 保持的非目标

本阶段没有实现：

- workflow engine
- non-API runtime
- marketplace
- billing
- credential vault
- hosted SaaS onboarding
- provider settlement

## 收口判断

本阶段达成了预期 re-entry：

```text
API input
  -> cheaper generated package
  -> safer direct/proxy execution
  -> better metadata
  -> more observable calls
```

建议：

1. 暂停 Tooling Re-entry。
2. 保留当前 reports 作为 v0.1-alpha Tooling evidence set。
3. 如果没有新的产品需求要先补充，回到此前暂停的 Control Plane write-side design。

当前下一项任务：

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```
