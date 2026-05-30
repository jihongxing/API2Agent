# Go Data Plane Consolidation Hardening v0 报告

日期：2026-05-30

## 目标

在进入 hosted control plane 工作前，补齐 `docs/cn-ZH/GO_DATAPLANE_STAGE_REVIEW.md` 中识别出的 hardening gaps。

## 已完成

### Reusable Protocol Conformance Validator

Protocol conformance 现在不再只存在于 `execute_test.go`。

新增：

- `services/data-plane/internal/conformance`
- `services/data-plane/cmd/api2agent-conformance`

validator 会检查 JSONL event envelopes，并基于以下 schema 校验 records：

```text
schemas/api2agent/v0.2/protocol.schema.json
```

### Dogfood Event Conformance

durable event 和 real external retry dogfood scripts 现在会构建并运行 `api2agent-conformance`。

两个报告都会包含：

```json
{
  "protocol_conformance": true
}
```

### Event Write Failure Policy

Go Data Plane 现在对 execution graph records 采用 fail-closed event writes。

如果关键 event 无法写入，`/v1/execute` 会返回：

```json
{
  "success": false,
  "error": {
    "error_type": "EVENT_WRITE_FAILED",
    "error_scope": "platform"
  }
}
```

这样可以避免 execution response 成功，但 audit / usage records 静默缺失。

### Runtime Provider Availability Probe

新增：

```text
python scripts/go_dataplane_provider_probe_dogfood.py --output .dogfood/go-dataplane-provider-probe/report.json
```

probe 会从 Go Data Plane runtime 测量 provider reachability，而不是依赖文档或另一个客户端的假设。

报告：

```text
docs/cn-ZH/GO_DATAPLANE_PROVIDER_PROBE_DOGFOOD_REPORT.md
```

## 非目标

本轮 hardening 不新增：

- hosted database
- queue-backed ingestion
- billing
- marketplace ranking
- provider onboarding portal
- workflow runtime

## 推荐下一步

下一项实现 slice 应该是：

```text
Timeout Budget Semantics v0
```

原因：

- 真实外部 dogfood 已经出现较长 wall-clock execution time
- 当前 timeout budget 是 per attempt 维度
- Agent 需要可预测的 total request latency
