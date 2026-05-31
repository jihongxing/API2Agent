# API2Agent Hosted Control Plane Pause + Agent Capability Compiler Re-entry v0

日期：2026-06-01

状态：complete

## 决策

暂停更深的 hosted Control Plane 工作，回到 Agent capability compiler 扩展。

此前推荐的任务：

```text
Go Control Plane Hosted Admin Gateway Permission Source Design v0
```

移入 hosted-readiness backlog。它仍然重要，但不再是立即下一项任务。

立即下一项任务是：

```text
Agent Capability Compiler Expansion Design v0
```

这次 re-entry 是有边界的。API2Agent 应该强化从真实 API 到 Agent-ready capabilities 的路径，而不是变成 workflow engine、marketplace、hosted provider onboarding product、vault、billing system 或 public Control Plane CRUD surface。

## 为什么现在暂停 Hosted Work

Hosted Control Plane track 已经到达可信的暂停点：

- persistent registry storage 已 dogfood
- import/replace mutation 已实现
- admin mutation idempotency 已 durable
- hosted admin identity 和 trusted-gateway auth 已实现
- gateway secret rotation 和 key-id evidence 已实现
- local gateway contract harness 已证明 public header stripping 和 trusted claim injection
- closeouts 已记录 remaining hosted-readiness risks

下一批 hosted tasks 是更深的平台工作：

- permission-source design
- real public auth
- production gateway deployment
- tenant-partitioned mutation semantics
- hosted operational controls

这些都重要，但当 Agent capability compiler 在真实 API onboarding 和 generated capability quality 上仍有明显提升空间时，它们不是最高杠杆的下一步。

## 为什么回到 Compiler

API2Agent 的核心产品循环是：

```text
real API input
  -> Agent capability compiler
  -> generated package
  -> observable execution
  -> usage, latency, error, credential, and routing data
  -> better reliability decisions
```

改进 compiler 有直接产品杠杆：

- 降低从 API input 到 first successful Agent call 的时间
- 增加可产生 usage data 的真实 API 数量
- 改进 generated tool names、schemas、docs 和 safe tests
- 提高 proxy/observable execution adoption
- 在不立即做 hosted product work 的情况下强化未来 Control Plane provider candidates

## Consolidated State

### Tooling / Compiler

稳定到可以继续扩展：

- OpenAPI 和 curl inputs 已支持。
- Generated packages 包含 runner、smoke test、MCP server、README 和 capability metadata。
- Direct 和 proxy execution paths 已可用。
- Credential intent、provider region、latency benchmark、base URL override、endpoint auth inference、manual write test path 和 large-spec filtering 已加固。

主要机会：

- generated capability quality 和 real-world API onboarding 仍需要系统扩展。

### Go Data Plane

稳定到可以继续作为 execution contract：

- Protocol v0.2 records 已 emit 并 validate。
- Retry/failover、timeout budget、quota、credential config、durable events、snapshot freshness、reload 和 attempt correlation 已 dogfood。
- Data Plane 继续消费 immutable/versioned snapshots，不读取 mutable Control Plane tables。

### Go Control Plane

稳定到可以暂停：

- persistent registry read/write primitives 已存在
- import/replace 保持 controlled 和 private
- idempotency 和 audit evidence 已 durable
- hosted/trusted-gateway admin path 已通过 local gateway contract harness 证明

Remaining hosted risks 已文档化，但现在刻意 deferred。

## Compiler Expansion Principles

### API-first

继续聚焦：

- OpenAPI
- curl
- HTTP/REST APIs
- generated capability packages
- generated runners
- generated smoke/manual write tests
- generated MCP servers

### Quality Over Surface Area

Compiler expansion 应提升 generated capabilities 是否 Agent-usable，而不是只增加 endpoint 数量。

好的扩展方向：

- 更好的 operation naming
- 更好的 parameter/schema shaping
- 更好的 auth inference
- 更好的 server/base URL handling
- 让 first call 更快的 generated docs
- capability quality diagnostics
- 更安全的 generated tests
- observable/proxy execution defaults

### Preserve Control/Data Plane Boundaries

Compiler 工作不应依赖 hosted Control Plane features。

Generated artifacts 应继续兼容：

- proxy mode
- credential-safe execution
- usage event identity
- routing/provider metadata
- 与 provider candidates 重叠处的 Data Plane snapshots
- language-neutral protocol artifacts

## Recommended Expansion Tracks

### Track A: Capability Quality Diagnostics

设计一个 compiler report，在用户运行前 score 或 flag generated capabilities。

候选检查：

- vague capability/provider/tool names
- missing auth intent
- missing required parameters
- risky write operations
- overly broad large-spec output
- weak descriptions for Agent tool selection
- missing examples or smoke-test defaults

### Track B: OpenAPI Real-World Hardening

改进常见 OpenAPI spec complexity 支持：

- multiple servers and base paths
- security scheme combinations
- request bodies with nested schemas
- enum/default/example propagation
- operation filtering diagnostics
- 会生成较差 Agent-facing tool inputs 的 schema cases

### Track C: curl Instant Onboarding

让 curl-derived packages 立刻更可用：

- stronger auth inference
- better query/header/body default preservation
- better capability naming from host/path/action
- clearer generated README first-call path
- safer write-method handling

### Track D: Observable Execution Defaults

让 generated packages 更自然地产生 usage data：

- proxy-mode guidance
- credential intent clarity
- latency benchmark hooks
- provider region metadata
- stable usage identity fields

## 推荐下一项 Slice

先做设计，不直接实现：

```text
Agent Capability Compiler Expansion Design v0
```

设计应选择第一个具体 compiler expansion slice，并定义：

- target user workflow
- accepted inputs
- generated artifact changes
- compatibility with existing generated packages
- tests and dogfood
- success metrics
- non-goals

推荐后续第一个 implementation candidate：

```text
Agent Capability Compiler Quality Diagnostics v0
```

它杠杆较高，因为它能同时改善 OpenAPI 和 curl paths，又不会过早增加新 runtime 或 hosted dependency。

## Frozen Scope

仍然不要开始：

- workflow engine execution
- non-API runtime adapters
- marketplace UI or provider submission
- billing or settlement
- credential vault writes
- hosted public CRUD
- real OAuth/OIDC implementation
- production gateway deployment
- automatic snapshot publish/reload
- Data Plane reads from mutable Control Plane tables

## Validation

这是 docs-only stage consolidation。验证要求：

```text
git diff --check
```
