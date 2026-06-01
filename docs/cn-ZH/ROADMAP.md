# API2Agent 路线图

## 1. 路线图职责

这份文档是唯一实施计划。

后续工作必须按照这份路线图推进，除非先明确更新路线图。

`docs/cn-ZH/API2AGENT_PROTOCOL.md` 定义这份 roadmap 要实现的 protocol 方向。

当前产品方向：

```text
可用 -> 可控 -> 可计量 -> 可比较 -> 可路由 -> 可靠执行
```

当前 execution focus：

```text
Agent request -> SDK call -> Adapter -> Real API -> Normalized output -> Usage -> Ledger
```

当前构建目标：

```text
API2Agent
```

当前阶段：

```text
Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness Closeout Complete
```

文档模式：

- 遵循 `docs/DOCUMENTATION_POLICY.md`
- 将 Hosted Control Plane 的 compact progress 追加到 `docs/HOSTED_CONTROL_PLANE_PHASE_LOG.md`
- 除非 durable API、storage、security、protocol、deployment、customer-data 或 major product-direction boundary 发生变化，否则避免新增 per-slice reports 或 closeouts

战略判断：

> API2Agent 起步是本地 Agent capability compiler，之后演进为 Agent 访问 API-backed capabilities 的 control、metrics、routing 和 reliable execution layer。

Tooling re-entry 判断：

> API2Agent 已完成一次带 Control/Data Plane 约束的 Tooling Layer 回切。Tooling Layer 继续优化更多真实执行数据、更低 API/provider 接入成本、更快 Agent API 响应，同时保持 API-first，不变成 workflow engine。详见 `docs/cn-ZH/API2AGENT_TOOLING_REENTRY_REVIEW_AND_EXPANSION_PLAN.md`。

Receipt and trust thesis：

> API2Agent 未来应该把 internal usage observations 演进为 verifiable receipts，用于 routing、trust、anti-gaming controls 和未来 settlement。这是战略方向，不是当前 implementation task。详见 `docs/cn-ZH/CONTROL_RECEIPT_AND_TRUST_LAYER_STRATEGY.md`。

Capability source 边界：

> v0.1-alpha 坚持 API-first。长期来看，API2Agent 可以支持任何能被适配成 `input -> execution -> output` 的来源，但非 API sources 只能在 API execution 可靠之后作为 future adapters 进入。详见 `docs/cn-ZH/CAPABILITY_SOURCES.md`。

v0.1-alpha 产品抓手：

```text
Reliability + Observability
```

alpha 必须证明 API2Agent 能让 Agent 调 API 比直接调用 provider 更可靠、可计量、可调试。

Marketplace 是远期可选结果。它不是当前产品，不是当前 MVP，也不是 active implementation phase。

## 2. 当前状态

已经实现：

- local OpenAPI/curl compiler
- API2Agent IR
- capability package generation
- generated runner
- generated MCP server
- smoke test
- tool filtering / selection
- local API2Agent Proxy
- SQLite usage event store
- usage summary command
- project-level quota
- generated runner proxy mode
- Capability Schema v0.1 code model
- Provider Candidate model
- Metrics Snapshot model
- Routing Policy model
- Routing v0 provider selection command
- local routing execution loop
- output normalization metadata and execution
- `weather.get` 的 SDK E2E core loop
- 两个 weather providers 的重复 benchmark，包含 p50/p95 latency
- SDK 根据本地 observed metrics 进行默认 provider selection
- SDK 显式 routing strategy selection
- SDK failover，并把失败 attempt 和 fallback attempt 都记录到 usage events
- v0.1-alpha plan 已把 Reliability + Observability 定为产品抓手
- CHANGELOG
- alpha Quickstart，覆盖 SDK call、benchmark、failover、ledger 和 compiler path
- clean baseline commit：`7157226`
- replay preflight command，用于 usage event audit
- SDK、proxy 和 local package execution paths 已安全捕获 replay metadata
- alpha capability naming validation warnings
- SDK shadow execution mode
- supported SDK 和 no-credential HTTP events 的 exact replay execution
- optional replay usage recording，使用 `execution_mode=replay`
- `shadow` 和 `replay` 的 routing metrics policy 已显式化
- usage events 的 golden trace marker
- golden trace filtering command
- local generated package replay execution
- generated package shadow execution mode
- Credential Orchestration strategy document
- Credential Schema v0.1 code models
- local Credential Resolver
- generated package execution 的 credential injection patches
- credential-safe usage attribution and replay
- capability source boundary document
- MVP exit review
- Architecture Definition Phase document
- API2Agent Protocol v0.2 plan
- API2Agent Protocol v0.2 frozen contract
- API2Agent Protocol v0.2 schema snapshot
- API2Agent Protocol v0.2 hardening constraints：request context、versions、metrics windows 和 plan/observation split
- Production Architecture RFC，明确 Go Data Plane 和 Go Control Plane backend 方向
- Python reference migration plan
- Go Data Plane Skeleton plan
- Go Data Plane Skeleton implementation，位于 `services/data-plane`
- Go/Python dual-run dogfood，覆盖 `network.public_ip.get`
- Go Data Plane Skeleton hardening，覆盖 health、auth、timeout、snapshot TTL 和 failure-event tests
- Go Data Plane protocol conformance checks，基于 v0.2 schema snapshot
- Go Data Plane retry/failover execution 和 controlled failover dogfood
- Go Data Plane env credential resolution skeleton 和 controlled credential dogfood
- Go Data Plane durable event ingestion 和 real external provider retry dogfood
- Go Data Plane stage review 和 consolidation hardening plan

尚未实现：

- non-API capability source adapters
- hard enforcement of capability naming rule
- endpoint-level auth
- base URL override
- manual write tests
- hosted proxy
- credential vault
- durable multi-project backend
- capability registry persistence
- billing

当前 API2Agent 范围明确不包含：

- workflow engine execution
- local function runtime
- arbitrary script sandbox
- database runtime
- human task routing
- agent-as-provider execution
- marketplace UI
- marketplace search
- provider revenue share
- public provider onboarding

## 3. Phase 1：Usable Tooling MVP

状态：已实现，需要继续做回归保护。

目标：

让真实 REST API 可以通过本地 generated package 被 Agent 调用。

范围：

- OpenAPI JSON/YAML input
- curl input
- API2Agent IR
- generated `capability.json`
- generated `tools.json`
- generated `runner.py`
- generated `smoke_test.py`
- generated `mcp_server.py`
- `api2agent generate`
- `api2agent inspect`
- `api2agent test`
- `api2agent run`

退出标准：

- 真实 API specs 可以生成 package
- read-only smoke tests 可以安全运行
- generated MCP server 可以被 MCP client 调用
- tests 覆盖 parser、generator、runner、MCP、CLI behavior

禁止扩展：

- 不做 marketplace UI
- 不做 hosted SaaS
- 不做 payment
- control-plane dogfood 前不扩大量新输入格式

## 4. Phase 2：Controllable Execution MVP

状态：第一版本地实现已完成；public-read 和 authenticated proxy dogfood 已完成。

目标：

从 direct execution 进入 observed and controlled execution。

范围：

- local `api2agent proxy`
- `POST /v1/proxy/call`
- generated runner 通过 `API2AGENT_PROXY_URL` 进入 proxy mode
- usage event schema
- SQLite usage store
- `api2agent usage`
- project-level quota
- latency/success/failure/status tracking
- estimated per-call cost field

退出标准：

- 一个 generated package 可以通过 proxy 调用
- proxy 可以记录 success 和 failure 的 usage events
- quota 在 forward 前阻止调用
- usage report 展示 total calls、success rate、latency、cost、errors
- dogfood report 覆盖至少 3 个真实 API 的 proxy mode

当前 dogfood 结果：

- JSONPlaceholder、GitHub rate_limit、httpbin 都通过 proxy mode 成功。
- httpbin bearer auth 通过 proxy mode 成功。
- 第 4 次调用的 quota blocking 正常。
- 详见 `docs/cn-ZH/CONTROL_LAYER_DOGFOOD_REPORT.md`。

禁止扩展：

- 不接 billing integration
- 不做 provider revenue share
- local proxy 行为验证前不做 hosted deployment

## 5. Phase 3：Capability Metrics MVP

状态：第一版 code model 已实现；local two-provider metrics dogfood 已完成。

目标：

把 raw usage events 变成同一个 semantic capability 下可比较的 provider metrics。

范围：

- Capability Definition
- Provider Candidate
- Metrics Snapshot
- usage aggregation by capability/provider
- minimal provider registry JSON
- metrics fields:
  - total calls
  - success rate
  - average latency
  - estimated cost per call

退出标准：

- 两个 provider candidates 可以映射到同一个 capability
- usage events 可以聚合为每个 provider 的 metrics
- 文档定义什么叫两个 provider 可比较
- 一个本地 demo 比较两个 mock 或真实 providers

当前 dogfood 结果：

- `image_generation` 在 `fast_cheap` 和 `reliable_expensive` 之间完成比较。
- metrics 可以改变不同 strategies 下的 routing outcome。
- 详见 `docs/cn-ZH/CAPABILITY_ROUTING_DOGFOOD_REPORT.md`。

禁止扩展：

- 不做 public registry
- 不做 provider onboarding
- 不做人工 marketplace curation

## 6. Phase 4：Routing v0

状态：provider selection 已实现并完成 dogfood；execution loop 未实现。

目标：

使用 policy 和 observed metrics 为 capability 选择 provider candidate。

范围：

- `api2agent route`
- strategy:
  - first
  - random
  - lowest_cost
  - lowest_latency
  - highest_success_rate
  - balanced
- ranked provider output
- routing policy model

退出标准：

- route command 可以从 registry 中选择 provider
- route command 在有 usage metrics 时使用 metrics
- tests 覆盖 strategy behavior
- 一个 dogfood scenario 证明 metrics 变化会改变 routing selection

当前 dogfood 结果：

- `lowest_cost` 和 `lowest_latency` 选择 `fast_cheap`。
- `highest_success_rate` 选择 `reliable_expensive`。
- `balanced` 选择 `fast_cheap`，暴露出需要显式 routing policy presets。
- routing decision event 和 policy presets 已定义。

当前真实 provider 结果：

- 真实 `public_ip_lookup` dogfood 已用 ipify 和 httpbin 完成。
- 两个 providers 都成功，但返回结构不同。
- 详见 `docs/cn-ZH/REAL_TWO_PROVIDER_DOGFOOD_REPORT.md`。

未接受本阶段前禁止实现：

- automatic routing execution loop
- failover execution
- hosted routing service

## 7. Phase 5：Routing Execution Loop

状态：最小本地实现已完成并 dogfooded；下一步是加固 decision/usage correlation。

目标：

从“选择 provider”进入“通过被选中的 provider 执行 capability request”。

范围：

- capability request input format
- registry lookup
- provider selection
- provider tool execution through proxy
- routing decision event
- routing decision ledger
- 通过 `routing_decision_id` 关联 usage event
- output normalization through `output_mapping`
- failed provider call 后的 Failover Policy v0

退出标准：

- 一次 capability request 可以通过被选中的 provider 执行
- routing decision 被记录
- selected provider result 会 normalize 成 capability output contract
- primary provider 失败后可以可选 fallback 到 secondary provider
- failover 可以被 max attempts、error type 和 HTTP status 限制
- usage event 和 routing event 可以关联

最小本地实现：

```text
capability registry JSON
  -> select provider
  -> load provider generated package
  -> execute provider tool through proxy
  -> normalize output
  -> return routing decision + normalized result
```

禁止扩展：

- 不做 marketplace search
- 不做 billing
- 不做 third-party provider onboarding
- 不做 hosted routing service

进入条件：

- routing decision event defined
- routing policy presets documented
- real two-provider dogfood completed
- output normalization requirements documented

当前 gate 结果：

- entry requirements 暴露出一个必要中间步骤：Capability Schema v0.2 for output normalization。
- v0.2 output normalization metadata 已定义。
- 下一道实现 gate 是在 routing execution 中应用 normalized outputs，而不是修改 provider selection。

当前 dogfood 结果：

- `public_ip_lookup` 已通过被选中的 local generated provider packages 执行。
- ipify 和 httpbin 都 normalize 成 `{ "ip": "..." }`。
- 详见 `docs/cn-ZH/ROUTING_EXECUTION_DOGFOOD_REPORT.md`。
- routing decision ledger 和 local usage ledger 已通过真实 ipify、httpbin proxy calls 完成 dogfood。
- 详见 `docs/cn-ZH/ROUTING_LEDGER_DOGFOOD_REPORT.md`。
- failover ledger behavior 已通过真实 HTTP 500 provider 加 ipify fallback 完成 dogfood。
- 详见 `docs/cn-ZH/FAILOVER_LEDGER_DOGFOOD_REPORT.md`。
- Failover Policy v0 已通过真实 HTTP 500 和 HTTP 400 providers 完成 dogfood。
- 详见 `docs/cn-ZH/FAILOVER_POLICY_DOGFOOD_REPORT.md`。
- routing decision inspection command 已实现，并用真实 failover dogfood database 验证。
- stable decision/usage contract fields 已文档化，并用 regression fixtures 覆盖。
- decision output 现在包含 `contract_version`。
- provider registry JSON 在 route/call execution 前会做 schema validation。
- provider registry contract fields 已文档化，并用 contract fixtures 覆盖。
- registry inspection command 已实现。
- route/call JSON output 现在包含 `registry_contract_version`。
- registry inspection 现在会报告 local package warnings。
- call execution 对请求 capability 的 provider local package metadata 会在 execution 前 fail fast。
- registry inspection 已用 generated ipify 和 httpbin provider packages dogfood，结果 zero warnings。
- `api2agent call` 已用同一个 registry dogfood，并返回 `registry_contract_version`。
- direct local execution 现在不经过 proxy 也会记录 usage events。
- direct local mode 已用 `api2agent decision` 和 `api2agent ledger` 完成 dogfood。
- usage events 现在包含 `execution_mode`。
- direct 和 proxy execution modes 都已通过 `api2agent decision` 验证。
- direct-vs-proxy audit regression fixture 已增加。
- `api2agent ledger --group-by-mode` 现在可以区分 direct 和 proxy rows。
- usage ledger contract fields 已文档化，并用 fixtures 覆盖。
- ledger 现在支持 project、capability、provider 和 month filters。
- `weather.get` + Open-Meteo 的 SDK E2E core loop 已实现并完成 dogfood。
- 第二个 weather provider `wttr_in` 已实现。
- `API2Agent Benchmark v0.1` 已对比 `open_meteo` 和 `wttr_in`。
- repeated benchmark calls 现在会计算 total calls、success rate、p50 latency、p95 latency、estimated vs observed cost。
- 默认 SDK routing 现在会使用本地 observed metrics；benchmark 数据显示 `wttr_in` 平均延迟更低后，默认调用选择了 `wttr_in`。
- SDK caller 现在可以显式传入 `first`、`lowest_latency`、`lowest_cost`、`highest_success_rate` 或 `balanced` 等 routing strategy。
- SDK failover 现在会把 failed attempt 和 successful fallback attempt 记录在同一个 routing decision 下。
- SDK failover 已用 controlled `open_meteo` 500 failure 加真实 `wttr_in` fallback 完成 dogfood。
- 详见 `docs/cn-ZH/SDK_FAILOVER_DOGFOOD_REPORT.md`。

立即下一步：

- 决定 capability naming 何时从 warning 升级为 hard enforcement
- 保持 policy 本地、显式，不引入隐藏的 marketplace-style provider preference

## 8. Phase 5.5：v0.1-alpha 产品抓手加固

状态：计划中。

目标：

把已经可运行的 local infra primitive 收口成以 Reliability + Observability 为核心的 alpha 产品。

范围：

- clean repo baseline
- CHANGELOG
- alpha Quickstart
- capability naming rule：`<domain>.<resource>.<action>`
- replay design and local command
- execution mode matrix：
  - `direct`
  - `proxy`
  - `shadow`
  - future `race`
- golden trace contract field
- 一个完整 alpha demo：
  - one capability
  - two providers
  - primary failure
  - fallback success
  - benchmark comparison
  - ledger inspection

退出标准：

- 新开发者可以按文档复现 alpha demo
- failed attempt 和 fallback attempt 都能在 ledger 中看到
- provider comparison 包含 success rate 和 p50/p95 latency
- replay 已本地实现，或明确文档化为下一项 alpha task
- marketplace 仍然不进入当前范围

当前 hardening 结果：

- `CHANGELOG.md` 已创建。
- 双语 Quickstart 已创建。
- Quickstart compiler path 已用 `generate`、`inspect`、`test` 验证。
- Quickstart failover path 已用 controlled `open_meteo` failure 加真实 `wttr_in` fallback 验证。
- clean baseline commit 已创建：`7157226`。
- `api2agent replay` preflight 已用失败的 Quickstart usage event 验证。
- replay metadata capture 已验证，返回 `exact_replay_metadata_ready: true`。
- alpha capability naming warnings 已用 legacy `public_ip_lookup` 验证。
- SDK shadow mode 已用真实 `open_meteo` main result 和真实 `wttr_in` shadow result 验证。
- 详见 `docs/cn-ZH/SHADOW_MODE_DOGFOOD_REPORT.md`。
- exact replay execution 已用真实 `wttr_in` shadow event 验证。
- 详见 `docs/cn-ZH/REPLAY_DOGFOOD_REPORT.md`。
- replay recording 已验证为 ledger row，并且不进入 routing metrics。
- shadow metrics policy 已验证：默认包含，可用显式选项排除。
- golden trace marker 已用真实 `wttr_in` shadow event 验证。
- 详见 `docs/cn-ZH/GOLDEN_TRACE_DOGFOOD_REPORT.md`。
- golden trace listing 和 `ledger --golden-only` filtering 已实现。
- generated package shadow execution mode 已在 `api2agent call` 中实现。
- local generated package replay execution 已支持 `local_package:<package_dir>` events。
- generated package shadow + replay 已用本地 package 和真实 no-auth API package 完成 dogfood；详见 `docs/cn-ZH/GENERATED_PACKAGE_SHADOW_REPLAY_DOGFOOD_REPORT.md`。

## 8.6 Phase 5.6：Credential Orchestration MVP

状态：第一版本地实现已完成。

目标：

让 API2Agent 具备 credential-aware 能力，但不直接做 payment 或 hosted vault。

范围：

- Credential Schema v0.1
- credential owner model：
  - user
  - project
  - platform
  - provider
- credential sources：
  - env
  - config
  - inline
  - none
- local credential resolver
- credential injection patch
- usage event `credential_reference`
- request metadata 和 replay metadata 中的 secret redaction

退出标准：

- 一个 authenticated API 可以通过 resolved credentials 调用
- raw secrets 不进入 usage events
- required credential 无法 resolve 时，replay 会 warning
- ledger 可以保留 credential attribution，且不暴露 secrets

禁止扩展：

- 不做 hosted vault
- 不做 payment processing
- 不做 provider settlement
- 不做 marketplace credential onboarding

已完成 architecture definition task：

```text
Protocol v0.2 contract freeze
Production Architecture RFC
```

立即下一步任务：

```text
先完成 durable event ingestion，再执行 real external provider retry dogfood
```

当前实现结果：

- `api2agent/credentials/models.py` 定义 Credential Schema v0.1 objects。
- `api2agent/credentials/resolver.py` 支持 env/config/inline/none credentials。
- generated runners 可以通过 local execution env 消费 credential injection patches。
- `execute_capability` 会 resolve credentials，并写入 `credential_reference`。
- local package replay 可以基于 redacted metadata 重新 resolve credentials。
- proxy mode 下，generated runners 现在只发送 credential intent，不发送 provider secrets。
- local proxy 会解析 credential intent，在转发前注入 provider auth，并记录脱敏后的 usage attribution。
- local proxy 可以加载 project-level credential config files。
- payload 不携带 credential intent 时，proxy 也可以使用 config credentials。
- credential resolver precedence 已明确：inline、config、request/env intent、none。
- config credential owner matching 会优先选择 exact project owner，然后是 local project owner，最后才按 config order。
- credential scope matching 现在支持 provider、capability、tool 和 wildcard scope entries。
- out-of-scope credentials 会返回 `credential_scope_denied`，且不会 fallback 到低优先级 credential。
- credential lifecycle metadata 现在包含 status、expiry 和 rotation hints。
- disabled 和 expired credentials 会在 secret resolution 之前返回 machine-readable errors。
- usage CLI 现在可以通过 `api2agent usage --credential-audit` 打印 credential audit events。
- credential audit output 使用 allowlist，并聚合 credential-related failures。
- authenticated proxy credential dogfood 已通过真实 `https://httpbin.org/bearer` API 验证。
- local BYOK loop 现在覆盖 config credential resolution、auth injection、usage ledger 和 audit CLI。
- 战略优先级已经提高：拥有真实执行数据、最小化 API/provider onboarding cost。
- location-aware execution 现在是 Phase 6+ routing requirement；详见 `docs/cn-ZH/LOCATION_AWARE_ROUTING.md`。
- usage events 和 SQLite storage 现在支持 optional region 和 latency breakdown fields。
- provider candidates 现在支持 `regions` 和 `geo_affinity`。
- `DecisionDatasetRecord` 定义了第一版 local decision dataset contract。
- `region_aware_latency` routing strategy 现在会按 client-region affinity 和 latency metrics 排序 providers。
- `api2agent route` 和 `api2agent call` 现在支持 `--client-region`。
- routing decisions 现在会持久化 `client_region`，用于 audit 和 decision dataset。
- `run_region_aware_routing_benchmark` 现在会返回 routing decision 和 decision-dataset record。
- route/call 现在会为 `region_aware_latency` 读取 aggregate metrics 和 matching client-region metrics。
- routing decisions 现在会持久化确定性的 `selected_provider_region`。
- generated package usage events 现在会记录推导后的 `provider_region`。
- credential resolver dogfood 已完成；详见 `docs/cn-ZH/CREDENTIAL_RESOLVER_DOGFOOD_REPORT.md`。
- proxy credential injection dogfood 已完成；详见 `docs/cn-ZH/PROXY_CREDENTIAL_INJECTION_DOGFOOD_REPORT.md`。
- proxy credential config dogfood 已完成；详见 `docs/cn-ZH/PROXY_CREDENTIAL_CONFIG_DOGFOOD_REPORT.md`。
- credential policy dogfood 已完成；详见 `docs/cn-ZH/CREDENTIAL_POLICY_DOGFOOD_REPORT.md`。
- credential scope dogfood 已完成；详见 `docs/cn-ZH/CREDENTIAL_SCOPE_DOGFOOD_REPORT.md`。
- credential lifecycle dogfood 已完成；详见 `docs/cn-ZH/CREDENTIAL_LIFECYCLE_DOGFOOD_REPORT.md`。
- credential audit CLI dogfood 已完成；详见 `docs/cn-ZH/CREDENTIAL_AUDIT_CLI_DOGFOOD_REPORT.md`。
- authenticated proxy credential dogfood 已完成；详见 `docs/cn-ZH/AUTHENTICATED_PROXY_CREDENTIAL_DOGFOOD_REPORT.md`。
- location-aware schema dogfood 已完成；详见 `docs/cn-ZH/LOCATION_AWARE_SCHEMA_DOGFOOD_REPORT.md`。
- Go Data Plane durable event ingestion 已完成；详见 `docs/cn-ZH/GO_DATAPLANE_DURABLE_EVENTS_DOGFOOD_REPORT.md`。
- Go Data Plane real external provider retry dogfood 已完成；详见 `docs/cn-ZH/GO_DATAPLANE_REAL_EXTERNAL_PROVIDER_RETRY_DOGFOOD_REPORT.md`。
- Go Data Plane stage review 已完成；详见 `docs/cn-ZH/GO_DATAPLANE_STAGE_REVIEW.md`。

实施 checklist：

1. Credential data models - complete
   - 新增 `api2agent/credentials/models.py`
   - 定义 `CredentialDefinition`、`CredentialSource`、`CredentialResolutionRequest`、`ResolvedCredential` 和 `CredentialInjectionPatch`
   - 校验 `owner_type`、`auth_type`、`injection_mode` 和 `source`
2. Local Credential Resolver - complete
   - 新增 `api2agent/credentials/resolver.py`
   - 按以下顺序 resolve：inline override、project config、environment variable、none
   - 返回 redacted credential reference 和 injection patch
3. Execution integration - complete
   - 把 resolver 接入 generated package / routing execution path
   - 把 resolved credentials 注入 provider requests
   - 保持 direct local mode 可用
4. Usage attribution - complete
   - 把 `credential_reference` 写入 usage events
   - 确保 raw secrets 不进入 usage event metadata、decision output、ledger output 或 logs
5. Replay and masking behavior - complete
   - required credentials 无法 resolve 时，replay 必须 warning
   - credentials 可 resolve 时，replay 可以执行
   - replay metadata 保持 redacted
6. Proxy-side credential injection - complete
   - generated runners 会把 credential intent 发送给 proxy
   - proxy 会解析 env-based credential intent，并在转发前注入 provider auth
   - proxy credential 缺失时，会生成 failed usage event，且不调用 provider
   - proxy usage metadata 只保存 redacted credential metadata
7. Credential config loading for local proxy - complete
   - 新增 JSON/YAML credential config loader
   - 新增 `api2agent proxy --credential-config`
   - 允许 proxy resolver 在 payload 没有 credential intent 时使用 config credentials
   - config credential secrets 不进入 usage metadata
8. Credential precedence and ownership policy hardening - complete
   - 暴露 deterministic credential precedence
   - 优先选择当前 `project_id` 拥有的 config credentials
   - fallback 到 local owner，再 fallback 到 config order
   - redacted resolver output 保留 owner metadata
9. Credential scope matching for capability and tool access - complete
   - 支持 `provider:<id>`、`capability:<id>`、`tool:<id>`、`*` 和 `*:*`
   - empty scope 对 matching provider 表示 unrestricted
   - out-of-scope credentials 返回 `credential_scope_denied`
   - 高优先级 credential out-of-scope 后，不允许继续 fallback 到低优先级 credential
10. Credential rotation metadata and audit events - complete
   - 为 credential definitions 新增 `status`、`expires_at` 和 `rotation_hint`
   - disabled credentials 返回 `credential_disabled`
   - expired credentials 返回 `credential_expired`
   - redacted resolver metadata 保留 lifecycle fields
11. Credential audit reporting in usage CLI - complete
   - 新增 `api2agent usage --credential-audit`
   - 新增 JSON 和 text audit output
   - 包含 `credential_reference`、selected metadata 和 credential failure counts
   - 省略非 allowlisted metadata，例如 `secret_value`
12. Authenticated proxy credential dogfood with a real API - complete
   - 使用 credential config authenticate 一个真实 provider request
   - 验证 provider 可以收到 Bearer auth
   - 验证 usage metadata 和 audit CLI 保持 secret-safe
   - 在双语 docs 中记录 dogfood results

验收测试集：

- resolver 可以读取 env credentials
- resolver 可以读取 config credentials
- inline credential override 优先级最高
- `auth_type=none` 不要求 credentials
- authenticated provider 能收到 injected header/query/body patch
- usage event 包含 `credential_reference`
- raw secret 不存在于 SQLite usage metadata
- replay 能清晰报告 missing credential
- credential 可 resolve 时 replay 可以执行
- proxy 能把 resolved credentials 注入 forwarded requests
- proxy 会把 missing credentials 记录到 ledger，且不会继续 forward
- proxy 可以加载 config credentials 并完成注入，且 metadata 不包含 raw secret
- resolver 会按 inline、config、request credentials 的顺序选择
- resolver 会先选择 project-owned config credentials，再选择 local fallback
- resolver 允许 matching capability/tool scopes
- resolver 会拒绝 out-of-scope credentials，且不暴露 raw secrets
- resolver 会用 redacted metadata 拒绝 disabled 和 expired credentials
- resolver 会为 accepted credentials 记录 lifecycle audit metadata
- usage CLI 可以打印 credential audit JSON，且不暴露 raw secrets
- usage CLI 可以打印 credential audit text，且不暴露 raw secrets
- authenticated real API dogfood 返回 provider `authenticated=true`
- credential audit CLI 可以报告 real API event，且不泄漏 raw token

下一步战略设计要求：

- 执行 Go Data Plane Consolidation Hardening v0：
  - reusable Protocol v0.2 conformance validator
  - event write failure policy
  - runtime provider availability probe

## 8.7 Phase 5.7：Architecture Definition Phase

状态：active。

目标：

在继续实现前，冻结 protocol 和 production architecture。

范围：

- Protocol v0.2 contract freeze
- Production Architecture RFC
- Control Plane vs Data Plane boundary
- data model finalization
- long-term runtime and language decision
- Python MVP migration path

禁止扩展：

- 不加新的 Python runtime features
- 不做 marketplace UI
- 不做 billing
- 不做 non-API capability source runtimes
- 不做 hosted SaaS productization

退出标准：

- `docs/cn-ZH/API2AGENT_PROTOCOL_V0_2_PLAN.md` 完成
- `docs/cn-ZH/API2AGENT_PROTOCOL_V0_2.md` 完成
- `schemas/api2agent/v0.2/protocol.schema.json` 完成
- `docs/cn-ZH/ARCHITECTURE_DEFINITION_PHASE.md` 完成
- `docs/cn-ZH/PRODUCTION_ARCHITECTURE_RFC.md` 完成
- `docs/cn-ZH/PYTHON_REFERENCE_MIGRATION_PLAN.md` 完成
- `docs/cn-ZH/GO_DATA_PLANE_SKELETON_PLAN.md` 完成
- production architecture responsibilities 明确
- Data Plane technology direction 已选择
- Control Plane technology direction 已选择

当前实现 gate：

```text
Go Data Plane Skeleton hardening - complete
Go Data Plane protocol conformance + retry/failover dogfood - complete
Go Data Plane env credential resolution skeleton - complete
Go Data Plane durable event ingestion - complete
Go Data Plane real external provider retry dogfood - complete
Go Data Plane Consolidation Hardening v0 - complete
Timeout Budget Semantics v0 - complete
Snapshot Freshness Gate v0 - complete
Project Quota Gate v0 - complete
Go Data Plane Credential Config v0 - complete
Go Data Plane Credential Audit Metadata v0 - complete
Execution Event Ordering / Attempt Correlation v0 - complete
Go Data Plane Milestone Closeout + Phase 6 Readiness Review - complete
Go Control Plane Minimum v0 - complete
Control Plane Registry Validation v0 - complete
Control Plane Snapshot Compatibility Gate v0 - complete
Control Plane Registry Store v0 - complete
Control Plane Snapshot Versioning Policy v0 - complete
Control Plane Snapshot Export Artifact v0 - complete
Control Plane Snapshot Distribution Stub v0 - complete
Control Plane Snapshot Refresh / Reload Policy v0 - complete
Control Plane Snapshot Reload Failure Semantics v0 - complete
Control Plane Snapshot Reload Audit Events v0 - complete
Control Plane Snapshot Version Compatibility Guard v0 - complete
Control Plane Snapshot Strict Metadata Requirement v0 - complete
Control Plane Snapshot Metadata Manifest Consistency Guard v0 - complete
Control Plane Snapshot Artifact Content Digest Guard v0 - complete
Control Plane Snapshot Artifact Path Safety Guard v0 - complete
Control Plane Snapshot Distribution Atomic Publish Guard v0 - complete
Go Control Plane Snapshot Distribution Closeout + Phase Review - complete
Go Control Plane Service API Skeleton v0 - complete
Go Control Plane Service Snapshot Publish Endpoint v0 - complete
Go Control Plane Service API Closeout + Hosted Persistence Readiness Review - complete
Go Control Plane Persistent Registry Store Design v0 - complete
Control, Receipt, and Trust Layer Strategy - documented
Go Control Plane Persistent Registry Store Schema v0 - complete
Go Control Plane Persistence Phase Review - complete
Go Control Plane PostgresStore Load Parity v0 - complete
Go Control Plane Persistent Store Runtime Wiring v0 - complete
Go Control Plane Live Postgres Store Dogfood v0 - complete
Go Control Plane Persistent Export/Publish Audit Writes v0 - complete
Go Control Plane Persistent Store Failure Semantics Hardening v0 - complete
Go Control Plane Persistent Registry Mutation Boundary Review v0 - complete
API2Agent Tooling Re-entry Review + Tooling Expansion Plan v0 - complete
API2Agent Tooling Baseline Audit v0 - complete
API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0 - complete
Generated Package Region Metadata v0 - complete
Proxy-mode Credential Dogfood Expansion v0 - complete
Generated Package Latency Benchmark Helper v0 - complete
Endpoint-level Auth Inference v0 - complete
Base URL Override v0 - complete
Manual Write Test Path v0 - complete
Large Spec Performance v0 - complete
Better curl naming residual review v0 - complete
API2Agent Tooling Re-entry Closeout + Phase Review v0 - complete
API2Agent Stage Consolidation Before Import/Replace v0 - complete
Go Control Plane Persistent Registry Import/Replace Transaction Design v0 - complete
Go Control Plane Persistent Registry Import/Replace CLI Implementation v0 - complete
Go Control Plane Persistent Registry Import/Replace Live Postgres Dogfood v0 - complete
Go Control Plane Import/Replace Closeout + Mutation API Readiness Review v0 - complete
Go Control Plane Private Admin Import/Replace Endpoint Design v0 - complete
Go Control Plane Private Admin Import/Replace Endpoint Implementation v0 - complete
Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0 - complete
Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0 - complete
Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0 - complete
Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0 - complete
Go Control Plane Admin Mutation Idempotency Store Design v0 - complete
Go Control Plane Admin Mutation Idempotency Store Implementation v0 - complete
Go Control Plane Admin Mutation Idempotency Store Live Postgres Dogfood v0 - complete
Go Control Plane Admin Mutation Idempotency Store Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Identity Boundary Design v0 - complete
Go Control Plane Hosted Admin Identity Boundary Implementation v0 - complete
Go Control Plane Hosted Admin Identity Boundary Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Authenticator Integration Design v0 - complete
Go Control Plane Hosted Admin Authenticator Integration Implementation v0 - complete
Go Control Plane Hosted Admin Authenticator Integration Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Implementation v0 - complete
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0 - complete
Go Control Plane Hosted Admin Gateway Contract Harness Design v0 - complete
Go Control Plane Hosted Admin Gateway Contract Harness Implementation v0 - complete
Go Control Plane Hosted Admin Gateway Contract Harness Closeout + Phase Review v0 - complete
```

## 8.8 Phase 5.8：Tooling Re-entry Phase

状态：complete。

收口判断：

Tooling Re-entry 可以暂停。API-first hardening backlog 已关闭；除非先更新产品需求，项目可以回到此前暂停的 Control Plane write-side design。详见 `docs/cn-ZH/API2AGENT_TOOLING_REENTRY_CLOSEOUT_REVIEW.md`。

目标：

在 Control/Data Plane foundation work 之后回到 API2Agent Tooling Layer，但不退化成一次性 generator。

产品目标：

- 更多真实调用数据
- 更低 API/provider 接入成本
- 更快 Agent API 响应

范围：

- OpenAPI reliability
- curl reliability
- generated package observability defaults
- real API dogfood harness
- speed and region readiness

硬约束：

- API-first only
- 不做 workflow engine
- 不扩展 non-API runtime
- 不做 marketplace
- 不做 billing
- 不做 vault
- 保持 proxy、usage、credential、replay、shadow、golden trace 和 Protocol v0.2 compatibility

已完成 re-entry 结果：

- Tooling re-entry 已作为 planned return to the top of the funnel 被接受。
- Tooling Layer 已明确负责喂给 execution/data flywheel。
- Control Plane mutation API work 保持暂停。
- 详见 `docs/cn-ZH/API2AGENT_TOOLING_REENTRY_REVIEW_AND_EXPANSION_PLAN.md`。
- Tooling baseline audit 已完成：
  - 4/4 curl inputs generation 成功。
  - 4/4 curl inputs 第一次 direct execution 成功。
  - 3/3 no-auth proxy paths 第一次 proxy execution 成功。
  - GitHub REST OpenAPI 生成成功，但未过滤时产生 1186 个 tools。
  - 把 GitHub REST spec 过滤到 `/repos/{owner}/{repo}` 后产生 3 个 tools。
  - 详见 `docs/cn-ZH/API2AGENT_TOOLING_BASELINE_AUDIT_REPORT.md`。
- OpenAPI filtering + curl tool naming hardening 已完成：
  - root-path curl tools 现在包含 capability intent，例如从 `get` 变为 `get_ipify_public_ip`。
  - non-root curl naming 为 backward compatibility 继续保持 path-based。
  - OpenAPI generation 在 package 仍超过 50 个 tools 时输出 warning。
  - 通过现有 filters 进行 bounded generation 的行为保持不变。
  - 详见 `docs/cn-ZH/API2AGENT_OPENAPI_FILTERING_CURL_NAMING_HARDENING_REPORT.md`。
- Generated Package Region Metadata v0 已完成：
  - `api2agent generate --provider-region` 会把 `provider_region` 和 `provider_regions` 写入 generated `capability.json`。
  - generated README files 会记录 provider-region intent 和 runtime override。
  - generated runners 会在 proxy payloads 中包含 `provider_region`。
  - `API2AGENT_PROVIDER_REGION` 可以在 runtime 覆盖 generated metadata。
  - 详见 `docs/cn-ZH/API2AGENT_GENERATED_PACKAGE_REGION_METADATA_REPORT.md`。
- Proxy-mode Credential Dogfood Expansion v0 已完成：
  - authenticated generated packages 可以通过 local proxy mode 使用 local credential config 执行。
  - generated packages 只发送 credential intent，不携带 provider secrets。
  - proxy usage events 会记录 `credential_reference` 和脱敏 credential metadata，且不泄露 raw secret。
  - dogfood 保持 local，不引入 credential vault。
  - 详见 `docs/cn-ZH/API2AGENT_PROXY_CREDENTIAL_DOGFOOD_EXPANSION_REPORT.md`。
- Generated Package Latency Benchmark Helper v0 已完成：
  - `run_generated_package_latency_benchmark` 可以测量 generated package 的 direct/proxy loops。
  - `api2agent benchmark-package` 为 generated tools 输出 p50/p95 latency。
  - proxy benchmark runs 会保留 usage event ids 和 provider-region metadata。
  - 详见 `docs/cn-ZH/API2AGENT_GENERATED_PACKAGE_LATENCY_BENCHMARK_REPORT.md`。
- Endpoint-level Auth Inference v0 已完成：
  - OpenAPI document-level auth 继续作为 capability default。
  - operation-level `security: []` 现在会把 public tools 标记为 no-auth。
  - operation-level bearer/API key security 可以覆盖 capability default。
  - generated runners 和 proxy credential intent 现在是 tool-aware。
  - local credential resolution 可以为 mixed-auth providers 选择 endpoint-matching config credentials。
  - 详见 `docs/cn-ZH/API2AGENT_ENDPOINT_AUTH_INFERENCE_REPORT.md`。
- Base URL Override v0 已完成：
  - generated runners 支持 `API2AGENT_BASE_URL` 作为 package-wide runtime override。
  - generated runners 支持 `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>` 作为 tool-specific override。
  - invalid overrides 会在 provider forwarding 前 fail fast。
  - 拼接 base URL 和 tool path 时会保留 `/v1` 这类 base path prefixes。
  - direct 和 proxy execution 共用同一套 URL resolution semantics。
  - 详见 `docs/cn-ZH/API2AGENT_BASE_URL_OVERRIDE_REPORT.md`。
- Manual Write Test Path v0 已完成：
  - generated packages 包含 `manual_write_test.py`，用于显式 write/delete checks。
  - 默认 `api2agent test` 仍然保持 read-only，不会执行 write/delete tools。
  - `api2agent test --allow-write` 会在运行 manual test 前注入 `API2AGENT_ALLOW_WRITE_TEST=1`。
  - direct 和 proxy opt-in write tests 会保留 usage、credential、provider-region 和 estimated-cost metadata。
  - 详见 `docs/cn-ZH/API2AGENT_MANUAL_WRITE_TEST_PATH_REPORT.md`。
- Large Spec Performance v0 已完成：
  - OpenAPI filters 会在 parsing 阶段应用于 tag/path/operation/max-tools selection。
  - `api2agent inspect` 会输出 tool count、safety summary、top tags、top path prefixes 和 large-package hints。
  - `api2agent test --tool ... --params ...` 可以运行指定 generated read tool。
  - local 1200-operation dogfood 已验证 unfiltered warnings、bounded generation、inspect truncation 和 targeted tool testing。
  - 详见 `docs/cn-ZH/API2AGENT_LARGE_SPEC_PERFORMANCE_REPORT.md`。
- Better curl naming residual review v0 已完成：
  - `api` 和 `www` 这类 generic leading curl host labels 不再生成过泛的默认 capability names。
  - `api.github.com` 现在会生成 `github_api` 和 `GITHUB_API_TOKEN`。
  - 显式 `--name` 仍然优先。
  - non-root path tools 为 backward compatibility 继续保持 path-based。
  - 详见 `docs/cn-ZH/API2AGENT_CURL_NAMING_RESIDUAL_REVIEW.md`。
- API2Agent Tooling Re-entry Closeout + Phase Review v0 已完成：
  - Tooling Re-entry acceptance criteria 已复盘并通过。
  - remaining risks 已文档化。
  - API-first 和 no-workflow-engine 约束保持明确。
  - 下一项任务回到 Control Plane import/replace transaction design。
  - 详见 `docs/cn-ZH/API2AGENT_TOOLING_REENTRY_CLOSEOUT_REVIEW.md`。
- API2Agent Stage Consolidation Before Import/Replace v0 已完成：
  - Tooling、Go Data Plane 和 Go Control Plane persistent read/audit primitives 已完成阶段汇总。
  - import/replace entry gates 已在 design 前记录。
  - FileStore default、Postgres opt-in、snapshot handoff、registry rows 只存 credential metadata、以及不做 workflow/marketplace/billing/vault 的不变量已重新确认。
  - 详见 `docs/cn-ZH/API2AGENT_STAGE_CONSOLIDATION_BEFORE_IMPORT_REPLACE.md`。

已完成 private admin endpoint design 结果：

- `POST /v1/admin/registry/import-replace` 是被接受的 private admin endpoint。
- request body 使用 wrapper object，包含 `registry`、可选 `source` 和 reserved `dry_run=false`。
- HTTP mutation requests 必须提供 `X-Request-ID` 和 `Idempotency-Key`。
- endpoint 只允许 Postgres mutation；file-store mode 返回 `REGISTRY_MUTATION_UNAVAILABLE`。
- response shape、request-size limit、error mapping、audit mapping 和 required implementation tests 已文档化。
- snapshot export、publish 和 Data Plane reload 继续分离。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`。

已完成 import/replace snapshot propagation 结果：

- E2E dogfood 本地启动了 Control Plane 和 Data Plane。
- HTTP import/replace 将 persistent registry provider 从 `ipify_public_ip_v1` 替换为 `httpbin_public_ip_v1`。
- Control Plane export 并 publish 替换后的 snapshot。
- Data Plane 手动 reload 了 published distribution。
- Data Plane execution 返回 replacement-provider output `{ "ip": "203.0.113.88" }`。
- Data Plane usage/decision records 归因到 `httpbin` / `httpbin_public_ip_v1` 和 `snapshot_propagation_httpbin_v2`。
- Persistent audit counts 已断言：`registry_revisions=4`、`snapshot_artifact_publications=2`、`admin_audit_events=5`、`providers=1`。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`。

已完成 propagation closeout 结果：

- import/replace snapshot propagation milestone 可以关闭。
- write-side path 已经从 private admin HTTP mutation 到 Data Plane execution with replaced provider 端到端证明。
- Data Plane 继续消费 immutable/versioned snapshots，而不是 mutable Control Plane tables。
- remaining risks 是 idempotency persistence、hosted admin identity、manual propagation、blunt full replacement、local filesystem distribution 和 conservative registry size limit。
- 下一项任务是 persistent admin mutation idempotency records 的 design task。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`。

下一项工程任务：

```text
Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation v0
```

## 9. Phase 6：Hosted Control Plane

状态：hosted permission policy mutation boundary contract harness closeout 已完成。Local Go Control Plane minimum、snapshot distribution、private import/replace、idempotency、hosted admin trusted gateway、local gateway contract harness、gateway permission-source proof、tenant partition validation、private project mutation endpoint、live dogfood closeout、durable permission-store boundary design、hosted permission-store contract harness and closeout、hosted permission-store schema、schema closeout、read model implementation、read model closeout、read model live Postgres dogfood、dogfood closeout、gateway runtime wiring design、gateway runtime wiring implementation、gateway runtime wiring closeout、decision persistence design、decision persistence implementation、decision persistence closeout、decision persistence integrity hardening design、decision persistence integrity hardening implementation、decision persistence integrity hardening closeout、decision persistence production boundary design、decision persistence production boundary implementation、decision persistence production boundary closeout、完整 decision persistence stage closeout、decision retention/customer-history boundary design、decision retention boundary implementation、decision retention boundary closeout、policy mutation boundary design、policy mutation contract harness implementation 和 policy mutation contract harness closeout 已完成。

目标：

把 local proxy concepts 迁移到 hosted service。

立即本地范围：

- local Go Control Plane model layer
- 生成可被 Go Data Plane 消费的 routing snapshot export
- local snapshot artifact and distribution lifecycle
- local Control Plane service API boundary
- project identity and admin authorization

已完成的 local entry slices：

```text
Go Control Plane Minimum v0
Go Control Plane Snapshot Distribution Closeout + Phase Review
Go Control Plane Service API Skeleton v0
Go Control Plane Service Snapshot Publish Endpoint v0
Go Control Plane Service API Closeout + Hosted Persistence Readiness Review
Go Control Plane Persistent Registry Store Design v0
Go Control Plane Persistent Registry Store Schema v0
Go Control Plane Persistence Phase Review
Go Control Plane PostgresStore Load Parity v0
Go Control Plane Persistent Store Runtime Wiring v0
Go Control Plane Live Postgres Store Dogfood v0
Go Control Plane Persistent Export/Publish Audit Writes v0
Go Control Plane Persistent Store Failure Semantics Hardening v0
Go Control Plane Persistent Registry Mutation Boundary Review v0
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
Go Control Plane Persistent Registry Import/Replace CLI Implementation v0
Go Control Plane Persistent Registry Import/Replace Live Postgres Dogfood v0
Go Control Plane Import/Replace Closeout + Mutation API Readiness Review v0
Go Control Plane Private Admin Import/Replace Endpoint Design v0
Go Control Plane Private Admin Import/Replace Endpoint Implementation v0
Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0
Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0
Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0
Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0
Go Control Plane Admin Mutation Idempotency Store Design v0
Go Control Plane Admin Mutation Idempotency Store Implementation v0
Go Control Plane Admin Mutation Idempotency Store Live Postgres Dogfood v0
Go Control Plane Admin Mutation Idempotency Store Closeout + Phase Review v0
Go Control Plane Hosted Admin Identity Boundary Design v0
Go Control Plane Hosted Admin Identity Boundary Implementation v0
Go Control Plane Hosted Admin Identity Boundary Closeout + Phase Review v0
Go Control Plane Hosted Admin Authenticator Integration Design v0
Go Control Plane Hosted Admin Authenticator Integration Implementation v0
Go Control Plane Hosted Admin Authenticator Integration Closeout + Phase Review v0
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood v0
Go Control Plane Hosted Admin Trusted Gateway Service Dogfood Closeout + Phase Review v0
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Design v0
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Implementation v0
Go Control Plane Hosted Admin Trusted Gateway Production Boundary Closeout + Phase Review v0
Go Control Plane Hosted Admin Gateway Contract Harness Design v0
Go Control Plane Hosted Admin Gateway Contract Harness Implementation v0
Go Control Plane Hosted Admin Gateway Contract Harness Closeout + Phase Review v0
Go Control Plane Hosted Admin Gateway Permission Source Design v0
Go Control Plane Hosted Admin Gateway Permission Source Implementation v0
Go Control Plane Hosted Admin Gateway Permission Source Closeout + Phase Review v0
Go Control Plane Tenant-Partitioned Registry Mutation Design v0
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness v0
Go Control Plane Tenant-Partitioned Registry Mutation Contract Harness Closeout + Phase Review v0
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Design v0
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Implementation v0
Go Control Plane Tenant-Partitioned Registry Mutation Private Endpoint Live Dogfood + Closeout v0
Go Control Plane Hosted Permission Store Design v0
Go Control Plane Hosted Permission Store Contract Harness v0
Go Control Plane Hosted Permission Store Contract Harness Closeout + Phase Review v0
Go Control Plane Hosted Permission Store Schema v0
Go Control Plane Hosted Permission Store Schema Closeout + Phase Review v0
Go Control Plane Hosted Permission Store Read Model v0
Go Control Plane Hosted Permission Store Read Model Closeout + Phase Review v0
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood v0
Go Control Plane Hosted Permission Store Read Model Live Postgres Dogfood Closeout + Phase Review v0
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Design v0
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Implementation v0
Go Control Plane Hosted Permission Read Model Gateway Runtime Wiring Closeout + Phase Review v0
Go Control Plane Hosted Permission Decision Persistence Design v0
Go Control Plane Hosted Permission Decision Persistence Implementation v0
Go Control Plane Hosted Permission Decision Persistence Closeout + Phase Review v0
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Design v0
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Implementation v0
Go Control Plane Hosted Permission Decision Persistence Integrity Hardening Closeout + Phase Review v0
Go Control Plane Hosted Permission Decision Persistence Production Boundary Design v0
Go Control Plane Hosted Permission Decision Persistence Production Boundary Implementation v0
Go Control Plane Hosted Permission Decision Persistence Production Boundary Live Dogfood + Closeout v0
Go Control Plane Hosted Permission Decision Persistence Stage Closeout + Readiness Review v0
Go Control Plane Hosted Permission Decision Retention + Customer History Boundary Design v0
Go Control Plane Hosted Permission Decision Retention Boundary Implementation v0
Go Control Plane Hosted Permission Decision Retention Boundary Live Dogfood + Closeout v0
Go Control Plane Hosted Permission Policy Mutation Boundary Design v0
Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness v0
Go Control Plane Hosted Permission Policy Mutation Boundary Contract Harness Closeout + Phase Review v0
```

下一项 hosted-readiness slice：

```text
Go Control Plane Hosted Permission Policy Mutation Durable Private Implementation v0
```

local/private mutation contract proof 和 durable/private implementation design 已作为 v0 接受。下一项任务应实现 private Postgres-backed mutation path，再考虑 public policy write API、production gateway rollout 或 customer-facing history/export surface。

范围：

1. 增加 durable private draft/change row support 和 registry package mutation functions。
2. 实现 validation、promotion 和 rollback transaction boundaries。
3. 保留 idempotency replay/conflict、stale-base conflict、duplicate grant conflict、scope violation 和 secret-safe audit semantics。
4. 保持 service private，不开放 public policy write APIs。
5. 增加 implementation tests 和 machine-readable dogfood evidence criteria。
6. 不实现 automatic publish/reload、vault、billing、marketplace、workflow、provider onboarding、OAuth/OIDC、public CRUD、policy write APIs、Data Plane mutable reads、customer-facing decision history/export/delete/legal-hold APIs 或 production gateway deployment。

退出标准：

- durable private implementation 已有 tests 覆盖。
- transaction 和 conflict semantics 已在 durable storage 上 enforced。
- private response/audit evidence 保持 secret-safe。
- live Postgres dogfood criteria 已满足，或明确 deferred 到下一条 phase-log entry。
- OAuth/OIDC、public CRUD、production deployment、vault、billing、marketplace、workflow、provider onboarding、policy write APIs、Data Plane mutable reads 和 automatic propagation 保持 deferred。

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_LIVE_POSTGRES_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_ADMIN_MUTATION_IDEMPOTENCY_STORE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_IDENTITY_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_POLICY_MUTATION_BOUNDARY_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_POLICY_MUTATION_BOUNDARY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_POLICY_MUTATION_BOUNDARY_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`
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
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_READ_MODEL_GATEWAY_RUNTIME_WIRING_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_READ_MODEL_GATEWAY_RUNTIME_WIRING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_INTEGRITY_HARDENING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_PRODUCTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_PERSISTENCE_STAGE_CLOSEOUT_READINESS_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_RETENTION_CUSTOMER_HISTORY_BOUNDARY_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_RETENTION_BOUNDARY_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_PERMISSION_DECISION_RETENTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/API2AGENT_HOSTED_CONTROL_PLANE_PAUSE_AND_AGENT_COMPILER_REENTRY.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_WORLD_HARDENING_DESIGN.md`
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
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_DESIGN.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_FINAL_REENTRY_CLOSEOUT_CONSOLIDATION_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_DESIGN.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`

已完成 tenant-partitioned registry mutation contract harness closeout 结果：

- local partition validation helper 被接受为足以支撑 v0。
- same-project、cross-project、global/platform、provider ownership、invalid registry 和 project-scoped idempotency cases 满足 design acceptance criteria。
- 未新增 HTTP endpoint、public CRUD、production gateway deployment、automatic propagation 或 Data Plane mutable-table reads。
- remaining risks 是 endpoint wiring、audit persistence、first-class provider ownership、project row policy、durable permissions 和 manual propagation。
- 下一项任务是 private hosted project mutation endpoint design。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`。

已完成 tenant-partitioned registry mutation contract harness 结果：

- local partition validation helper `ValidateProjectPartitionMutation` 已实现。
- same-project project/API key/credential metadata changes 通过。
- cross-project、global routing、snapshot config、capability、provider ownership 和 platform-owned provider changes 使用 stable partition errors 失败。
- 只有 ownership metadata 匹配 principal project 时，才允许 project-owned provider metadata changes。
- project-scoped idempotency fingerprint evidence 已由 tests 覆盖。
- 未新增 HTTP endpoint、public CRUD、production gateway deployment、automatic propagation 或 Data Plane mutable-table reads。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`。

已完成 tenant-partitioned registry mutation design 结果：

- project partition ownership rules 已明确。
- global/platform read-only objects 继续受保护，不允许 project-scoped mutation 修改。
- provider ownership 被识别为 project-owned provider mutation 前的 schema/metadata gap。
- partition diff validation 被设计为 full-registry replacement 前的 pre-commit gate。
- idempotency、audit evidence、snapshot boundaries 和 failure semantics 已定义。
- 下一项任务是 partition rules 的 local contract harness，不是 public CRUD。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_TENANT_PARTITIONED_REGISTRY_MUTATION_DESIGN.md`。

已完成 hosted admin gateway permission source closeout 结果：

- permission-source implementation slice 可以关闭。
- static dogfood policy 被接受为 v0 trust-boundary proof，不是 production auth。
- gateway-local denial 不创建 Control Plane audit/idempotency rows。
- Control Plane trusted-gateway authenticator 继续作为第二道 gate，并拒绝 insufficient trusted permissions。
- 下一条最高风险 hosted lane 是 tenant-partitioned registry mutation design。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_CLOSEOUT_PHASE_REVIEW.md`。

已完成 hosted admin gateway permission source implementation 结果：

- gateway-side permission decisions 已在 local contract harness 中实现。
- static policy 会把 public principals 解析为 trusted project-scoped roles 和 permissions。
- missing/invalid public auth、permission source unavailable、route/method mismatch 和 public authz denial 都会在 gateway 本地 fail before forwarding。
- Control Plane trusted-gateway authenticator 继续作为第二道 gate，并会用 `AUTHZ_DENIED` 拒绝 forced insufficient trusted permissions。
- live dogfood 已通过，audit/idempotency evidence 使用 trusted claims，且未泄漏 raw public token 或 gateway secret。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_IMPLEMENTATION_REPORT.md`。

已完成 hosted admin gateway permission source design 结果：

- gateway-side permission source contract 已定义。
- static dogfood policy 会将 public principals 映射为 trusted roles and permissions。
- endpoint permission mapping 和 fail-closed semantics 已指定。
- audit/idempotency evidence 和 local harness dogfood expectations 已定义。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_PERMISSION_SOURCE_DESIGN.md`。

已完成 Agent capability compiler final re-entry closeout 结果：

- compiler re-entry scope 被接受为 100% complete。
- future compiler work 移入 evidence-triggered backlog。
- 下一条 project lane 回到 hosted Control Plane permission-source design。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_FINAL_REENTRY_CLOSEOUT_CONSOLIDATION_REVIEW.md`。

已完成 Agent capability compiler OpenAPI cached real-spec corpus expansion closeout 结果：

- 一个 required cached public-spec case 对 v0 被接受为 sufficient。
- 更多 cached specs 暂缓到 final compiler consolidation 之后。
- Agent Capability Compiler 完成度估计为 99%。
- 下一项任务是 final compiler re-entry consolidation。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler OpenAPI cached real-spec corpus expansion implementation 结果：

- default calibration manifest 已包含 committed Apache-2.0 Petstore excerpt。
- cached source metadata、checksum validation、path containment 和 additive result fields 已实现。
- local calibration 现在报告 5 pass、2 warn、0 fail 和 1 skipped。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler OpenAPI cached real-spec corpus expansion design 结果：

- source criteria、licensing/cache metadata、redaction policy、artifact layout、manifest changes、metrics、thresholds、tests 和 dogfood expectations 已定义。
- normal calibration 保持 offline and deterministic。
- 下一项 compiler hardening task 是 cached real-spec corpus expansion implementation。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_DESIGN.md`。

已完成 Agent capability compiler OpenAPI generic example reduction closeout 结果：

- deterministic name-aware fallbacks 被接受为 complete。
- default generated calibration cases 现在报告 zero generic examples 和 empty generic first-call params。
- Agent Capability Compiler 完成度估计为 98%。
- 下一项 confidence gap 是 cached real-spec corpus expansion design。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler OpenAPI generic example reduction implementation 结果：

- name-aware parameter/property examples、secret-safe placeholders、numeric/name fallbacks、calibration generic example metrics、regression coverage 和 dogfood reducing default calibration generic first-call params to zero 已实现。
- full Python suite 已通过 217 tests。
- 后续 closeout 现在已完成。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler OpenAPI generic example reduction design 结果：

- deterministic name-aware fallback rules、priority preservation for source/schema hints、object field context threading、calibration generic example metrics、tests、dogfood 和 non-goals 已定义。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_DESIGN.md`。

已完成 Agent capability compiler OpenAPI summary noise reduction closeout 结果：

- v0 summary budgets 对当前 corpus 被接受为 sufficient。
- remaining risks 是 opinionated text-output budgets、large README tool sections、advisory repeated diagnostic groups、generic first-call params 和 fixture-heavy corpus coverage。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler OpenAPI summary noise reduction implementation 结果：

- compact inspect aggregate rendering、representative response previews、line clipping、grouped diagnostics text、README package overview/key caveats、calibration summary-density metrics、regression coverage 和 dogfood 已实现。
- full Python suite 已通过 213 tests。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler OpenAPI summary noise reduction design 结果：

- noise taxonomy、bounded summary budgets、risk-first rendering order、repeated finding folding、README/inspect/diagnostics text effects、calibration summary-density metrics、tests、dogfood 和 non-goals 已定义。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_DESIGN.md`。

已完成 Agent capability compiler diagnostics score calibration closeout 结果：

- calibrated score profile 被接受为 complete。
- remaining risks 是更广 real specs 上的 action-cap calibration、heuristic score semantics、summary noise、generic examples 和 fixture-heavy corpus coverage。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler diagnostics score calibration implementation 结果：

- diagnostics scoring 现在使用 explicit impact profile、score breakdown、metadata cap、repeated action-finding cap 和 readiness zero-penalty handling。
- real-spec calibration 从 1 pass / 5 warn 改善为 4 pass / 2 warn，同时 write-heavy 和 large-surface cases 仍保持 visible warnings。
- full Python suite 已通过 212 tests。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler diagnostics score calibration design 结果：

- scoring weakness、compatibility strategy、impact classes、initial mapping、score formula、metadata cap、score breakdown、calibration expectations、tests、dogfood 和 non-goals 已定义。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_DESIGN.md`。

已完成 Agent capability compiler OpenAPI real-spec calibration harness closeout 结果：

- local calibration harness 被接受为 complete。
- 第一个 evidence-driven next gap 是 metadata-rich packages 的 diagnostics score calibration。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler OpenAPI real-spec calibration harness implementation 结果：

- local offline calibration script、purpose-labeled corpus cases、machine-readable result artifact、status classification、fixture/synthetic-large coverage 和 dogfood 已实现。
- full Python suite 已通过 210 tests。
- 下一项 compiler hardening task 是 real-spec calibration harness closeout。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler OpenAPI real-spec calibration design 结果：

- calibration-after-keyword-coverage rationale、corpus slots、metric contract、status thresholds、harness behavior、artifact strategy、tests、dogfood 和 non-goals 已定义。
- 下一项 compiler hardening task 是 local real-spec calibration harness implementation。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_DESIGN.md`。

已完成 Agent capability compiler OpenAPI JSON Schema keyword coverage closeout 结果：

- bounded keyword coverage 被接受为 complete。
- remaining risks 是 bounded keyword semantics、heuristic examples、summary density、advisory diagnostics 和 OpenAPI 3.1 dialect nuance。
- 下一项 compiler hardening task 是 OpenAPI real-spec calibration design。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler OpenAPI JSON Schema keyword coverage implementation 结果：

- compact keyword summaries、deterministic keyword-hint examples、inspect schema hint counts、diagnostics、fixture coverage 和 local dogfood 已实现。
- raw schema compatibility 保持 intact，Tier 2 advanced keywords 会被诊断，而不是被当作 validator semantics 处理。
- full Python suite 已通过 205 tests。
- 下一项 OpenAPI hardening task 是 JSON Schema keyword coverage closeout。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler OpenAPI JSON Schema keyword coverage design 结果：

- current keyword coverage baseline and gaps 已文档化。
- Tier 1 display/example keywords、Tier 2 diagnostics-only keywords、compatibility strategy、generated artifact effects、tests、dogfood 和 non-goals 已定义。
- 下一项 OpenAPI hardening task 是 JSON Schema keyword coverage implementation。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_DESIGN.md`。

已完成 Agent capability compiler OpenAPI response shape documentation closeout 结果：

- response shape documentation 已接受为 complete。
- remaining risks 是 documentation-only content negotiation、unvalidated source examples、advisory diagnostics、no runtime output validation 和 partial JSON Schema keyword coverage。
- 下一项 OpenAPI hardening task 是 JSON Schema keyword coverage design。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler OpenAPI response shape documentation implementation 结果：

- additive response metadata、deterministic content selection、README/inspect response summaries、diagnostics、fixture coverage 和 local dogfood 已实现。
- generated runner behavior 保持 unchanged，old capability JSON without response metadata 仍然 valid。
- local response-shape dogfood 已通过，full Python suite 以 201 tests 通过。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler OpenAPI response shape documentation design 结果：

- current response documentation baseline and gaps 已文档化。
- additive response metadata、extraction rules、status categories、README/inspect summaries、diagnostics、tests、dogfood 和 non-goals 已定义。
- 下一项 OpenAPI hardening task 是 response shape documentation implementation。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_DESIGN.md`。

已完成 Agent capability compiler OpenAPI discriminator handling implementation 结果：

- discriminator-aware schema summaries、mapping-driven examples、schema hints、diagnostics 和 tool schema preservation 已实现。
- discriminator fixture 和 parser/generator/diagnostics/CLI regression tests 已增加。
- local discriminator dogfood 已通过，full Python suite 以 197 tests 通过。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler OpenAPI discriminator handling closeout 结果：

- discriminator handling 已接受为 complete。
- remaining risks 是 pragmatic branch matching、bounded mapping resolution、sparse response documentation、advisory diagnostics 和 no runtime branch validation。
- 下一项 OpenAPI hardening task 是 response shape documentation design。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler OpenAPI discriminator handling design 结果：

- current discriminator baseline 和 gaps 已文档化。
- compatibility strategy、extraction rules、summary formatting、deterministic example rules、generated artifact effects、diagnostics、tests、dogfood 和 non-goals 已定义。
- 下一项 OpenAPI hardening task 是 discriminator handling implementation。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_DESIGN.md`。

已完成 Agent capability compiler OpenAPI schema shaping closeout 结果：

- schema shaping 已接受为 complete。
- generated Agent-facing inputs 对 nullable、map、array、polymorphic 和 optional object shapes 更清楚。
- remaining risks 是 discriminator metadata not yet used、response shaping depth、intentional partial JSON Schema coverage、advisory diagnostics 和 bounded rather than semantic simplification。
- 下一项 OpenAPI hardening task 是 discriminator handling design。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler OpenAPI schema shaping implementation 结果：

- direction-aware schema helpers 已实现，未增加 required IR changes。
- generated README、inspect、OpenAI tools schema、examples 和 diagnostics 现在使用 shaped schema summaries 和 request-body filtering。
- nullable、readOnly/writeOnly、additionalProperties、array、polymorphism 和 required/optional cases 已由 fixtures 和 regression tests 覆盖。
- local schema-shaping dogfood 已通过，full Python suite 以 193 tests 通过。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler OpenAPI schema shaping design 结果：

- current schema handling baseline 和 gaps 已文档化。
- direction-aware request/response shaping rules 已定义。
- nullable、readOnly/writeOnly、additionalProperties、array、polymorphism 和 required/optional field policies 已定义。
- generated README、tools schema、examples、inspect、diagnostics、tests 和 dogfood expectations 已定义。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_DESIGN.md`。

已完成 Agent capability compiler OpenAPI real-world hardening design 结果：

- examples/defaults propagation 被选为第一项 OpenAPI hardening implementation slice。
- current parser baseline 和 gaps 已文档化。
- additive IR fields 和 deterministic example selection order 已指定。
- generated README/test params、diagnostics evidence、tests 和 dogfood expectations 已定义。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_WORLD_HARDENING_DESIGN.md`。

已完成 Agent capability compiler quality diagnostics closeout 结果：

- quality diagnostics 已接受为 complete。
- deterministic diagnostics 现在为 generated package quality 提供 feedback layer。
- remaining risks 是 real-spec calibration、advisory-only diagnostics、shallow schema quality 和 broader OpenAPI complexity。
- 下一项 compiler expansion task 是 OpenAPI real-world hardening design。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_CLOSEOUT_PHASE_REVIEW.md`。

已完成 Agent capability compiler quality diagnostics implementation 结果：

- generated packages 现在写入 additive `diagnostics.json`。
- `api2agent diagnose` 可以从旧 packages 重新计算 diagnostics。
- generation、README 和 inspect surfaces 暴露 compact diagnostics summaries。
- deterministic findings 覆盖 usability、safety、auth、schema、execution 和 observability risks。
- tests 和 local dogfood 已通过。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`。

已完成 Agent capability compiler expansion design 结果：

- quality diagnostics 被选为第一项 compiler expansion implementation slice。
- design 覆盖 generate、diagnose 和 inspect workflows。
- `diagnostics.json`、finding ids、severity/status semantics、scoring、tests 和 dogfood 已定义。
- implementation 保持 API-first，不引入 workflow、marketplace、vault、billing、hosted public CRUD 或 production gateway work。
- 详见 `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`。

已完成 hosted Control Plane pause + Agent compiler re-entry 结果：

- deeper hosted Control Plane work 在可信边界处暂停。
- hosted permission-source design 移入 hosted-readiness backlog。
- immediate next project task 回到 API-first Agent capability compiler expansion。
- 推荐扩展 tracks 是 capability quality diagnostics、OpenAPI real-world hardening、curl instant onboarding 和 observable execution defaults。
- 详见 `docs/cn-ZH/API2AGENT_HOSTED_CONTROL_PLANE_PAUSE_AND_AGENT_COMPILER_REENTRY.md`。

已完成 hosted admin gateway contract harness closeout 结果：

- local gateway contract proof 已接受为 complete。
- public header stripping 和 trusted claim injection 已通过真实 gateway hop dogfood。
- audit/idempotency evidence 使用 harness-injected identity，并保持 secret/token-safe。
- remaining risks 是 static public auth、static permission policy、production gateway deployment、tenant-partitioned mutation 和 manual propagation。
- 下一项 hosted-readiness task 是 permission-source design，但 immediate project focus 已切回 compiler。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_CLOSEOUT_PHASE_REVIEW.md`。

已完成 hosted admin gateway contract harness implementation 结果：

- local dogfood-only gateway harness 已实现。
- public bearer auth 会在本地消费，trusted `X-API2Agent-*` headers 会被 strip 并重新注入。
- dogfood requests 通过 harness 到达 private Control Plane admin endpoints。
- audit/idempotency evidence 使用 harness-injected identity 和 gateway key id。
- raw public bearer tokens 和 raw gateway secret 未出现在 evidence/report artifacts 中。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_IMPLEMENTATION_REPORT.md`。

已完成 hosted admin gateway contract harness design 结果：

- local gateway harness responsibilities 明确。
- static public auth and identity policy 明确。
- public header stripping matrix 明确。
- trusted claim injection 和 request/idempotency propagation 明确。
- negative spoofing 和 dogfood evidence requirements 已命名。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_GATEWAY_CONTRACT_HARNESS_DESIGN.md`。

已完成 hosted trusted-gateway production boundary closeout 结果：

- Control Plane 侧 production boundary mechanics 可以关闭。
- active secret rotation 和 gateway key-id evidence 已实现并完成 dogfood。
- remaining gateway contract、public auth、permission-source、deployment 和 tenant-partitioning risks 已文档化。
- 下一项最高信号任务是 gateway contract harness design。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_CLOSEOUT_PHASE_REVIEW.md`。

已完成 hosted trusted-gateway production boundary implementation 结果：

- rotation-compatible active gateway secrets 已实现。
- legacy single-secret configuration 保持兼容。
- optional gateway key-id evidence 会进入 audit 和 import/replace metadata。
- live dogfood 验证 old/new overlap、removed old-secret rejection、new-secret mutation、key-id evidence 和 secret-safe metadata。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_IMPLEMENTATION_REPORT.md`。

已完成 hosted trusted-gateway production boundary design 结果：

- gateway-to-Control-Plane trust boundary 明确。
- trusted header strip/rewrite rules 明确。
- gateway secret rotation approach 明确。
- permission issuance assumptions 明确。
- audit/idempotency evidence contract 明确。
- deployment and observability expectations 明确。
- implementation tests 和 dogfood requirements 已命名。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_PRODUCTION_BOUNDARY_DESIGN.md`。

已完成 hosted trusted-gateway service dogfood closeout 结果：

- Control Plane 侧 hosted trusted-gateway admin path 可以暂停。
- service dogfood acceptance criteria 已通过真实 HTTP 和 live Postgres 验证。
- import/replace audit metadata 现在包含 hosted principal evidence。
- remaining production gateway、secret rotation、permission-source、header-stripping 和 tenant-partitioning risks 已文档化。
- 下一项最高信号任务是 production gateway boundary design。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_CLOSEOUT_PHASE_REVIEW.md`。

已完成 hosted trusted-gateway service dogfood 结果：

- Control Plane service 在 hosted/trusted-gateway mode 下不传 `--admin-token` 即可启动。
- trusted gateway headers 下真实 HTTP validation 返回 `200`。
- missing gateway authorization 返回 `401 AUTH_ERROR`。
- missing endpoint permission 返回 `403 AUTHZ_DENIED`。
- Postgres audit rows 保留 trusted actor、subject、project、organization、auth method、token id 和 `local_private=false`。
- Postgres idempotency rows 使用 trusted gateway project 和 actor scope。
- import/replace audit metadata 已修复为包含 hosted principal evidence。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_HOSTED_ADMIN_TRUSTED_GATEWAY_SERVICE_DOGFOOD_REPORT.md`。

已完成 propagation closeout 结果：

- import/replace snapshot propagation milestone 可以关闭。
- private admin HTTP mutation 到 Data Plane execution with replaced provider 已证明。
- Data Plane 继续消费 immutable/versioned snapshots，而不是 mutable Control Plane tables。
- 下一项最高信号缺口是 admin mutations 的 durable idempotency semantics。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_CLOSEOUT_PHASE_REVIEW.md`。

已完成 propagation dogfood 结果：

- dogfood script 启动了 podman-backed Postgres、Control Plane service、Data Plane service 和本地 httpbin-like replacement provider。
- Data Plane 初始加载 `snapshot_propagation_ipify_v1`。
- HTTP import/replace 将 persistent registry provider 替换为 `httpbin_public_ip_v1`。
- Control Plane export 并 publish `snapshot_propagation_httpbin_v2`。
- Data Plane manual reload 从 `snapshot_propagation_ipify_v1` 切换到 `snapshot_propagation_httpbin_v2`。
- Data Plane execution 返回 `{ "ip": "203.0.113.88" }`。
- usage 和 decision records 已归因到 replacement provider。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_SNAPSHOT_PROPAGATION_E2E_DOGFOOD_REPORT.md`。

已完成 endpoint closeout 结果：

- private admin endpoint design、implementation 和 live dogfood 已完成。
- write-side milestone 可以关闭。
- remaining risks 包括 hosted auth maturity、缺少 idempotency cache、full-registry replacement 较钝、snapshot propagation 仍然手动、request-size limit 偏保守。
- 下一项最高信号证明是 import/replace snapshot propagation 到 Data Plane execution。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_CLOSEOUT_PHASE_REVIEW.md`。

已完成 live endpoint dogfood 结果：

- Live Postgres dogfood 使用 podman。
- service 使用 Postgres store wiring 接受了 `POST /v1/admin/registry/import-replace`。
- changed registry 返回 `201` 和 `noop=false`。
- repeated same-registry import 返回 `200` 和 `noop=true`。
- service validation 和 artifact export 都看到了替换后的 registry。
- Exported snapshot provider 是 `httpbin_public_ip_v1`。
- Persistent audit counts 为 `registry_revisions=3`、`admin_audit_events=4`、`providers=1`。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_LIVE_POSTGRES_DOGFOOD_REPORT.md`。

已完成 private admin endpoint implementation 结果：

- `POST /v1/admin/registry/import-replace` 已注册。
- handler 要求 admin auth、`X-Request-ID` 和 `Idempotency-Key`。
- handler 接收已设计的 wrapper request body，并拒绝 `dry_run=true`。
- Postgres runtime wiring 注入很窄的 `RegistryImportReplacer`。
- FileStore/unconfigured mutation 返回 `409 REGISTRY_MUTATION_UNAVAILABLE`。
- changed registry 返回 `201`；same-fingerprint no-op 返回 `200`。
- mutation errors 映射到稳定 service error envelope。
- `go test ./...` 在 `services/control-plane` 通过。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_IMPLEMENTATION_REPORT.md`。

已完成 private admin endpoint design 结果：

- 被接受的 endpoint 是 `POST /v1/admin/registry/import-replace`。
- 设计要求 wrapper request body、`Authorization`、`X-Request-ID` 和 `Idempotency-Key`。
- v0 会用稳定 error records 拒绝 `dry_run=true`、过大的 request body、invalid registry，以及 unconfigured/file-store mutation mode。
- success/failure audit evidence 继续由 registry import/replace primitive 负责；endpoint 只传递 identity metadata。
- Snapshot export/publish/reload 继续作为独立流程。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`。

已完成的 import/replace closeout 和 mutation API readiness 结果：

- Local/admin CLI primitive 满足当前 write-side import/replace goal。
- 该 slice 可以关闭。
- 项目可以进入 private admin import/replace endpoint design。
- 项目不能跳过 design 直接实现 endpoint。
- Public CRUD、provider onboarding、vault、billing、settlement 和 automatic snapshot reload 继续 out of scope。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_IMPORT_REPLACE_CLOSEOUT_MUTATION_API_READINESS_REVIEW.md`。

已完成的 live Postgres import/replace dogfood 结果：

- Podman provisioned 了 live Postgres-compatible database。
- Schema apply、seed、changed-registry import/replace、same-registry no-op 和 snapshot export 均通过。
- 第一次 import 返回 `noop=false`；第二次 import 返回 `noop=true`。
- Exported snapshot 反映了 `snapshot_import_replace_live_v1` 和 provider `httpbin_public_ip_v1`。
- Persistent audit counts 为 `registry_revisions=2`、`admin_audit_events=2`、`providers=1`。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_LIVE_POSTGRES_DOGFOOD_REPORT.md`。

已完成的 import/replace CLI implementation 结果：

- `api2agent-controlplane import-replace-postgres` 已作为 local/admin command 实现。
- `ReplacePersistentRegistry` 使用 serializable transaction options 和 transaction-scoped advisory lock。
- same-fingerprint import 返回 no-op，并且只写 success audit。
- changed registry replacement 会在同一 transaction 中写入 `registry_revisions` 和 success `admin_audit_events`。
- required success audit failure 会 rollback mutation。
- 没有引入 public write API。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_CLI_IMPLEMENTATION_REPORT.md`。

已完成的 import/replace transaction design 结果：

- 第一个 write-side operation 被限制为 controlled full-registry import/replace。
- `seed-postgres` 仍然是 dogfood helper，不是 production mutation path。
- 已接受的 transaction 使用 serializable isolation 加 `pg_try_advisory_xact_lock(22021, 1)`。
- Mutable registry tables 作为一个 validated graph 被替换；append-only evidence tables 不被直接编辑。
- Snapshot export/publish/reload 仍然是 import/replace 之后的独立序列。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_IMPORT_REPLACE_TRANSACTION_DESIGN.md`。

已完成 schema/load-parity 结果：

- Schema shape 可以在本地测试，且不改变 runtime defaults。
- File registry 和 persistent row mapping 已经用现有 fixture 证明。
- Canonical registry ordering 已有 regression tests 覆盖。
- `FileStore` 仍然是默认 runtime store。
- 不包含 hosted deployment、live database service、vault、billing 或 marketplace 工作。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_STORE_SCHEMA_REPORT.md`。

已完成 phase review 结果：

- runtime persistence readiness 已完成复盘。
- API2Agent-first 范围已重新确认。
- 下一项 runtime persistence slice 已收窄为 `PostgresStore.Load(ctx)` parity。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENCE_PHASE_REVIEW.md`。

已完成 PostgresStore load parity 结果：

- `PostgresStore.Load(ctx)` 通过 read-only `REPEATABLE READ` transaction 读取。
- Persistent rows 可以重建与 `FileStore` 相同的 in-memory `Registry` shape。
- File 和 Postgres-loaded registries 在测试中生成等价 snapshot contract output。
- Runtime store selection 和 live Postgres dogfood 保留为下一项切片。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_POSTGRES_STORE_LOAD_PARITY_REPORT.md`。

已完成 runtime wiring 结果：

- `--registry-store file|postgres` 和 `--postgres-dsn` 已接入 local commands。
- `seed-postgres` 可以把 file registry model import 到 persistent schema。
- `file` 仍然是默认 store。
- 当前环境没有 Docker 或 host `psql`，live dogfood 已使用 podman 完成。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_STORE_RUNTIME_WIRING_REPORT.md`。

已完成 live Postgres dogfood 结果：

- Podman provisioned 了临时 Postgres-compatible database。
- Schema apply、`seed-postgres`、snapshot export parity、CLI artifact export、service validation 和 service artifact export 都已通过。
- File-store 和 postgres-store snapshots 完全一致。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_LIVE_POSTGRES_STORE_DOGFOOD_REPORT.md`。

已完成 persistent export/publish audit 结果：

- Postgres runtime wiring 现在会接入 `PersistentAuditSink`。
- 配置 persistent audit sink 时，service registry validation、artifact export、distribution publish 和 current pointer reads 会写入 `admin_audit_events`。
- artifact export 成功后写入 `registry_revisions`。
- distribution publish 成功后写入 `snapshot_artifact_publications`。
- live Postgres dogfood 已验证 `admin_audit_events=4`、`registry_revisions=2`、`snapshot_artifact_publications=1`。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_EXPORT_PUBLISH_AUDIT_REPORT.md`。

已完成 persistent store failure semantics 结果：

- Postgres-backed registry load failures 现在返回 `PERSISTENT_STORE_READ_FAILED`，HTTP 503，platform scope，并标记为 retryable。
- File-store load failures 仍然保持 `REGISTRY_INVALID`，HTTP 400，caller scope，并标记为 non-retryable。
- required persistent audit writes 失败时，成功 admin operations 会 fail closed，返回 `AUDIT_WRITE_FAILED`。
- Failure-path admin audit writes 保持 best-effort，避免遮盖原始错误。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_STORE_FAILURE_SEMANTICS_REPORT.md`。

已完成 persistent registry mutation boundary review 结果：

- Granular registry CRUD APIs 暂缓。
- 下一条安全写侧路径是 controlled full-registry import/replace transaction。
- Mutable registry state 限定为 `projects`、`api_keys`、`capabilities`、`providers`、`credential_metadata`、`routing_policies` 和 `snapshot_configs`。
- `registry_revisions`、`snapshot_artifact_publications` 和 `admin_audit_events` 保持 append-only evidence surfaces。
- Transaction、audit、idempotency、failure 和 rollback requirements 已在实现前文档化。
- 详见 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENT_REGISTRY_MUTATION_BOUNDARY_REVIEW.md`。

后续 hosted 范围：

- hosted proxy endpoint
- durable database
- multi-project usage isolation
- hosted usage reporting
- basic credential vault

Hosted 退出标准：

- 外部用户可以让 generated calls 通过 hosted proxy
- hosted usage metrics 可靠
- credentials 不存入 generated files
- quota works per project

## 10. Phase 7：Economic Layer

状态：计划中。

目标：

让 usage 可计量、未来可收费，但不过早实现 payment、settlement 或 marketplace economics。

范围：

- pricing metadata
- free quota model
- estimated cost reporting
- routing-decision-linked usage ledger
- 按 project/capability/provider 聚合的 local usage ledger
- plan/quota configuration
- billing-ready usage ledger

退出标准：

- 每次 proxied call 都有 cost metadata
- local ledger 可以按 capability/provider 报告 calls、success rate、latency 和 estimated cost
- 可以按 project 计算 monthly usage
- 从 free quota 升级到 paid quota 的技术路径清晰

禁止扩展：

- 暂不做 revenue share settlement
- hosted usage 真实前不做完整 payment system

## 11. Phase 8：Capability Registry

状态：计划中。

目标：

持久化可复用 capabilities 和 provider candidates。

范围：

- capability registry
- provider candidate registry
- versioning
- quality metrics
- compatibility metadata
- install/search command

退出标准：

- 用户可以复用 registered capability
- 多个 providers 可以挂到同一个 capability
- routing 可以从 registry 读取，而不是 one-off JSON files

## 12. 远期可选方向：Agent Capability Marketplace

状态：远期目标，不是当前 active implementation phase。

目标：

创建 Agent 和 Agent builders 可以发现 capabilities、比较 providers，并基于 quality/cost/latency signals 路由调用的 marketplace。

范围：

- provider onboarding
- marketplace search
- pricing models
- billing
- revenue share
- trust and safety review
- public quality metrics

退出标准：

- providers 竞争 capability traffic
- 用户可以基于 observed metrics 选择 capabilities
- API2Agent 可以通过 usage、subscription 或 revenue share 变现

这个方向必须等 API2Agent 的 compiler、proxy、metrics、routing、hosted control plane、registry 和 billing-ready usage ledger 都可靠之后才允许启动。

## 13. 执行规则

任何 phase 开始主要实现前，必须满足：

- 前一个 phase tests passing
- 新 phase docs 已更新
- acceptance criteria 明确
- 至少定义一个 dogfood scenario

这条规则用于防止项目漂移到有趣但未计划的基础设施。
