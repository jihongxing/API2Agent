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

战略判断：

> API2Agent 起步是本地 Agent capability compiler，之后演进为 Agent 访问 API-backed capabilities 的 control、metrics、routing 和 reliable execution layer。

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

尚未实现：

- local generated package replay execution
- generated package shadow execution mode
- golden trace filtering command
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

## 9. Phase 6：Hosted Control Plane

状态：计划中。

目标：

把 local proxy concepts 迁移到 hosted service。

范围：

- hosted proxy endpoint
- project identity
- API keys for proxy access
- durable database
- multi-project usage isolation
- hosted usage reporting
- basic credential vault

退出标准：

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
