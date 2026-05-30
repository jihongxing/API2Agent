# API2Agent 实施计划

## 1. 当前构建目标

当前仓库实现的是 Free Tooling Layer：

```text
OpenAPI / curl
  -> API2Agent IR
  -> filtered capability package
  -> generated runner
  -> generated smoke test
  -> generated MCP server
```

这已经证明了本地可用性和第一条 controlled execution loop。

当前阶段：

```text
Python MVP freeze
  -> Protocol v0.2 contract freeze
  -> Production Architecture RFC
  -> Control Plane / Data Plane split
```

Python 实现保留为 reference implementation、local tooling surface 和 dogfood harness，不应该继续扩展成长远 hosted data plane。

## 2. 当前仓库结构

```text
api2agent/
  cli.py
  filters.py
  ir/
    models.py
  parsers/
    openapi.py
    curl.py
  generators/
    package.py
    runner.py
    tools.py
    mcp.py
    readme.py
    smoke_test.py
  safety/
    classifier.py
tests/
  fixtures/
docs/
  en-US/
  cn-ZH/
```

## 3. 已完成 Tooling Milestones

- Project skeleton
- API2Agent IR
- OpenAPI parser
- curl parser
- safety classifier
- package generator
- runner generator
- smoke test generator
- MCP server generator
- MCP stdio integration test
- tool filtering / selection
- bilingual docs
- open-core license
- control layer MVP
- capability/provider/routing model
- usage、ledger、replay、shadow 和 golden trace
- credential orchestration MVP
- region-aware routing 和 provider-region selection
- decision dataset seed
- MVP exit review
- Architecture Definition Phase documentation
- API2Agent Protocol v0.2 planning document

## 4. 剩余 Tooling Reliability 工作

这些仍然有价值，但不再是战略终点：

1. Endpoint-level auth
2. Base URL override
3. Manual write test path
4. Better curl naming
5. Large spec performance

在 proxy 和 metrics 存在之前，不要继续扩很多新输入格式。

## 5. 下一阶段主线：Control Layer MVP

目标：

```text
generated package
  -> API2Agent Proxy
  -> third-party API
  -> usage event
```

### Step 1：Usage Event Schema

定义中立事件模型：

- project_id
- capability_id
- provider_id
- tool_id
- timestamp
- method
- path
- status_code
- success
- latency_ms
- estimated_cost
- error_type

完成条件：

- event model 可以序列化为 JSON
- tests 覆盖 success 和 failure events

### Step 2：Proxy Call Contract

定义：

```http
POST /v1/proxy/call
```

Request：

```json
{
  "capability_id": "github_repos",
  "tool_id": "list_repos",
  "provider_id": "github",
  "params": {}
}
```

完成条件：

- contract 被文档化
- runner 可以生成 direct mode 或 proxy mode

### Step 3：Local Proxy Prototype

先构建最小 local service。

建议 stack：

- FastAPI or simple ASGI app
- SQLite for usage events
- httpx for forwarding
- pytest for proxy tests

完成条件：

- proxy 可以 forward 一个 generated tool call
- proxy 可以记录 usage event
- proxy 返回 structured success/error result

### Step 4：Quota MVP

添加 project-level quota：

- max calls per project
- quota exceeded error
- usage count query

完成条件：

- proxy 在 quota 超额后阻止调用
- quota event 被清晰记录

### Step 5：Metrics Report

添加 CLI 或 endpoint report：

- total calls
- success rate
- average latency
- estimated cost
- error type counts

完成条件：

- 用户可以看到某个 API capability 是否可靠、是否昂贵

## 6. Capability Layer MVP

这一层从最小 machine-readable schema 开始。

定义：

- Capability Schema v0.1
- Provider Candidate model
- tool 到 capability 的 mapping
- metrics snapshot per candidate

完成条件：

- 两个 provider 可以映射到同一个 capability
- metrics 可以比较

## 7. Routing Layer MVP

Routing v0 支持简单策略：

- random
- lowest estimated cost
- highest observed success rate
- lowest average latency
- balanced score

完成条件：

- 一次 capability request 可以路由到两个 providers 中的一个
- routing decision 被记录
- failover 可以尝试第二个 provider

CLI：

```bash
api2agent route capability-registry.json \
  --capability-id image_generation \
  --strategy lowest_cost \
  --db api2agent-usage.sqlite
```

最小 provider registry：

```json
{
  "providers": [
    {
      "id": "provider_a",
      "capability_id": "image_generation",
      "provider_id": "a",
      "tool_id": "generate",
      "estimated_cost": 0.02
    }
  ]
}
```

## 8. Credential Orchestration MVP

Credential orchestration 在 billing 和 marketplace 之前。

定义：

- Credential Schema v0.1
- owner types：user、project、platform、provider
- sources：env、config、inline、none
- resolver order
- injection patch contract
- usage event `credential_reference`
- redaction rules

完成条件：

- 一个 authenticated API 可以使用 resolved local credential 调用
- raw secrets 不会存入 usage events
- exact replay 需要 credential 但无法 resolve 时会 warning
- ledger 可以保留 credential attribution，且不暴露 secrets

当前实现：

- Credential Schema v0.1 code models 已实现。
- Local resolver 支持 env/config/inline/none。
- Generated package execution 可以 inject credentials。
- Usage events 会记录 `credential_reference`。
- Local package replay 可以基于 redacted metadata 重新 resolve credentials。
- Generated package proxy mode 会发送 credential intent，而不是 provider secrets。
- Local proxy 会解析 credential intent，并在转发前注入 provider auth。
- Local proxy 可以通过 `--credential-config` 加载 JSON/YAML credential config。
- payload 不携带 credential intent 时，config credentials 可以作为 provider-level fallback。
- Credential precedence 是确定性的：inline、config、request/env intent、none。
- Config credential ownership 会优先选择 exact project owner，然后是 local owner，最后按 config order。
- Credential scope 可以按 provider、capability、tool 或 wildcard 限制访问。
- Out-of-scope credentials 会返回 redacted `credential_scope_denied` errors。
- Credential lifecycle metadata 支持 status、expiry 和 rotation hints。
- Disabled 和 expired credentials 会返回 redacted machine-readable errors。
- Usage CLI 可以打印 secret-safe credential audit events 和 failure counts。
- Real authenticated proxy credential dogfood 已通过 httpbin bearer auth 验证。
- 新战略优先级：最大化真实执行数据，并最小化 API/provider onboarding cost。
- 新 routing requirement：location-aware execution 和 region-aware latency。
- Region-aware usage schema、provider metadata 和 decision dataset contract 已在本地实现。
- `region_aware_latency` routing strategy 已实现。
- `api2agent route` 和 `api2agent call` 支持 `--client-region`。
- routing decisions 会持久化 `client_region`。
- routing decisions 会持久化确定性的 `selected_provider_region`。
- generated package usage events 会记录推导后的 `provider_region`。
- Python MVP 已达到文档化退出标准。
- Architecture Definition Phase 已启动。
- Protocol v0.2 freeze planning 已文档化。
- Protocol v0.2 frozen contract 已文档化。
- Protocol v0.2 machine-readable schema snapshot 已提供。
- Production Architecture RFC 已文档化。
- Data Plane 和 Control Plane backend 方向是 Go。
- Python reference migration plan 已文档化。
- Go Data Plane Skeleton plan 已文档化。
- Go Data Plane Skeleton implementation 已位于 `services/data-plane`。
- Go/Python dual-run dogfood 已通过，覆盖 `network.public_ip.get`。
- Python 冻结为 reference implementation 和 local dogfood harness，不作为 production data plane。
- Go Data Plane Skeleton hardening 已完成：
  - `/healthz` 暴露 protocol 和 snapshot metadata。
  - snapshot TTL parsing 和 expiration helpers 已实现。
  - project-key bearer auth、timeout failure mapping、missing-adapter failed decisions 和 event sequence IDs 已有 Go tests 覆盖。
- Go Data Plane protocol conformance 和 failover dogfood 已完成：
  - emitted RequestContext、RoutingDecision、UsageEvent 和 DecisionLog records 会基于 v0.2 schema snapshot 检查。
  - failover policy 可以在 controlled HTTP 500 primary provider 失败后切到 fallback provider 成功。
  - 每个 attempt 都会写 UsageEvent，DecisionLog 会聚合两个 attempt IDs。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_FAILOVER_DOGFOOD_REPORT.md`。
- Go Data Plane env credential resolution skeleton 已完成：
  - `/v1/execute` 接受 request-level credential intent。
  - local env-backed secrets 可以被 resolve，并注入 provider requests。
  - usage events 只记录 `credential_reference` 和 redacted credential metadata。
  - env secret 缺失会在 provider forwarding 前失败，并写入 failed UsageEvent。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_CREDENTIAL_DOGFOOD_REPORT.md`。
- Go Data Plane durable event ingestion 已完成：
  - JSONL event writer 会在返回前对每条 event 执行 fsync。
  - writer 启动时会从已有 `events.jsonl` 恢复下一个 event sequence ID。
  - 已损坏的 event log 会让 writer 启动失败，而不是静默重置 sequence state。
  - restart dogfood 在两次 Data Plane 进程运行中产出了单调递增的 sequence IDs `1..8`。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_DURABLE_EVENTS_DOGFOOD_REPORT.md`。
- Go Data Plane real external provider retry dogfood 已完成：
  - `httpbin/status/500` 会写入失败的第一条 `UsageEvent`。
  - `httpbin/ip` 作为 fallback attempt 成功，并返回标准化 `{"ip": ...}` 输出。
  - `DecisionLog` 记录最终成功，并引用两次 usage attempts。
  - dogfood 也记录了本地 Go runtime 访问 `api.ipify.org` fallback 被断开的失败经验，说明外部 API 可用性必须从真实 execution runtime 测量。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_REAL_EXTERNAL_PROVIDER_RETRY_DOGFOOD_REPORT.md`。
- Go Data Plane stage review 已完成：
  - 当前阶段总结在 `docs/cn-ZH/GO_DATAPLANE_STAGE_REVIEW.md`。
  - 下一项 hardening slice 已收敛为 conformance validation、event write failure policy 和 runtime provider availability probing。
- Go Data Plane Consolidation Hardening v0 已完成：
  - reusable Protocol v0.2 conformance validator 已在 Go 中可用。
  - durable 和 real external retry dogfood scripts 会校验 emitted JSONL events。
  - event write failures 现在会 fail closed，并返回 `EVENT_WRITE_FAILED`。
  - runtime provider reachability probe 已完成 dogfood。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_CONSOLIDATION_HARDENING_REPORT.md`。
- Timeout Budget Semantics v0 已完成：
  - `timeout_budget_ms` 现在按 request-level total deadline 执行。
  - 每个 provider attempt 只能使用 request 的剩余预算。
  - total budget 耗尽后不会继续 fallback。
  - `UsageEvent.request_metadata` 会记录 total、attempt、remaining 和 policy timeout metadata。
  - `DecisionLog.routing_context` 会记录 timeout budget 是否耗尽。
  - local dogfood 覆盖 slow-primary exhaustion 和 fast-failure fallback。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_TIMEOUT_BUDGET_DOGFOOD_REPORT.md`。
- Snapshot Freshness Gate v0 已完成：
  - `/v1/execute` 会在 routing 前检查 snapshot TTL。
  - expired snapshots 会以 `SNAPSHOT_EXPIRED` fail closed。
  - invalid snapshot TTL 会以 `SNAPSHOT_INVALID` fail closed。
  - expired snapshots 不会调用 provider adapters。
  - failed freshness checks 仍然会写入 `RequestContext` 和 failed `DecisionLog`。
  - `/healthz` 会把 expired snapshots 报告为 `degraded`。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_FRESHNESS_DOGFOOD_REPORT.md`。
- Project Quota Gate v0 已完成：
  - Go Data Plane 可以执行本地 process-level project quota。
  - quota 通过 `API2AGENT_PROJECT_QUOTA` 配置。
  - quota failures 会返回 `QUOTA_EXCEEDED` 和 HTTP `429`。
  - quota failures 不会调用 provider adapters。
  - quota failures 仍然会写入 `RequestContext` 和 failed `DecisionLog`。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_PROJECT_QUOTA_DOGFOOD_REPORT.md`。
- Go Data Plane Credential Config v0 已完成：
  - Go Data Plane 可以通过 `API2AGENT_CREDENTIAL_CONFIG` 加载本地 JSON credentials。
  - config credentials 可以在每次 request 不携带 credential intent 时注入 provider auth。
  - config credential references 会记录为 `config:<credential_id>`。
  - raw secrets 不会写入 emitted events。
  - config credential scope 和 lifecycle checks 会被执行。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_CREDENTIAL_CONFIG_DOGFOOD_REPORT.md`。
- Go Data Plane Credential Audit Metadata v0 已完成：
  - local credential definitions 可以携带 `credential_version`。
  - credential resolution 会记录安全的 `resolved_at` audit metadata。
  - rotation hints 和 lifecycle status 会保留在 redacted usage metadata 中。
  - Protocol v0.2 `CredentialReference` 保持不变；audit extensions 放在 `UsageEvent.request_metadata.credential` 下。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_CREDENTIAL_CONFIG_DOGFOOD_REPORT.md`。
- Execution Event Ordering / Attempt Correlation v0 已完成：
  - 每次 provider attempt 使用自己的 `UsageEvent.id` 作为 attempt id。
  - fallback attempts 会把 `UsageEvent.parent_attempt_id` 设置为前一次 attempt id。
  - attempt id 和 parent id 也会进入 safe request metadata。
  - `DecisionLog.routing_context.attempt_chain` 会记录有序的 attempt correlation。
  - controlled 和 real external retry dogfoods 都会校验 attempt chain。
- Go Data Plane Milestone Closeout + Phase 6 Readiness Review 已完成：
  - local Go Data Plane execution and observability primitive 已收口。
  - Phase 6 可以从 local Go Control Plane minimum 开始。
  - readiness 是有条件的：还不进入 hosted public alpha、billing 或 marketplace。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_MILESTONE_CLOSEOUT.md`。

下一项工程任务：

```text
Go Control Plane Minimum v0
```

初始范围：

1. Project model
2. API2Agent project API key model
3. Capability registry model
4. Provider registry model
5. Credential metadata model，不包含 secret storage
6. Routing snapshot export format，供现有 Go Data Plane 消费

当前 Phase 6 进展：

- Go Control Plane Minimum v0 已完成：
  - `services/control-plane` 包含初始 Go module。
  - `api2agent-controlplane export-snapshot` 可以从 local registry JSON 导出 Data Plane-compatible routing snapshot。
  - local registry JSON 覆盖 projects、API keys、capabilities、providers、credential metadata、routing policy 和 snapshot export metadata。
  - Go Data Plane 可以加载 Control Plane 导出的 snapshot，并保留 exporter metadata。
  - cross-plane dogfood 证明 `Control Plane registry -> snapshot export -> Data Plane execute`。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_MINIMUM_DOGFOOD_REPORT.md`。
- Control Plane Registry Validation v0 已完成：
  - registry validation 会检查 project、API key、capability、provider 和 credential ids 的唯一性。
  - API keys 必须引用已知 projects。
  - providers 必须引用已知 capabilities，并且 capability version 要一致。
  - active providers 必须包含 `metadata.base_url`。
  - routing strategy、routing mode、failover policy、snapshot source 和 snapshot TTL 会被校验。
  - credential metadata 会校验 owner/project references、provider references、status、auth type、injection mode、source 和 scope references。
  - dogfood 会验证 invalid registries 在 snapshot export 前被拒绝。
- Control Plane Snapshot Compatibility Gate v0 已完成：
  - Go Data Plane 提供 `api2agent-snapshot-check`。
  - snapshot checker 会加载 exported snapshots、解析 TTL、校验 required capability/provider/routing fields，并输出 JSON report。
  - Control Plane minimum dogfood 现在会先用 `api2agent-snapshot-check` gate snapshot export，再进入 Data Plane execution。
  - 这可以防止 Control Plane/Data Plane contract 静默漂移。
- Control Plane Registry Store v0 已完成：
  - `registry.Store` 定义 Control Plane state source boundary。
  - `registry.FileStore` 是当前 local implementation。
  - `api2agent-controlplane export-snapshot` 现在通过 store interface 加载 registry state。
  - 未来 hosted phases 可以增加 Postgres-backed store，而不改变 snapshot export semantics。
- Control Plane Snapshot Versioning Policy v0 已完成：
  - snapshots 继续要求显式 `snapshot.version`。
  - exported snapshots 包含 `snapshot_version_policy=explicit`。
  - exported snapshots 包含确定性的 `registry_fingerprint=sha256:<hash>` metadata。
  - 相同 registry content 的 fingerprint 稳定，registry content 变化时 fingerprint 会变化。
  - `api2agent-snapshot-check` 会报告 version policy 和 registry fingerprint metadata。

## 9. Marketplace 是后面的结果

在以下条件成立前，不要做 marketplace UI：

- proxy works
- credential orchestration exists
- metrics exist
- capability abstraction exists
- routing works
- pricing metadata exists

Marketplace 应该是 routing plus economics 的结果，不是起点。
