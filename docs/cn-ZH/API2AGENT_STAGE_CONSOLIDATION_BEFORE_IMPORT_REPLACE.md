# API2Agent Import/Replace 前阶段总结与加固 v0

日期：2026-05-31

状态：complete

## 决策

API2Agent 可以进入：

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```

但下一项任务必须从已经加固过的阶段边界出发，而不是重新打开一个空白设计面。

本 review 的目标，是把 Tooling Re-entry 回切到 Go Control Plane write-side design 之前的状态、约束和风险钉牢。

## 当前阶段

项目现在已经有三个稳定的本地基础：

1. API-first Tooling Layer
2. Go Data Plane local production primitive
3. Go Control Plane persistent registry read/audit primitive

这些已经足够进入第一个受控的 persistent registry mutation path 设计。

但这不意味着现在可以扩展到 hosted product、marketplace、billing、vault、workflow runtime 或 granular provider onboarding APIs。

## 阶段状态汇总

### Tooling Layer

状态：已经足够稳定，可以暂停。

证据：

- curl 和 OpenAPI onboarding paths 已 dogfood。
- generated packages 支持 direct 和 proxy execution。
- generated packages 保留 provider region、credential intent、cost hints 和 selected tool metadata。
- large OpenAPI specs 已有 parse-time filters、inspect summaries 和 targeted test paths。
- write/delete testing 需要显式 opt-in。
- Python 仍然是 Tooling reference implementation 和 local dogfood harness。

加固含义：

下一项 Control Plane write-side design 不能要求 Tooling 变成 hosted-only、Go-only 或 workflow-native。

### Go Data Plane

状态：local production primitive 已经足够稳定，可以依赖 snapshots。

证据：

- Protocol v0.2 execution graph records 已输出并通过验证。
- timeout budget、quota、credential config、snapshot freshness、snapshot reload、retry/failover 和 attempt correlation semantics 已 dogfood。
- event ingestion 是 durable JSONL，并支持 sequence recovery。
- snapshot reload 失败时会保留 previous snapshot active。

加固含义：

下一项 registry mutation path 必须保持 snapshot compatibility、deterministic registry fingerprints、strict metadata、content digest validation 和 reload-safe failure behavior。

### Go Control Plane

状态：persistent read/audit primitive 已稳定；write-side registry mutation 还没有实现。

证据：

- file-backed registry store 仍然是默认值。
- PostgresStore load parity 已通过现有 Store interface 实现。
- live Postgres dogfood 使用 podman 验证了 schema apply、seed import、snapshot parity、CLI export、service validation 和 service export。
- persistent audit writes 已覆盖 registry revisions、artifact publications 和 admin audit events。
- persistent store failure semantics 是 fail-closed 且 machine-readable。
- mutation boundary review 已拒绝 granular CRUD，并建议 full-registry import/replace。

加固含义：

下一项任务必须先设计一个受控的 full-registry replacement transaction，不能先做 public write API。

## Import/Replace Design 进入门槛

下一项设计必须明确：

- input registry document shape
- parse 和 schema validation order
- canonicalization rules
- full registry graph validation
- registry fingerprint computation
- idempotent no-op behavior
- transaction isolation
- registry-wide mutation lock
- mutable registry tables 的 replacement strategy
- 同 transaction 内写入 `registry_revisions`
- 同 transaction 内写入 success `admin_audit_events`
- best-effort failure audit behavior
- rollback semantics
- stable machine-readable error taxonomy

## 不变量

这些不能回退：

- `FileStore` 仍然是默认 runtime store。
- Postgres 仍然必须显式 opt-in。
- registry tables 只存 credential metadata，永远不存 secret material。
- snapshots 仍然是 Data Plane handoff unit。
- Data Plane 不直接读取 mutable Control Plane tables。
- full registry validation 必须发生在 publishable snapshot export 之前。
- generated packages 保持 API-first。
- Python tooling 是 reference implementation，不是 production Data Plane。
- 不引入 workflow engine。
- 不引入 marketplace、billing、settlement 或 credential vault。

## 需要警惕的风险

### Partial Registry Mutation

import/replace path 不能退化成 individual row CRUD。Registry objects 是耦合的，必须作为一个 graph 验证。

### Hidden Snapshot Drift

import/replace 必须产出 deterministic fingerprints 和 export-compatible registry state。如果 file registry 和 persistent registry 语义漂移，Data Plane reload behavior 会变得不可解释。

### Audit 只做 Best Effort

成功的 persistent mutations 必须要求 audit writes。失败 audit 只有在需要保留原始错误时才可以 best effort。

### Credential Boundary Creep

credential metadata 可以经过 registry。secret values 不可以。Vault design 仍然不属于这个阶段。

### Product Scope Creep

这个阶段不是加入 marketplace provider onboarding、workflow adapters、billing 或 hosted user/org product surfaces 的时机。

## 推荐下一项任务

本 review 推荐的任务已经完成：

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```

当前下一项任务：

```text
Go Control Plane Private Admin Import/Replace Endpoint Design v0
```

已完成的 design 产出：

- 一份 design document，而不是 runtime write API
- transaction 和 rollback rules
- idempotency 和 audit requirements
- failure taxonomy
- explicit non-goals

## 验证基线

最近已知验证基线：

```text
python -m pytest
169 passed

go test ./...   # services/data-plane
go test ./...   # services/control-plane
```

本次 consolidation review 是 docs-only；更新指针后做文档引用和轻量回归验证即可。
