# Architecture Definition Phase

## 决策

API2Agent 已经退出 Python MVP validation，进入 Architecture Definition Phase。

这一阶段的目标是在继续实现之前，先定义 production architecture。

## 为什么需要这个阶段

项目已经跨过 feasibility threshold。

现在继续加 Python 功能会带来风险：

- protocol 被 reference runtime 细节塑形
- control plane 和 data plane 边界继续模糊
- future production implementation 继承 MVP shortcuts
- marketplace 和 routing data models 定义不足

## 工作流

### 1. Protocol Freeze

输出：

- API2Agent Protocol v0.2 plan
- API2Agent Protocol v0.2 frozen contract
- API2Agent Protocol v0.2 schema snapshot
- v0.1 compatibility story
- stable schema ownership

### 2. Control Plane vs Data Plane

Data Plane responsibilities：

- proxy execution
- routing decision evaluation
- retry and failover
- provider-region selection
- low-latency metering

建议技术：

- Go

Control Plane responsibilities：

- capability registry
- provider onboarding
- credential vault
- pricing and SLA metadata
- analytics
- decision dataset

建议技术：

- Go for backend
- TypeScript for future dashboard

Python role：

- reference implementation
- compiler/local tooling
- dogfood harness

### 3. Production Component Split

目标组件：

- Agent SDK
- Edge Proxy
- Routing Engine
- Provider Adapter Layer
- Control Plane API
- Capability Registry
- Credential Vault
- Usage and Ledger Store
- Decision Dataset Pipeline

### 4. Data Model Finalization

关键模型：

- Usage Event
- Decision Log
- Capability Graph
- Provider Registry
- Credential Ownership
- Latency Profile
- Reliability Profile

## Freeze Rules

这个阶段不要构建：

- new capability source runtimes
- marketplace UI
- billing and settlement
- hosted SaaS product
- major Python feature expansions

允许的工作：

- protocol docs
- schema design
- architecture RFCs
- migration planning
- small reference tests that protect contract clarity

## 退出标准

Architecture Definition Phase 退出条件：

- Protocol v0.2 plan 完成
- Production Architecture RFC 完成
- Control Plane 和 Data Plane responsibilities 明确
- long-term language/runtime choices 已文档化
- Python reference implementation migration path 已定义
