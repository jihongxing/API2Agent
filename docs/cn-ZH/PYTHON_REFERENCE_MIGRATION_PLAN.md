# Python Reference Migration Plan

状态：active

日期：2026-05-30

相关文档：

- `docs/cn-ZH/MVP_EXIT_REVIEW.md`
- `docs/cn-ZH/ARCHITECTURE_DEFINITION_PHASE.md`
- `docs/cn-ZH/PRODUCTION_ARCHITECTURE_RFC.md`
- `docs/cn-ZH/API2AGENT_PROTOCOL_V0_2.md`
- `schemas/api2agent/v0.2/protocol.schema.json`

## 1. 目的

这个 plan 定义 Python MVP 如何从 hot path 退到 reference 和 compatibility 角色。

Python 继续有价值的地方：

- compiler behavior
- local dogfood
- compatibility validation
- protocol regression testing

Python 不应该继续作为 hosted production data plane。

## 2. 迁移原则

迁移本质上是逐步收缩 Python 的职责：

```text
hot path execution
  -> dual-run reference path
  -> compatibility oracle
  -> local dogfood and compiler only
```

迁移必须保留：

- protocol compatibility
- deterministic replay
- usage 和 decision 的可审计性
- dogfood 可比性

迁移不能保留：

- hidden runtime assumptions
- Python 和 Go 同时实现 production logic 造成的重复
- event schema 的长期分叉

## 3. 迁移后 Python 的职责

Python 继续负责：

- OpenAPI/curl compiler
- generated package reference behavior
- protocol conformance tests
- local dogfood harness
- schema validation helpers

Python 停止负责：

- hosted proxy execution
- high-throughput routing
- production credential vault
- production usage ingestion
- long-lived hosted adapter runtime

## 4. 迁移阶段

### Phase 1：冻结 Python Surface

目标：

- 不再扩展新的 Python runtime
- 把 emitted events 锁定到 v0.2 schema
- 保持 Python 作为 compatibility baseline

产物：

- schema-validated usage events
- schema-validated routing decisions
- schema-validated decision logs
- protocol regression tests

### Phase 2：引入 Go Data Plane Skeleton

目标：

- 构建第一个 Go `/v1/execute` 路径
- 支持一个真实 adapter
- 输出和 Python 相同的 contract objects

产物：

- RequestContext creation
- RoutingDecision creation
- UsageEvent append
- snapshot propagation
- timeout budget propagation

### Phase 3：Dual-Run Dogfood

目标：

- 同一个 capability 同时走 Python 和 Go
- 对比 outputs、events 和 latency breakdown

产物：

- identical capability inputs
- comparable normalized outputs
- compatible credential references
- matching ledger aggregation

验收：

- Go 和 Python 输出语义等价的 contract objects
- 任何差异都必须能由 snapshot version 或 adapter version 解释

### Phase 4：把 Hosted Traffic 迁到 Go

目标：

- 把 hosted proxy requests 从 Python hot path 迁走
- 保留 Python 作为 fallback reference

产物：

- Go Edge Proxy
- Go Routing Engine
- Go Provider Adapter runtime
- Control Plane snapshot distribution

迁移规则：

- 按 capability 迁移，不按 user 随机迁移
- region 迁移必须建立在 capability path 稳定之后

### Phase 5：Python 退出 Hot Path

目标：

- Python 不再参与 hosted execution
- Python 只保留 compiler 和 reference 用途

最终 Python 职责：

- local compiler
- dogfood harness
- compatibility oracle
- documentation examples

## 5. 兼容规则

Python 和 Go 必须一致的对象：

- `RequestContext`
- `RoutingDecision`
- `UsageEvent`
- `DecisionLog`
- `LedgerRow`
- `CredentialReference`
- `metrics_window`
- `snapshot_version`

如果 Python 和 Go 在 schema semantics 上不一致，且没有显式 version 理由，这个迁移就是失败的。

## 6. 测试策略

必须做的测试：

- schema conformance tests
- replay equivalence tests
- routing decision equivalence tests
- credential redaction tests
- output normalization tests
- failover parity tests

推荐做的测试：

- golden trace comparison
- region-aware routing comparison
- metrics window comparison

## 7. 退出标准

这个 migration plan 完成时应满足：

- Python 不再承载 hosted production traffic
- Go Data Plane 承担 production hot path
- Python 仍然可作为 reference compiler 和 dogfood harness
- protocol conformance 在两个 runtime 间保持一致
- replay 和 audit output 仍然可解释
