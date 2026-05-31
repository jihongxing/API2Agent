# Go Control Plane Persistence 阶段复盘

日期：2026-05-31

状态：已完成

判断：API2Agent 已经可以规划第一项 runtime persistence implementation slice，但还不应该进入 hosted public persistence、registry mutation APIs、vault、billing 或 marketplace 工作。

## 1. 复盘范围

这次复盘关闭的是 local Control Plane persistence planning checkpoint：

```text
Control Plane service boundary
  -> persistent registry design
  -> persistent schema/load-parity contract
  -> runtime persistence readiness decision
```

这次复盘不实现 `PostgresStore.Load(ctx)`。

## 2. 已完成的 Primitives

当前项目已经具备：

- Go Data Plane local execution and observability primitive
- Protocol v0.2 execution graph conformance checks
- durable local event ingestion
- retry/failover、timeout budget、snapshot freshness、quota 和 credential config gates
- Go Control Plane local registry model
- `registry.Store` read boundary
- `registry.FileStore` 作为当前默认 store
- 带 version policy 和 registry fingerprint 的 snapshot export
- snapshot artifact manifest 和 digest validation
- local snapshot distribution 和 atomic publish
- 带 admin auth guard 的 local Control Plane service API
- persistent registry store design
- persistent registry state 的 Postgres schema draft
- file registry 到 persistent rows 的映射
- canonical registry ordering helper 和 regression tests

## 3. 代码边界证据

当前代码确认了这个边界：

- `services/control-plane/internal/registry/store.go` 只定义 read-side `Store` interface。
- `FileStore` 仍然是 runtime implementation。
- `services/control-plane/internal/registry/persistent_schema.go` 只把 registry data 映射成 persistent row shapes，不打开数据库连接。
- `services/control-plane/schema/postgres/001_persistent_registry_store.sql` 定义第一版 schema draft，但没有接入 service runtime。

这说明项目是有意停在 schema/load-parity，而不是已经进入 runtime persistence。

## 4. 需求复核

确认继续有效的 active requirements：

- API2Agent 仍然坚持 API-first。
- Marketplace 仍然是远期目标，不进入当前 active implementation scope。
- Runtime persistence 必须保持 Data Plane snapshot contract 不变。
- 在 Postgres-backed store 证明 load/export parity 前，`FileStore` 仍然是默认 store。
- Credential secrets 不能进入 registry tables。
- Receipt/trust 和 Edge-Mesh privacy strategy 作为未来约束保留，但不进入当前 runtime scope。

本次复盘没有接受任何会绕过 runtime persistence readiness 的新实现需求。

## 5. 已准备好

项目可以进入很窄的 `PostgresStore.Load(ctx)` 规划/实现切片，因为：

- schema shape 已存在
- deterministic canonical mapping 已存在
- registry validation 已经会在 loaded registries 上运行
- snapshot export callers 依赖 `registry.Store`，而不是 `FileStore`
- service API 已经接受 `registry.Store`
- schema/load-parity tests 已用现有 fixture 通过

## 6. 尚未准备好

项目还不适合进入更宽的 hosted persistence，因为仍然缺少：

- live Postgres-backed `Store` implementation
- migration runner
- database-backed import fixture 或 seed command
- transaction-level load tests
- 基于真实数据库的 dual-store snapshot parity test
- artifact export 时持久化 `registry_revisions`
- publish 时持久化 `snapshot_artifact_publications`
- 持久化 `admin_audit_events`
- per-project hosted authorization
- KMS-backed credential vault
- registry mutation HTTP APIs
- remote artifact storage compare-and-swap protocol

## 7. Readiness Decision

下一项工程任务应该是：

```text
Go Control Plane PostgresStore Load Parity v0
```

这应该是最小 runtime persistence 切片。

## 8. 推荐下一项切片

范围：

1. 在现有 read interface 后面增加 Postgres-backed `registry.Store` implementation。
2. 保持 `FileStore` 为默认 runtime store。
3. 如果项目环境允许，增加 local database test fixture 或 test container strategy。
4. 把现有 `network.public_ip.get` registry fixture import 到 persistent schema。
5. 从 Postgres 加载 registry，并构造同样的 in-memory `Registry` shape。
6. 验证 `FileStore` 和 `PostgresStore` 在 canonicalization 后生成等价 snapshot 和 registry fingerprint。

退出标准：

- `PostgresStore.Load(ctx)` 可以读取 valid active registry view。
- 现有 fixture 可以被 persistent schema 表达。
- File 和 Postgres 路径生成等价 snapshot contract output。
- `FileStore` 仍然是默认 store。
- 不包含 registry mutation API、hosted deployment、vault、billing 或 marketplace 工作。

## 9. 战略判断

Control Plane 已经从 local file/service mechanics 进入 durable state readiness。

下一阶段的关键问题不再是：

```text
Can the Control Plane define a persistent registry schema?
```

这已经被证明。

下一阶段的关键问题是：

```text
Can the Control Plane load durable registry state without changing the Data Plane contract?
```

这才是正确的下一项工程切片。
