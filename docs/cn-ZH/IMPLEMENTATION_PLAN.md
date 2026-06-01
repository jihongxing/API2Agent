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
Go Control Plane Hosted Permission Decision Persistence Implementation Complete
```

Python 实现保留为 reference implementation、local tooling surface 和 dogfood harness。Agent Capability Compiler re-entry phase 已关闭，当前 gate 是 hosted permission decision persistence closeout and phase review。

实现语言决策：

```text
Python = Tooling reference implementation 和 local dogfood harness。
Go = production Data Plane 和 Control Plane implementation。
Protocol artifacts = language-neutral boundary。
```

参见 `docs/cn-ZH/TOOLING_IMPLEMENTATION_LANGUAGE_DECISION.md`。

当前 Tooling Layer 目标：

1. 更多真实调用数据
2. 更低 API/provider 接入成本
3. 更快 Agent API 响应

当前 Tooling Layer 约束：

- API-first
- 不做 workflow engine
- 不新增 non-API runtime
- 不做 marketplace
- 不做 billing
- 不做 vault
- 保持 proxy、usage、credential、replay、shadow、golden trace 和 Protocol v0.2 compatibility

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

当前 active Tooling Re-entry hardening backlog 已完成，closeout review 也已完成。

最近完成：

- Manual write test path
- Large spec performance
- Better curl naming residual review
- Tooling Re-entry closeout review

不要继续扩很多新输入格式。当前 tooling expansion 保持 API-first：OpenAPI、curl、HTTP/REST、generated packages、generated runner、smoke test 和 MCP server。

当前 re-entry plan：

- 详见 `docs/cn-ZH/API2AGENT_TOOLING_REENTRY_REVIEW_AND_EXPANSION_PLAN.md`

下一项 tooling task：

```text
Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0
```

下一项工程任务：

```text
Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0
```

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
- Control Plane Snapshot Export Artifact v0 已完成：
  - `api2agent-controlplane export-artifact` 会写入 artifact 目录，而不是只输出裸 `snapshot` 文件。
  - artifact layout 是 `snapshot.json` 加 `manifest.json`。
  - manifest 记录 artifact version、export time、registry store/source、snapshot file/version/source、snapshot version policy、registry fingerprint 和 validation summary。
  - Control Plane minimum dogfood 会在 Data Plane execution 前验证 manifest 存在、manifest 引用 snapshot、registry fingerprint 与 `api2agent-snapshot-check` 一致，以及 registry validation summary 有效。
  - 这为后续 snapshot distribution 建立了 local artifact boundary。
- Control Plane Snapshot Distribution Stub v0 已完成：
  - `api2agent-controlplane publish-artifact` 会将 artifact 目录发布到 local distribution 目录。
  - distribution layout 是 `current.json` 加 `artifacts/<snapshot_version>/snapshot.json` 和 `artifacts/<snapshot_version>/manifest.json`。
  - `current.json` 记录 distribution version、publish time、snapshot version、artifact file references、registry fingerprint 和 snapshot version policy。
  - Go Data Plane snapshot loading 现在支持裸 snapshot 文件、包含 `current.json` 的 distribution 目录，或直接传入 `current.json` 路径。
  - `api2agent-snapshot-check` 可以校验 distribution 目录，因为它使用同一个 snapshot resolver。
  - cross-plane dogfood 证明 `Control Plane registry -> artifact export -> local distribution publish -> Data Plane execute`。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_SNAPSHOT_DISTRIBUTION_DOGFOOD_REPORT.md`。
- Control Plane Snapshot Refresh / Reload Policy v0 已完成：
  - Data Plane 默认 snapshot policy 仍然是 `startup_only`。
  - local manual reload 只有在 `API2AGENT_SNAPSHOT_RELOAD_POLICY=manual` 时开启。
  - `POST /v1/admin/reload-snapshot` 会重新加载配置的 snapshot source，包括 `current.json` 已变化的 distribution 目录。
  - `/healthz` 会报告 snapshot reload policy、loaded-at timestamp、source path 和 resolved snapshot path。
  - 如果设置了 `API2AGENT_PROJECT_KEY`，reload endpoint 需要和 `/v1/execute` 相同的 bearer token。
  - cross-plane dogfood 证明 v1 startup、v2 distribution publish、manual reload 和 v2 execution event attribution。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_RELOAD_DOGFOOD_REPORT.md`。
- Control Plane Snapshot Reload Failure Semantics v0 已完成：
  - 从 serving snapshot 视角看，reload 是 atomic 的：失败 reload 不会替换 active snapshot。
  - 失败 reload 返回 `SNAPSHOT_RELOAD_FAILED`、`reloaded=false`、`kept_snapshot_version`、当前 `snapshot_resolved_to` 和 retryable error metadata。
  - 失败 reload 后 `/healthz` 仍然停留在 previous snapshot。
  - cross-plane dogfood 证明损坏的 `current.json` 失败后保持 v1 active，随后 valid v2 publish 和 reload 可以成功。
- Control Plane Snapshot Reload Audit Events v0 已完成：
  - Data Plane 会为 failed 和 successful reload attempts 写入 `snapshot_reload_event`。
  - successful reload 会先写 audit event，再替换 active snapshot。
  - failed reload 会写 audit event，并保持 previous snapshot active。
  - reload audit events 与 execution events 共享同一个 append-only event stream 和 event sequence IDs。
  - cross-plane dogfood 验证 failed reload audit、successful reload audit 和 execution graph ordering。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_RELOAD_AUDIT_DOGFOOD_REPORT.md`。
- Control Plane Snapshot Version Compatibility Guard v0 已完成：
  - Control Plane exported snapshots 包含 `metadata.schema_version=api2agent.protocol.v0.2`。
  - Data Plane snapshot loading 会拒绝声明了其他 `metadata.schema_version` 的 snapshots。
  - 因为 startup load、`api2agent-snapshot-check` 和 manual reload 使用同一个 snapshot loader，所以 guard 覆盖三条路径。
  - 暂时仍然允许缺少 `metadata.schema_version` 的 legacy local snapshots。
  - cross-plane dogfood 验证 incompatible v3 reload 被拒绝，v2 保持 active，并且 execution 继续使用 v2。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_COMPATIBILITY_GUARD_DOGFOOD_REPORT.md`。
- Control Plane Snapshot Strict Metadata Requirement v0 已完成：
  - Control Plane/exported snapshots 必须包含 `metadata.schema_version`、`metadata.registry_fingerprint` 和 `metadata.snapshot_version_policy`。
  - 暂时仍然允许没有 Control Plane metadata 的 legacy local snapshots。
  - startup load、`api2agent-snapshot-check` 和 manual reload 共享同一个 strict metadata guard。
  - cross-plane dogfood 验证缺少 `registry_fingerprint` 的 v4 distribution 会被拒绝，v2 保持 active，并记录 reload audit event。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_STRICT_METADATA_DOGFOOD_REPORT.md`。
- Control Plane Snapshot Metadata Manifest Consistency Guard v0 已完成：
  - Control Plane 会在写入或发布 artifact 前校验 `snapshot.json` 和 `manifest.json` consistency。
  - Data Plane 会在加载 distributed snapshot 前校验 `current.json`、`manifest.json` 和 `snapshot.json` consistency。
  - publish-time manifest mismatch 会在推进 `current.json` 前被拒绝。
  - reload-time distribution tampering 会被拒绝，previous active snapshot 继续 serving。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_MANIFEST_CONSISTENCY_DOGFOOD_REPORT.md`。
- Control Plane Snapshot Artifact Content Digest Guard v0 已完成：
  - Control Plane artifact manifests 现在包含 `snapshot_digest=sha256:<hash>`。
  - distribution `current.json` 会携带同一个 snapshot digest，用于 pointer-level audit。
  - `snapshot.json` 文件字节不匹配 manifest digest 时，Control Plane 会拒绝 artifact publish。
  - 文件字节不再匹配 manifest/current digest 时，Data Plane 会拒绝 distributed snapshot reload。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_CONTENT_DIGEST_DOGFOOD_REPORT.md`。
- Control Plane Snapshot Artifact Path Safety Guard v0 已完成：
  - Control Plane 会在写入或发布 artifact 前拒绝 unsafe `manifest.snapshot_file` 引用。
  - Data Plane 会在读取 distributed files 前拒绝 unsafe `current.snapshot_file`、`current.manifest_file` 和 `manifest.snapshot_file` 引用。
  - distribution metadata 内的绝对路径和 `..` 路径穿越都会被拒绝。
  - 直接传入 `API2AGENT_SNAPSHOT=<snapshot.json>` 的路径行为不变。
  - 详见 `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_PATH_SAFETY_DOGFOOD_REPORT.md`。
- Control Plane Snapshot Distribution Atomic Publish Guard v0 已完成：
  - Control Plane 会先通过 temporary artifact directory 复制 artifact，再 commit 最终 versioned artifact path。
  - `current.json` 通过 temporary file 写入，再替换。
  - duplicate `snapshot_version` publish 会在修改 `current.json` 前被拒绝。
  - duplicate publish dogfood 验证 current 保持稳定，并且没有 temporary artifact dirs 残留。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_SNAPSHOT_ATOMIC_PUBLISH_DOGFOOD_REPORT.md`。
- Go Control Plane Snapshot Distribution Closeout + Phase Review 已完成：
  - local snapshot distribution 链路已经从 registry 到 artifact、distribution、Data Plane reload 完成收口。
  - 剩余缺口明确推迟到 service API、remote storage、hosted persistence、vault、billing 或 marketplace 阶段。
  - 下一项 implementation slice 收窄为 local Control Plane service API skeleton。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_SNAPSHOT_DISTRIBUTION_CLOSEOUT.md`。
- Go Control Plane Service API Skeleton v0 已完成：
  - `api2agent-controlplane serve` 会在现有 file registry 上启动 local HTTP service。
  - `/healthz` 是 public endpoint，会报告 service/protocol metadata。
  - `/v1/admin/registry/validate`、`/v1/admin/snapshots/export-artifact`、`/v1/admin/distribution/publish` 和 `/v1/admin/distribution/current` 需要 admin bearer auth。
  - service dogfood 验证 auth guard、registry validation、HTTP artifact export 和 distribution pointer read。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_SERVICE_API_DOGFOOD_REPORT.md`。
- Go Control Plane Service Snapshot Publish Endpoint v0 已完成：
  - `/v1/admin/distribution/publish` 会把 existing artifact publish 到配置的 local distribution。
  - endpoint 复用与 CLI 相同的 atomic publish 和 duplicate-version guards。
  - duplicate publish 返回 `DISTRIBUTION_ARTIFACT_EXISTS`，并保持 `current.json` 不变。
  - service dogfood 现在验证 HTTP export -> HTTP publish -> HTTP current pointer。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_SERVICE_API_DOGFOOD_REPORT.md`。
- Go Control Plane Service API Closeout + Hosted Persistence Readiness Review 已完成：
  - local service boundary 已围绕 registry validation、artifact export、distribution publish 和 current pointer reads 完成收口。
  - hosted persistence readiness 被批准进入 design，但不直接进入 database implementation。
  - 下一项 implementation slice 收窄为 persistent registry store design。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_SERVICE_API_CLOSEOUT.md`。
- Go Control Plane Persistent Registry Store Design v0 已完成：
  - persistent registry store 仍然位于现有 `registry.Store` read boundary 后面。
  - 第一版 Postgres logical table model 已文档化，覆盖 projects、API keys、capabilities、providers、credential metadata、routing policy、snapshot configs、registry revisions、artifact publications 和 admin audit events。
  - registry load、artifact export 和 distribution publish 的 transaction boundaries 已定义。
  - fingerprint、versioning、migration 和 dual-store rules 已文档化。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_STORE_DESIGN.md`。
- Control, Receipt, and Trust Layer Strategy 已文档化：
  - `UsageEvent` 保持为 internal observation record。
  - 未来 `Receipt` 被定义为从 execution records 派生的 protocol-grade、verifiable execution evidence。
  - receipt farming 和 Edge-Mesh privacy requirements 已作为战略约束记录。
  - 这不改变当前下一项任务。
  - 详见 `docs/cn-ZH/CONTROL_RECEIPT_AND_TRUST_LAYER_STRATEGY.md`。
- Go Control Plane Persistent Registry Store Schema v0 已完成：
  - Postgres schema draft 已添加到 `services/control-plane/schema/postgres`。
  - schema tests 覆盖 required tables 和关键 constraints。
  - `MapRegistryToPersistentRows` 可以把现有 file registry fixture 映射为 persistent row-shaped structs。
  - `CanonicalRegistry` 可以对 persistent export inputs 做确定性排序，且不修改原始 registry。
  - `FileStore` 仍然是默认 runtime store。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_STORE_SCHEMA_REPORT.md`。
- Go Control Plane Persistence Phase Review 已完成：
  - 已完成的 Data Plane 和 Control Plane local primitives 已总结。
  - runtime persistence readiness 仅批准进入很窄的 load-parity 切片。
  - active requirements 已重新确认：API-first、snapshot-contract stability、registry tables 不存 secrets、不进入 marketplace/billing/vault scope。
  - 下一项 implementation slice 收窄为 `PostgresStore.Load(ctx)` parity。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENCE_PHASE_REVIEW.md`。
- Go Control Plane PostgresStore Load Parity v0 已完成：
  - `PostgresStore.Load(ctx)` 会在 read-only `REPEATABLE READ` transaction 内读取 persistent registry rows。
  - persistent row loading 会重建与 `FileStore` 相同的 in-memory `Registry` shape。
  - file-backed 和 Postgres-loaded registries 在测试中生成等价 snapshot contract output。
  - runtime store selection、Postgres driver wiring 和 live DB dogfood 被明确推迟。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_POSTGRES_STORE_LOAD_PARITY_REPORT.md`。
- Go Control Plane Persistent Store Runtime Wiring v0 已完成：
  - `--registry-store file|postgres` 和 `--postgres-dsn` 已接入 local commands。
  - 已增加 `pgx` stdlib driver 支持，用于显式选择 Postgres。
  - `seed-postgres` 可以把 file registry import 到 persistent schema。
  - `file` 仍然是默认 runtime store。
  - 当前环境没有 Docker 和 host `psql`，live Postgres dogfood 已使用 podman 完成。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_STORE_RUNTIME_WIRING_REPORT.md`。
- Go Control Plane Live Postgres Store Dogfood v0 已完成：
  - podman provisioned 了临时 Postgres-compatible database。
  - schema application、seed import、file/postgres snapshot parity、CLI artifact export、service validation 和 service artifact export 均通过。
  - 对现有 fixture，file-store 和 postgres-store snapshot output 完全一致。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_LIVE_POSTGRES_STORE_DOGFOOD_REPORT.md`。
- Go Control Plane Persistent Export/Publish Audit Writes v0 已完成：
  - Postgres runtime mode 现在会接入 persistent audit sink。
  - 配置 persistent audit 时，service registry validation、artifact export、distribution publish 和 current pointer reads 会写入 `admin_audit_events`。
  - artifact export 成功后写入 `registry_revisions`。
  - distribution publish 成功后写入 `snapshot_artifact_publications`。
  - live Postgres dogfood 已验证 `admin_audit_events=4`、`registry_revisions=2`、`snapshot_artifact_publications=1`。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_EXPORT_PUBLISH_AUDIT_REPORT.md`。
- Go Control Plane Persistent Store Failure Semantics Hardening v0 已完成：
  - Postgres-backed registry load failures 现在返回 `PERSISTENT_STORE_READ_FAILED`，HTTP 503，platform scope，并标记为 retryable。
  - file-store load failures 仍然保持 `REGISTRY_INVALID`，HTTP 400，caller scope，并标记为 non-retryable。
  - required persistent audit writes 失败时，成功 admin operations 会 fail closed，返回 `AUDIT_WRITE_FAILED`。
  - failure-path admin audit writes 保持 best-effort，避免遮盖原始错误。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_STORE_FAILURE_SEMANTICS_REPORT.md`。
- Go Control Plane Persistent Registry Mutation Boundary Review v0 已完成：
  - granular registry CRUD APIs 暂缓。
  - 下一条安全写侧路径是 controlled full-registry import/replace transaction。
  - mutable registry state 限定为 `projects`、`api_keys`、`capabilities`、`providers`、`credential_metadata`、`routing_policies` 和 `snapshot_configs`。
  - `registry_revisions`、`snapshot_artifact_publications` 和 `admin_audit_events` 保持 append-only evidence surfaces。
  - transaction、audit、idempotency、failure 和 rollback requirements 已在实现前文档化。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_MUTATION_BOUNDARY_REVIEW.md`。
- API2Agent Tooling Re-entry Review + Tooling Expansion Plan v0 已完成：
  - 项目现在带着 Control/Data Plane 约束回到 Tooling Layer。
  - 当前 Tooling Layer 目标是更多真实执行数据、更低 API/provider 接入成本、更快 Agent API 响应。
  - 当前实现保持 API-first，并明确不变成 workflow engine。
  - Control Plane import/replace transaction design 在 tooling baseline audit 期间保持暂停。
  - 详见 `docs/cn-ZH/API2AGENT_TOOLING_REENTRY_REVIEW_AND_EXPANSION_PLAN.md`。
- API2Agent Tooling Baseline Audit v0 已完成：
  - 可复现 audit script 位于 `scripts/api2agent_tooling_baseline_audit.py`。
  - ipify、Open-Meteo、GitHub repo read 和 httpbin bearer 的 curl generation 与第一次 direct call 均成功。
  - ipify、Open-Meteo 和 GitHub repo read 的 no-auth proxy execution 成功。
  - GitHub REST OpenAPI 生成成功，但未过滤 package 暴露 1186-tool 风险。
  - 下一项 Tooling fix 收窄为 OpenAPI filtering 和 curl tool naming hardening。
  - 详见 `docs/cn-ZH/API2AGENT_TOOLING_BASELINE_AUDIT_REPORT.md`。
- API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0 已完成：
  - root-path curl tools 现在包含 capability intent。
  - non-root curl naming 为 backward compatibility 继续保持 path-based。
  - OpenAPI generation 在 oversized packages 仍 unbounded 时输出 warning。
  - targeted tests 和 baseline audit script 在改动后均通过。
  - 详见 `docs/cn-ZH/API2AGENT_OPENAPI_FILTERING_CURL_NAMING_HARDENING_REPORT.md`。
- Generated Package Region Metadata v0 已完成：
  - `--provider-region` 会把 region metadata 写入 generated `capability.json`。
  - generated README files 包含 provider region guidance。
  - generated runners 会把 provider-region intent 传入 proxy payloads。
  - region metadata dogfood 已通过，scope 保持 API-first。
  - 详见 `docs/cn-ZH/API2AGENT_GENERATED_PACKAGE_REGION_METADATA_REPORT.md`。
- Proxy-mode Credential Dogfood Expansion v0 已完成：
  - `scripts/api2agent_proxy_credential_dogfood.py` 会让 authenticated generated package 通过 local proxy 运行。
  - local credential config 在 proxy 侧注入 provider auth，不让 generated package 携带 secret。
  - usage events 保留 credential-safe attribution 和 provider-region metadata。
  - 详见 `docs/cn-ZH/API2AGENT_PROXY_CREDENTIAL_DOGFOOD_EXPANSION_REPORT.md`。
- Generated Package Latency Benchmark Helper v0 已完成：
  - `run_generated_package_latency_benchmark` 提供可复用的 generated-package direct/proxy timing。
  - `api2agent benchmark-package` 可以为 generated package tools 输出 p50/p95 latency。
  - local dogfood 已验证 direct/proxy timing、proxy usage ids 和 provider-region attribution。
  - 详见 `docs/cn-ZH/API2AGENT_GENERATED_PACKAGE_LATENCY_BENCHMARK_REPORT.md`。
- Endpoint-level Auth Inference v0 已完成：
  - OpenAPI mixed public/protected operations 现在会生成 endpoint-aware auth metadata。
  - generated runners 只对 operation 需要 auth 的 tools 要求 auth。
  - proxy credential intent 和 local credential config selection 对 mixed-auth providers 具备 tool-specific 语义。
  - local dogfood 已验证 public/no-auth、bearer 和 API key endpoints 的 direct/proxy execution。
  - 详见 `docs/cn-ZH/API2AGENT_ENDPOINT_AUTH_INFERENCE_REPORT.md`。
- Base URL Override v0 已完成：
  - generated packages 可以用 `API2AGENT_BASE_URL` 在 runtime 覆盖 provider base URLs。
  - generated packages 可以用 `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>` 覆盖单个 tool。
  - direct 和 proxy execution 共用同一套 URL resolution semantics。
  - local dogfood 已验证 default、global override、tool-specific override、invalid override fail-fast 和 proxy usage metadata。
  - 详见 `docs/cn-ZH/API2AGENT_BASE_URL_OVERRIDE_REPORT.md`。
- Manual Write Test Path v0 已完成：
  - generated packages 现在包含 guarded `manual_write_test.py`。
  - 默认 `api2agent test` 继续保持 read-only。
  - `api2agent test --allow-write` 会显式 opt in write/delete testing。
  - local dogfood 已验证 default no-write behavior、direct opt-in execution、proxy opt-in execution 和 usage metadata preservation。
  - 详见 `docs/cn-ZH/API2AGENT_MANUAL_WRITE_TEST_PATH_REPORT.md`。
- Large Spec Performance v0 已完成：
  - OpenAPI filters 会在 parsing 阶段应用，而不是只在完整 tool construction 之后过滤。
  - `api2agent inspect` 会输出 large-package summaries 和 bounded tool lists。
  - `api2agent test --tool ... --params ...` 支持 targeted generated read-tool checks。
  - local dogfood 已验证 1200-operation spec 的 unfiltered warning、bounded generation、inspect summary 和 targeted execution。
  - 详见 `docs/cn-ZH/API2AGENT_LARGE_SPEC_PERFORMANCE_REPORT.md`。
- Better curl naming residual review v0 已完成：
  - `api` 和 `www` 这类 generic leading curl host labels 不再生成过泛的默认 capability names。
  - generated auth env names 现在继承更好的 capability intent，例如 `GITHUB_API_TOKEN`。
  - 显式 `--name` 和 non-root path-based tool naming 保持稳定。
  - local dogfood 已验证 generic API subdomain、root-path inferred naming、explicit name override 和 non-root path compatibility。
  - 详见 `docs/cn-ZH/API2AGENT_CURL_NAMING_RESIDUAL_REVIEW.md`。
- API2Agent Tooling Re-entry Closeout + Phase Review v0 已完成：
  - Tooling Re-entry 被判断为可以暂停。
  - acceptance criteria、validation 和 remaining risks 已文档化。
  - 除非先更新产品需求，下一项工程范围回到 Control Plane import/replace transaction design。
  - 详见 `docs/cn-ZH/API2AGENT_TOOLING_REENTRY_CLOSEOUT_REVIEW.md`。
- API2Agent Stage Consolidation Before Import/Replace v0 已完成：
  - Tooling、Go Data Plane 和 Go Control Plane persistent read/audit 状态已汇总。
  - import/replace design 的 entry gates 已文档化。
  - write-side design 开始前的不变量边界已重新确认。
  - 详见 `docs/cn-ZH/API2AGENT_STAGE_CONSOLIDATION_BEFORE_IMPORT_REPLACE.md`。
- Go Control Plane Persistent Registry Import/Replace Transaction Design v0 已完成：
  - 第一个 write-side operation 被限制为 controlled full-registry import/replace。
  - `seed-postgres` 仍然是 dogfood helper，不是 production mutation path。
  - serializable transaction、advisory lock、idempotency、same-transaction audit、rollback 和 snapshot boundary semantics 已明确。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_TRANSACTION_DESIGN.md`。
- Go Control Plane Persistent Registry Import/Replace CLI Implementation v0 已完成：
  - `api2agent-controlplane import-replace-postgres` 已实现为很窄的 local/admin write path。
  - `ReplacePersistentRegistry` 覆盖 serializable transaction、advisory lock、full mutable-table replacement、no-op detection、revision/audit writes 和 rollback behavior。
  - unit tests 覆盖 no-op、replacement、lock conflict、audit failure rollback 和 transaction options。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_CLI_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Persistent Registry Import/Replace Live Postgres Dogfood v0 已完成：
  - live Postgres dogfood 使用 podman。
  - schema apply、seed、changed-registry import/replace、same-registry no-op 和 snapshot export 均通过。
  - persistent audit counts 已断言：`registry_revisions=2`、`admin_audit_events=2`、`providers=1`。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_LIVE_POSTGRES_DOGFOOD_REPORT.md`。
- Go Control Plane Import/Replace Closeout + Mutation API Readiness Review v0 已完成：
  - local/admin CLI primitive 被接受为当前 write-side slice 的完成状态。
  - readiness decision 是只进入 private admin endpoint design。
  - public CRUD 和 endpoint implementation 继续 deferred。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_CLOSEOUT_MUTATION_API_READINESS_REVIEW.md`。
- Go Control Plane Private Admin Import/Replace Endpoint Design v0 已完成：
  - `POST /v1/admin/registry/import-replace` 是被接受的 private admin endpoint。
  - endpoint 要求 `Authorization`、`X-Request-ID` 和 `Idempotency-Key`。
  - request body 使用 wrapper object，包含 `registry`、可选 `source` 和 reserved `dry_run=false`。
  - FileStore 保持不变；只有 Postgres mutation mode 可以执行 import/replace。
  - response shape、request-size limit、error mapping、audit mapping 和 implementation tests 已文档化。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`。
- Go Control Plane Private Admin Import/Replace Endpoint Implementation v0 已完成：
  - `POST /v1/admin/registry/import-replace` 已在现有 admin auth boundary 后实现。
  - Postgres runtime wiring 注入很窄的 registry import replacer。
  - FileStore/unconfigured mutation 返回 `REGISTRY_MUTATION_UNAVAILABLE`。
  - changed registry 返回 `201`；same-fingerprint no-op 返回 `200`。
  - required request headers、2 MiB request-size limit、error mapping 和 option propagation 已有测试覆盖。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0 已完成：
  - live service dogfood 使用 podman-backed Postgres。
  - HTTP import/replace 返回 `201` 和 `noop=false`。
  - repeated import 返回 `200` 和 `noop=true`。
  - service validation/export 看到了替换后的 registry 和 `httpbin_public_ip_v1` provider。
  - persistent audit counts 已断言：`registry_revisions=3`、`admin_audit_events=4`、`providers=1`。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_LIVE_POSTGRES_DOGFOOD_REPORT.md`。
- Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0 已完成：
  - design、implementation 和 live dogfood 被接受为 complete。
  - private admin write-side endpoint milestone 可以关闭。
  - remaining risks 已文档化。
  - 下一项安全证明是从 import/replace 到 Data Plane execution 的 snapshot propagation。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0 已完成：
  - HTTP import/replace 将 persistent registry provider 替换为 `httpbin_public_ip_v1`。
  - Control Plane export 并 publish replacement snapshot。
  - Data Plane manual reload 从 `snapshot_propagation_ipify_v1` 切换到 `snapshot_propagation_httpbin_v2`。
  - Data Plane execution 返回 replacement-provider output `{ "ip": "203.0.113.88" }`。
  - usage 和 decision records 已归因到 replacement provider 和 snapshot version。
  - persistent audit counts 已断言。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`。
- Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0 已完成：
  - manual propagation milestone 可以关闭。
  - architecture rule 继续成立：Data Plane 消费 immutable/versioned snapshots，而不是 mutable Control Plane tables。
  - remaining hosted-readiness risks 已文档化。
  - 下一项任务收窄为 admin mutation idempotency store design。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0 已完成：
  - hosted/trusted-gateway service mode 不传 `--admin-token` 即可启动。
  - trusted gateway success、missing gateway auth 和 missing permission 已通过真实 HTTP 验证。
  - Postgres audit 和 idempotency records 保留 trusted principal evidence。
  - dogfood 修复了 import/replace audit metadata，使其包含 hosted principal evidence。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`。
- Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Closeout + Phase Review v0 已完成：
  - Control Plane 侧 hosted trusted-gateway path 可以暂停。
  - remaining gateway、secret-rotation、permission-source、header-stripping 和 tenant-partitioning risks 已文档化。
  - 下一项任务是 production gateway boundary design。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0 已完成：
  - gateway-to-Control-Plane trust boundary 已定义。
  - trusted header strip/rewrite rules 和 secret rotation policy 已定义。
  - permission issuance、audit/idempotency evidence、failure semantics、deployment 和 observability contracts 已定义。
  - implementation tests 和 dogfood requirements 已命名。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_DESIGN.md`。
- Go Control Plane Hosted Admin Trusted Gateway Production Boundary Implementation v0 已完成：
  - rotation-compatible active gateway secrets 已实现。
  - legacy single-secret configuration 保持兼容。
  - optional gateway key-id evidence 会进入 audit 和 import/replace metadata。
  - live dogfood 验证 overlap、old-secret removal、key-id evidence 和 secret-safe metadata。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0 已完成：
  - Control Plane 侧 production boundary mechanics 可以关闭。
  - remaining gateway contract、public auth、permission-source、deployment 和 tenant-partitioning risks 已文档化。
  - 下一项任务是 gateway contract harness design。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Hosted Admin Gateway Contract Harness Design v0 已完成：
  - local gateway harness responsibilities 已定义。
  - static public auth and identity policy 已定义。
  - header stripping、trusted claim injection 和 request/idempotency propagation 已定义。
  - negative spoofing cases 和 dogfood evidence requirements 已命名。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_DESIGN.md`。
- Go Control Plane Hosted Admin Gateway Contract Harness Implementation v0 已完成：
  - local dogfood-only gateway harness 已用 Python standard library HTTP server 实现。
  - public bearer auth 会在本地消费，同时 trusted gateway claims 会被 strip 并重新注入。
  - live dogfood 证明 health、validation、readonly authorization failure、import/replace、audit evidence、idempotency evidence 和 secret/token-safe artifacts。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Hosted Admin Gateway Contract Harness Closeout + Phase Review v0 已完成：
  - local gateway contract proof 已接受为 complete。
  - remaining risks 是 static public auth、static permission policy、production gateway deployment、tenant-partitioned mutation 和 manual propagation。
  - 下一项 hosted-readiness gap 是 permission-source design。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`。
- API2Agent Hosted Control Plane Pause + Agent Capability Compiler Re-entry v0 已完成：
  - deeper hosted Control Plane work 在可信暂停点后移入 backlog。
  - immediate next focus 回到 API-first Agent capability compiler expansion。
  - 推荐扩展 tracks 是 capability quality diagnostics、OpenAPI real-world hardening、curl instant onboarding 和 observable execution defaults。
  - 详见 `docs/cn-ZH/API2AGENT_HOSTED_CONTROL_PLANE_PAUSE_AND_AGENT_COMPILER_REENTRY.md`。
- Agent Capability Compiler Expansion Design v0 已完成：
  - quality diagnostics 被选为第一项 compiler expansion implementation slice。
  - target generate/diagnose/inspect workflows 已定义。
  - `diagnostics.json` contract、initial finding set、scoring heuristic、tests、dogfood 和 non-goals 已文档化。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`。
- Agent Capability Compiler Quality Diagnostics v0 已完成：
  - generated packages 现在包含 additive `diagnostics.json`。
  - `api2agent diagnose` 可以输出 human-readable 或 JSON diagnostics。
  - generation、README 和 inspect surfaces 会显示 compact diagnostics summaries。
  - deterministic findings 覆盖 usability、safety、auth、schema、execution 和 observability risks。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler Quality Diagnostics Closeout + Phase Review v0 已完成：
  - quality diagnostics 已接受为 complete。
  - remaining risks 是 real-spec calibration、advisory-only diagnostics、shallow schema quality 和 broader OpenAPI complexity。
  - 下一项 compiler expansion task 是 OpenAPI real-world hardening design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Real-World Hardening Design v0 已完成：
  - examples/defaults propagation 被选为第一项 OpenAPI hardening implementation slice。
  - current parser baseline 和 gaps 已文档化。
  - source fields、additive IR changes、deterministic example selection order、generated artifact effects、tests 和 dogfood 已定义。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_WORLD_HARDENING_DESIGN.md`。
- Agent Capability Compiler OpenAPI Examples + Defaults Propagation v0 已完成：
  - OpenAPI parameter/body examples 和 examples maps 已保留进 additive IR fields。
  - README first-call commands、parameter/body details、smoke tests 和 manual write tests 现在会先使用 source examples/defaults/enums，再回落到 generic fallbacks。
  - local generated-runner dogfood 已在 safe loopback target 上通过 read 和 opt-in write calls。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_EXAMPLES_DEFAULTS_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Examples + Defaults Propagation Closeout + Phase Review v0 已完成：
  - examples/defaults propagation 已接受为 complete。
  - remaining risks 是 conservative deep schema coverage、diagnostics 尚未评分 example quality、complex real-spec example objects 和 unresolved OpenAPI auth semantics。
  - 下一项 OpenAPI hardening task 是 security requirement combinations design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_EXAMPLES_DEFAULTS_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Security Requirement Combinations Design v0 已完成：
  - OpenAPI security OR/AND semantics 和 current flattening gaps 已文档化。
  - additive IR metadata、deterministic primary auth selection、bearer/header/query/cookie/OAuth scheme mappings、generated artifact effects、tests、dogfood 和 non-goals 已定义。
  - 下一项 OpenAPI hardening task 是 security requirement combinations implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_DESIGN.md`。
- Agent Capability Compiler OpenAPI Security Requirement Combinations Implementation v0 已完成：
  - OpenAPI OR/AND security requirements 已作为 additive generated package metadata 保留。
  - query API key、cookie API key 和 supported combined auth execution 已在 generated runners 中实现。
  - OAuth/OpenID schemes 作为 metadata-only auth 保留，并带 diagnostics。
  - loopback dogfood 已通过 query、cookie 和 combined auth。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Security Requirement Combinations Closeout + Phase Review v0 已完成：
  - security requirement combinations 已接受为 complete。
  - remaining risks 是 multi-credential proxy product semantics、OAuth metadata-only behavior、coarse API key env naming 和 real specs 中的 complex server layouts。
  - 下一项 OpenAPI hardening task 是 server handling design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Server Handling Design v0 已完成：
  - current server handling baseline 和 gaps 已文档化。
  - additive IR metadata、deterministic selection rules、relative server URL policy、profile hints、generated artifact effects、tests、dogfood 和 non-goals 已定义。
  - 下一项 OpenAPI hardening task 是 server handling implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_DESIGN.md`。
- Agent Capability Compiler OpenAPI Server Handling Implementation v0 已完成：
  - document/path/operation server metadata 已作为 additive generated package metadata 保留。
  - server variables、selected server provenance、relative URL detection 和 profile hints 已实现。
  - README、inspect 和 diagnostics 现在会暴露 server choices 和 override guidance。
  - loopback dogfood 已通过 package-wide 和 tool-specific base URL overrides。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Server Handling Closeout + Phase Review v0 已完成：
  - server handling 已接受为 complete。
  - remaining risks 是 heuristic profile hints、relative URLs requiring runtime origin、no automatic profile switching 和 unresolved schema complexity。
  - 下一项 OpenAPI hardening task 是 schema shaping design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Schema Shaping Design v0 已完成：
  - current schema handling baseline 和 gaps 已文档化。
  - additive compatibility strategy、direction-aware request/response shaping、nullable/readOnly/writeOnly/additionalProperties/array/polymorphism policies、generated artifact effects、diagnostics、tests、dogfood 和 non-goals 已定义。
  - 下一项 OpenAPI hardening task 是 schema shaping implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_DESIGN.md`。
- Agent Capability Compiler OpenAPI Schema Shaping Implementation v0 已完成：
  - direction-aware schema helpers 已实现，未增加 required IR changes。
  - README、inspect、OpenAI tools schema、examples 和 diagnostics 现在使用 shaped schema summaries 和 request-body filtering。
  - nullable、readOnly/writeOnly、additionalProperties、array、polymorphism 和 required/optional cases 已有 fixtures 和 regression tests。
  - local schema-shaping dogfood 已通过，full Python suite 以 193 tests 通过。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Schema Shaping Closeout + Phase Review v0 已完成：
  - schema shaping 已接受为 complete。
  - remaining risks 是 discriminator metadata not yet used、response shaping depth、intentional partial JSON Schema coverage、advisory diagnostics 和 bounded rather than semantic simplification。
  - 下一项 OpenAPI hardening task 是 discriminator handling design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Discriminator Handling Design v0 已完成：
  - current discriminator baseline 和 gaps 已文档化。
  - compatibility strategy、extraction rules、summary formatting、deterministic example rules、generated artifact effects、diagnostics、tests、dogfood 和 non-goals 已定义。
  - 下一项 OpenAPI hardening task 是 discriminator handling implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_DESIGN.md`。
- Agent Capability Compiler OpenAPI Discriminator Handling Implementation v0 已完成：
  - discriminator-aware schema summaries、mapping-driven examples、schema hints、diagnostics 和 tool schema preservation 已实现。
  - discriminator fixture 和 parser/generator/diagnostics/CLI regression tests 已增加。
  - local discriminator dogfood 已通过，full Python suite 以 197 tests 通过。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Discriminator Handling Closeout + Phase Review v0 已完成：
  - discriminator handling 已接受为 complete。
  - remaining risks 是 pragmatic branch matching、bounded mapping resolution、sparse response documentation、advisory diagnostics 和 no runtime branch validation。
  - 下一项 OpenAPI hardening task 是 response shape documentation design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Response Shape Documentation Design v0 已完成：
  - current response documentation baseline and gaps 已文档化。
  - additive response metadata、extraction rules、status categories、README/inspect summaries、diagnostics、tests、dogfood 和 non-goals 已定义。
  - 下一项 OpenAPI hardening task 是 response shape documentation implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_DESIGN.md`。
- Agent Capability Compiler OpenAPI Response Shape Documentation Implementation v0 已完成：
  - additive response metadata、deterministic content selection、README/inspect response summaries、diagnostics、fixture coverage 和 local dogfood 已实现。
  - generated runner behavior 保持 unchanged，old capability JSON without response metadata 仍然 valid。
  - local response-shape dogfood 已通过，full Python suite 以 201 tests 通过。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Response Shape Documentation Closeout + Phase Review v0 已完成：
  - response shape documentation 已接受为 complete。
  - remaining risks 是 documentation-only content negotiation、unvalidated source examples、advisory diagnostics、no runtime output validation 和 partial JSON Schema keyword coverage。
  - 下一项 OpenAPI hardening task 是 JSON Schema keyword coverage design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Design v0 已完成：
  - current keyword coverage baseline and gaps 已文档化。
  - Tier 1 display/example keywords、Tier 2 diagnostics-only keywords、compatibility strategy、generated artifact effects、tests、dogfood 和 non-goals 已定义。
  - 下一项 OpenAPI hardening task 是 JSON Schema keyword coverage implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_DESIGN.md`。
- Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Implementation v0 已完成：
  - compact keyword summaries、deterministic keyword-hint examples、inspect schema hint counts、diagnostics、fixture coverage 和 local dogfood 已实现。
  - raw schema compatibility 保持 intact，Tier 2 advanced keywords 会被诊断，而不是被当作 validator semantics 处理。
  - full Python suite 已通过 205 tests。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI JSON Schema Keyword Coverage Closeout + Phase Review v0 已完成：
  - bounded keyword coverage 被接受为 complete。
  - remaining risks 是 bounded keyword semantics、heuristic examples、summary density、advisory diagnostics 和 OpenAPI 3.1 dialect nuance。
  - 下一项 compiler hardening task 是 OpenAPI real-spec calibration design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Real-Spec Calibration Design v0 已完成：
  - calibration-after-keyword-coverage rationale、corpus slots、metric contract、status thresholds、harness behavior、artifact strategy、tests、dogfood 和 non-goals 已定义。
  - 下一项 compiler hardening task 是 local real-spec calibration harness implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_DESIGN.md`。
- Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Implementation v0 已完成：
  - local offline calibration script、purpose-labeled corpus cases、machine-readable result artifact、status classification、fixture/synthetic-large coverage 和 dogfood 已实现。
  - full Python suite 已通过 210 tests。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Real-Spec Calibration Harness Closeout + Phase Review v0 已完成：
  - local calibration harness 被接受为 complete。
  - 第一个 evidence-driven next gap 是 metadata-rich packages 的 diagnostics score calibration。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler Diagnostics Score Calibration Design v0 已完成：
  - scoring weakness、compatibility strategy、impact classes、initial mapping、score formula、metadata cap、score breakdown、calibration expectations、tests、dogfood 和 non-goals 已定义。
  - 下一项 compiler hardening task 是 diagnostics score calibration implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_DESIGN.md`。
- Agent Capability Compiler Diagnostics Score Calibration Implementation v0 已完成：
  - diagnostics scoring 现在使用 explicit impact profile、score breakdown、metadata cap、repeated action-finding cap 和 readiness zero-penalty handling。
  - real-spec calibration 从 1 pass / 5 warn 改善为 4 pass / 2 warn，同时 write-heavy 和 large-surface cases 仍保持 visible warnings。
  - full Python suite 已通过 212 tests。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler Diagnostics Score Calibration Closeout + Phase Review v0 已完成：
  - calibrated score profile 被接受为 complete。
  - remaining risks 是更广 real specs 上的 action-cap calibration、heuristic score semantics、summary noise、generic examples 和 fixture-heavy corpus coverage。
  - 下一项 compiler hardening task 是 OpenAPI summary noise reduction design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Summary Noise Reduction Design v0 已完成：
  - noise taxonomy、bounded summary budgets、risk-first rendering order、repeated finding folding、README/inspect/diagnostics text effects、calibration summary-density metrics、tests、dogfood 和 non-goals 已定义。
  - 下一项 compiler hardening task 是 OpenAPI summary noise reduction implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_DESIGN.md`。
- Agent Capability Compiler OpenAPI Summary Noise Reduction Implementation v0 已完成：
  - compact inspect aggregate rendering、representative response previews、line clipping、grouped diagnostics text、README package overview/key caveats、calibration summary-density metrics、regression coverage 和 dogfood 已实现。
  - full Python suite 已通过 213 tests。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Summary Noise Reduction Closeout + Phase Review v0 已完成：
  - v0 summary budgets 对当前 corpus 被接受为 sufficient。
  - remaining risks 是 opinionated text-output budgets、large README tool sections、advisory repeated diagnostic groups、generic first-call params 和 fixture-heavy corpus coverage。
  - 下一项 compiler hardening task 是 OpenAPI generic example reduction design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Generic Example Reduction Design v0 已完成：
  - deterministic name-aware fallback rules、priority preservation for source/schema hints、object field context threading、calibration generic example metrics、tests、dogfood 和 non-goals 已定义。
  - 下一项 compiler hardening task 是 OpenAPI generic example reduction implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_DESIGN.md`。
- Agent Capability Compiler OpenAPI Generic Example Reduction Implementation v0 已完成：
  - name-aware parameter/property examples、secret-safe placeholders、numeric/name fallbacks、calibration generic example metrics、regression coverage 和 dogfood reducing default calibration generic first-call params to zero 已实现。
  - full Python suite 已通过 217 tests。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Generic Example Reduction Closeout + Phase Review v0 已完成：
  - deterministic name-aware fallbacks 被接受为 complete。
  - default generated calibration cases 现在报告 zero generic examples 和 empty generic first-call params。
  - Agent Capability Compiler 完成度估计为 98%。
  - 下一项 confidence gap 是 cached real-spec corpus expansion design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Design v0 已完成：
  - source criteria、licensing/cache metadata、redaction policy、artifact layout、manifest changes、metrics、thresholds、tests 和 dogfood expectations 已定义。
  - normal calibration 保持 offline and deterministic。
  - 下一项 compiler hardening task 是 cached real-spec corpus expansion implementation。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_DESIGN.md`。
- Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Implementation v0 已完成：
  - default calibration manifest 已包含 committed Apache-2.0 Petstore excerpt。
  - cached source metadata、checksum validation、path containment 和 additive result fields 已实现。
  - local calibration 现在报告 5 pass、2 warn、0 fail 和 1 skipped。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_IMPLEMENTATION_REPORT.md`。
- Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Closeout + Phase Review v0 已完成：
  - 一个 required cached public-spec case 对 v0 被接受为 sufficient。
  - 更多 cached specs 暂缓到 final compiler consolidation 之后。
  - Agent Capability Compiler 完成度估计为 99%。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_CLOSEOUT_PHASE_REVIEW.md`。
- Agent Capability Compiler Final Re-entry Closeout + Consolidation Review v0 已完成：
  - compiler re-entry scope 被接受为 100% complete。
  - future compiler work 移入 evidence-triggered backlog。
  - 下一条 project lane 回到 hosted Control Plane permission-source design。
  - 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_FINAL_REENTRY_CLOSEOUT_CONSOLIDATION_REVIEW.md`。
- Go Control Plane Hosted Admin Gateway Permission Source Design v0 已完成：
  - gateway-side permission source contract、static dogfood policy shape、endpoint permission mapping、fail-closed semantics、audit/idempotency evidence、tests 和 dogfood expectations 已定义。
  - Control Plane trusted-gateway authenticator 保持第二道 authorization gate。
  - 下一项 hosted-readiness task 是 permission-source implementation。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_DESIGN.md`。
- Go Control Plane Hosted Admin Gateway Permission Source Implementation v0 已完成：
  - local hosted admin gateway contract harness 现在会先通过显式 permission decisions 解析 public bearer tokens，然后才转发。
  - static policy evidence、endpoint permission mapping、typed local failures、trusted header injection 和 Control Plane second-gate denial 已实现。
  - live dogfood 已通过，记录 `admin_audit_events=3`、`idempotency_records=1`，并确认 evidence 中无 raw public token 或 gateway secret 泄漏。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Hosted Admin Gateway Permission Source Closeout + Phase Review v0 已完成：
  - static dogfood permission source 被接受为 v0 trust-boundary proof，不是 production authorization。
  - gateway-local denial、Control Plane second-gate behavior 和 secret-safe evidence 满足 design acceptance criteria。
  - 下一条最高风险 hosted lane 是 tenant-partitioned registry mutation design。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Tenant-Partitioned Registry Mutation Design v0 已完成：
  - project partition ownership rules、global/platform read-only objects 和 provider ownership gaps 已明确。
  - 设计定义了 full-registry replacement 前的 partition diff validation，且不包含 public CRUD 或 automatic propagation。
  - 下一项任务是 partition rules 的 local contract harness。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_DESIGN.md`。
- Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness v0 已完成：
  - local partition validation helpers 和 tests 证明 same-project metadata changes 以及 cross-project/global rejection behavior。
  - provider ownership metadata、partition violation decisions 和 project-scoped idempotency fingerprint evidence 已覆盖。
  - 未新增 HTTP endpoint、public CRUD、automatic propagation 或 production gateway deployment。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness Closeout + Phase Review v0 已完成：
  - helper proof 被接受为足以关闭 v0 contract。
  - remaining risks 是 endpoint wiring、audit persistence、first-class provider ownership、project row policy、durable permissions 和 manual propagation。
  - 下一项任务是 private hosted project mutation endpoint design。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Design v0 已完成：
  - private hosted endpoint contract、trusted principal requirements、project-derived scope、registry-layer transaction seam、partition evidence response shape、idempotency/audit mapping 和 stable error semantics 已定义。
  - implementation 保持 deferred 到下一项任务。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_PRIVATE_ENDPOINT_DESIGN.md`。
- Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Implementation v0 已完成：
  - trusted-gateway-only project partition replacement、registry-layer same-transaction validation、project-scoped idempotency、partition audit evidence、HTTP response evidence、gateway permission mapping 和 regression tests 已实现。
  - live Postgres dogfood 是下一项 evidence task。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_PRIVATE_ENDPOINT_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Live Dogfood + Closeout v0 已完成：
  - real service plus live Postgres dogfood 已通过，覆盖 project partition success、idempotency replay、partition violation、gateway-local readonly denial、audit/idempotency evidence 和 secret-safe artifacts。
  - project mutation endpoint slice 可以关闭。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_PRIVATE_ENDPOINT_LIVE_DOGFOOD_CLOSEOUT.md`。
- Go Control Plane Hosted Permission Store Design v0 已完成：
  - durable permission-store entities、gateway lookup contract、endpoint permission mapping、failure semantics、consistency/cache rules、audit evidence 和 contract harness requirements 已定义。
  - 设计在概念上替换 static dogfood policy，同时不加入 public role CRUD、OAuth/OIDC、production gateway deployment、marketplace、vault、billing、workflow 或 automatic propagation scope。
  - 下一项 hosted-readiness task 是 lookup boundary 的 contract harness。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_DESIGN.md`。
- Go Control Plane Hosted Permission Store Contract Harness v0 已完成：
  - local hosted admin gateway harness 现在会先通过 store-shaped subject/membership/role/grant read model 解析 public principals，然后才 forward。
  - policy version、fingerprint、decision id、required permission evidence、gateway-local membership/revocation/stale-policy failures 和 Control Plane second-gate behavior 已覆盖。
  - 下一项 hosted-readiness task 是 contract harness closeout and phase review。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Hosted Permission Store Contract Harness Closeout + Phase Review v0 已完成：
  - store-shaped lookup proof 被接受为 v0。
  - remaining risks 是 durable schema、policy write lifecycle、real public identity lifecycle、production gateway deployment、cache/consistency persistence 和 provider ownership hardening。
  - 下一项 hosted-readiness task 是 hosted permission store schema。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Hosted Permission Store Schema v0 已完成：
  - hosted subject、membership、role、role binding、permission grant、policy version 和 permission decision tables 已定义在 Postgres schema 中。
  - constraints 和 indexes 保留 private read-model boundary、fail-closed lookup evidence 和 secret-safe storage assumptions。
  - 下一项 hosted-readiness task 是 schema closeout and phase review。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Hosted Permission Store Schema Closeout + Phase Review v0 已完成：
  - durable hosted permission-store schema boundary 被接受为 v0。
  - remaining risks 是 runtime read model wiring、seed/migration lifecycle、policy write lifecycle、real public identity lifecycle、production gateway deployment、runtime consistency 和 provider ownership hardening。
  - 下一项 hosted-readiness task 是 hosted permission store read model。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Hosted Permission Store Read Model v0 已完成：
  - internal repeatable-read/read-only Go read model 可以从 hosted permission tables 解析 active policy、subject、project membership、active roles、grants 和 gateway-compatible decision evidence。
  - missing membership、suspended membership、revoked grants、missing permission、no active policy 和 ambiguous active policy 已在 registry package tests 中 fail closed。
  - gateway runtime wiring、decision persistence、public CRUD、OAuth/OIDC、production gateway deployment、vault、billing、marketplace、workflow 和 automatic propagation 继续保持 out of scope。
  - 下一项 hosted-readiness task 是 read model closeout and phase review。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Hosted Permission Store Read Model Closeout + Phase Review v0 已完成：
  - internal read-model implementation 被接受为 v0。
  - remaining risks 是 live Postgres seeded proof、gateway runtime wiring、decision persistence、seed/migration lifecycle、policy write lifecycle、real public identity lifecycle、production gateway deployment 和 provider ownership hardening。
  - 下一项 hosted-readiness task 是 read model 的 live Postgres dogfood。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood v0 已完成：
  - 真实 local Postgres dogfood 现在会 apply schema、seed hosted permission rows，并用 pgx 调用 internal read model。
  - allowed admin evidence、missing membership、suspended membership、revoked/missing permission、no active policy 和 ambiguous active policy 已在真实 SQL 上证明。
  - decision evidence 保持 secret-safe，且 v0 中 `hosted_permission_decisions` 保持为空。
  - 下一项 hosted-readiness task 是 live Postgres dogfood closeout and phase review。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_LIVE_POSTGRES_DOGFOOD_REPORT.md`。
- Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood Closeout + Phase Review v0 已完成：
  - real Postgres read-model proof 被接受为 v0。
  - remaining risks 是 gateway runtime wiring、decision persistence、seed/migration lifecycle、policy write lifecycle、real public identity lifecycle、production gateway deployment 和 provider ownership hardening。
  - 下一项 hosted-readiness task 是 hosted read-model permission source 的 gateway runtime wiring design。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_LIVE_POSTGRES_DOGFOOD_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Design v0 已完成：
  - design 定义了 gateway runtime permission-source interface、read-model request/decision shape、public principal inputs、project context、endpoint mapping、trusted header mapping、timeout/unavailable behavior、tests 和 dogfood requirements。
  - runtime implementation、decision persistence、public CRUD、OAuth/OIDC、production gateway deployment、vault、billing、marketplace、workflow 和 automatic propagation 保持 out of scope。
  - 下一项 hosted-readiness task 是 gateway runtime wiring implementation。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_READ_MODEL_GATEWAY_RUNTIME_WIRING_DESIGN.md`。
- Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Implementation v0 已完成：
  - local gateway harness 现在有 hosted read-model permission-source mode，通过 local Go lookup helper 和 Postgres DSN 支撑。
  - static fixture mode 仍保留给 focused tests。
  - live Postgres dogfood 证明 gateway-local public auth、read-model allow/deny decisions、trusted header injection、Control Plane second-gate behavior、no active/ambiguous policy 503、zero persisted permission decisions 和 secret-safe evidence。
  - public CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、decision persistence、vault、billing、marketplace、workflow 和 automatic propagation 仍然 out of scope。
  - 下一项 hosted-readiness task 是 gateway runtime wiring closeout and phase review。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_READ_MODEL_GATEWAY_RUNTIME_WIRING_IMPLEMENTATION_REPORT.md`。
- Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Closeout + Phase Review v0 已完成：
  - runtime wiring proof 被接受为 v0。
  - static fixture fallback 仍然 useful 且 bounded，live Postgres dogfood 覆盖 read-model-backed gateway path。
  - remaining risks 是 decision persistence、dogfood-scoped helper boundary、real public identity lifecycle、policy write lifecycle、production gateway deployment 和 provider ownership hardening。
  - 下一项 hosted-readiness task 是 hosted permission decision persistence design。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_READ_MODEL_GATEWAY_RUNTIME_WIRING_CLOSEOUT_PHASE_REVIEW.md`。
- Go Control Plane Hosted Permission Decision Persistence Design v0 已完成：
  - design 定义了 append-only hosted permission decision evidence、gateway ownership、row shape、source-unavailable sentinel evidence、write timing、persistence-failure behavior、secret-safe metadata、retention boundaries、tests 和 live dogfood requirements。
  - public CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace、vault、billing、workflow、automatic propagation、policy write APIs 和 Data Plane mutable reads 仍然 out of scope。
  - 下一项 hosted-readiness task 是 hosted permission decision persistence implementation。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_DESIGN.md`。
- Go Control Plane Hosted Permission Decision Persistence Implementation v0 已完成：
  - local gateway harness 现在会为 allowed、denied 和 source-unavailable authenticated gateway decisions 写入 append-only hosted permission decision rows。
  - missing/invalid public auth 与 unknown route/method failures 仍保持在 hosted decision persistence 之外。
  - live Postgres dogfood 证明 15 条 secret-safe persisted decision rows、allowed-write-failure fail-closed behavior、invalid public auth 后 zero decision rows，以及 Control Plane audit/idempotency boundaries 不变。
  - public CRUD、OAuth/OIDC、invitation/session lifecycle、production gateway deployment、marketplace、vault、billing、workflow、automatic propagation、policy write APIs 和 Data Plane mutable reads 仍然 out of scope。
  - 下一项 hosted-readiness task 是 hosted permission decision persistence closeout and phase review。
  - 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_IMPLEMENTATION_REPORT.md`。

下一项工程任务：

```text
Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0
```

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_LIVE_POSTGRES_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_AUTHENTICATOR_INTEGRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_PRIVATE_ENDPOINT_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_PRIVATE_ENDPOINT_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_PRIVATE_ENDPOINT_LIVE_DOGFOOD_CLOSEOUT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_SCHEMA_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_LIVE_POSTGRES_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_STORE_READ_MODEL_LIVE_POSTGRES_DOGFOOD_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_READ_MODEL_GATEWAY_RUNTIME_WIRING_DESIGN.md`
- `docs/cn-ZH/API2AGENT_HOSTED_CONTROL_PLANE_PAUSE_AND_AGENT_COMPILER_REENTRY.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_WORLD_HARDENING_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_EXAMPLES_DEFAULTS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_EXAMPLES_DEFAULTS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_DESIGN.md`

## 9. Marketplace 是后面的结果

在以下条件成立前，不要做 marketplace UI：

- proxy works
- credential orchestration exists
- metrics exist
- capability abstraction exists
- routing works
- pricing metadata exists

Marketplace 应该是 routing plus economics 的结果，不是起点。
