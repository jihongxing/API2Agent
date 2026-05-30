# Go Data Plane Skeleton Plan

状态：planned

日期：2026-05-30

相关文档：

- `docs/cn-ZH/PRODUCTION_ARCHITECTURE_RFC.md`
- `docs/cn-ZH/PYTHON_REFERENCE_MIGRATION_PLAN.md`
- `docs/cn-ZH/API2AGENT_PROTOCOL_V0_2.md`
- `schemas/api2agent/v0.2/protocol.schema.json`

## 1. 目的

这个 plan 定义第一个 Go Data Plane skeleton。

目标不是用 Go 重写完整 Python MVP，而是证明 production hot-path shape：

```text
POST /v1/execute
  -> RequestContext
  -> RoutingDecision
  -> ProviderAdapter
  -> UsageEvent
  -> DecisionLog
```

Skeleton 必须 protocol-first、小而可测。

## 2. 范围

范围内：

- Go Data Plane module
- `/v1/execute` HTTP endpoint
- local static snapshot loading
- deterministic routing stub
- 一个真实 no-auth provider adapter
- append-only event writer
- schema-shaped contract objects
- timeout budget propagation
- snapshot metadata propagation

范围外：

- Control Plane API
- hosted credential vault
- dashboard
- billing
- marketplace
- multi-provider routing optimization
- non-API capability sources

## 3. 建议仓库结构

```text
services/
  data-plane/
    go.mod
    cmd/
      api2agent-dataplane/
        main.go
    internal/
      httpapi/
        execute.go
      protocol/
        models.go
      routing/
        engine.go
      snapshots/
        loader.go
      adapters/
        adapter.go
        ipify.go
      credentials/
        resolver.go
      events/
        writer.go
      config/
        config.go
    testdata/
      snapshots/
        network.public_ip.get.json
```

规则：

- generated 或 manually maintained protocol structs 必须符合 v0.2 semantics
- 不 import Python runtime
- 不隐式依赖本地 Python package internals
- JSON fields 必须保持 protocol-compatible

## 4. Endpoint Contract

初始 endpoint：

```http
POST /v1/execute
Authorization: Bearer <api2agent_project_key>
Content-Type: application/json
```

最小 request：

```json
{
  "project_id": "local",
  "capability_id": "network.public_ip.get",
  "capability_version": "0.1-migrated",
  "input": {},
  "execution_mode": "proxy",
  "client_region": "local",
  "timeout_budget_ms": 5000
}
```

最小 response：

```json
{
  "request_id": "req_...",
  "routing_decision_id": "route_...",
  "usage_event_id": "usage_...",
  "success": true,
  "output": {
    "ip": "127.0.0.1"
  }
}
```

## 5. 第一个 Capability

初始真实 capability：

```text
network.public_ip.get
```

初始 provider：

```text
ipify
```

原因：

- 不需要 auth
- output 稳定
- 已经在 Python MVP 中 dogfood
- 足够简单，适合 dual-run comparison

## 6. Snapshot Model

Control Plane 存在之前，skeleton 使用 local static snapshots。

必须包含的 snapshot fields：

- `snapshot_version`
- `snapshot_fetched_at`
- `snapshot_ttl`
- `snapshot_source`
- capability definition
- provider candidates
- routing policy

规则：

- RoutingDecision 必须记录 `snapshot_version`。
- Skeleton mode 下 snapshot expiration policy 可以先 warning。
- Phase B 不引入 mutable live Control Plane reads。

## 7. Routing Skeleton

初始 routing policy：

```text
first
```

必须包含的 routing fields：

- `request_id`
- `routing_mode`
- `routing_seed`
- `snapshot_version`
- `selected_provider_id`
- `selected_provider_region`

规则：

- 默认 routing mode 是 `deterministic`
- stochastic routing 不属于 skeleton 范围
- routing decisions 是 pre-execution plans

## 8. Timeout Budget

Skeleton 必须显式传递 timeout budget。

字段：

- `execution_timeout_budget_ms`
- `attempt_timeout_ms`
- `attempt_timeout_policy`

初始 policy：

```text
fixed
```

规则：

- provider attempt timeout 不能超过剩余 execution budget
- timeout errors 必须映射到 standardized error records
- timeout budget 必须出现在 safe request metadata 或 decision context 中

## 9. Event Writer

Skeleton 使用 append-only local event writer。

初始 storage：

```text
.api2agent/events/*.jsonl
```

Event objects：

- RequestContext
- RoutingDecision
- UsageEvent
- DecisionLog

Ordering fields：

- `event_sequence_id`
- `parent_attempt_id`

规则：

- event writes 不应该让 provider response 被不必要地阻塞
- JSONL 对 Phase B 足够
- Postgres 属于 Control Plane minimum phase

## 10. Credential Boundary

第一个 provider 是 no-auth。

即使如此，skeleton 也必须定义 credential boundaries：

- credential resolver interface
- usage events 上的 credential reference
- 不记录 raw secret logs
- missing credential error shape

Hosted vault integration 不属于 Phase B。

## 11. Dual-Run Compatibility

Go skeleton 必须支持和 Python 做 dual-run comparison。

对比对象：

- normalized output
- RequestContext
- RoutingDecision
- UsageEvent
- DecisionLog

允许差异：

- IDs 可以不同
- timestamps 可以不同
- implementation metadata 可以不同

必须一致：

- capability ID
- capability version
- provider ID
- selected provider
- success flag
- normalized output schema
- failure 时的 error category

## 12. Test Plan

必须测试：

- `/v1/execute` golden path
- snapshot load and version propagation
- deterministic provider selection
- timeout budget propagation
- UsageEvent emission
- DecisionLog emission
- no raw credential logging

可选测试：

- schema validation against JSON schema
- dual-run comparison fixture with Python output

## 13. Acceptance Criteria

Phase B plan 可以进入实现的条件：

- repository layout 被接受
- first capability/provider 被接受
- endpoint contract 被接受
- event writer behavior 被接受
- snapshot behavior 被接受
- timeout budget behavior 被接受
- 不需要 Control Plane dependency

实现完成条件：

- `go test ./...` 在 `services/data-plane` 内通过
- local `/v1/execute` 返回真实 `network.public_ip.get` result
- RequestContext、RoutingDecision、UsageEvent 和 DecisionLog 被写出
- emitted records 包含 snapshot 和 timeout metadata
- hot path 不需要 Python runtime
