# Capability Sources

## Purpose

API2Agent starts with APIs, but the long-term product is not limited to APIs.

The stable boundary is:

```text
anything executable -> API-like capability execution unit -> Agent-callable capability
```

API2Agent should not become a workflow engine, agent framework, script runtime, or marketplace-first product. It should make external capabilities executable, observable, routable, and eventually measurable for economics.

## Core Rule

A source can become an API2Agent capability only when it can be represented as:

```text
input -> execution -> output
```

If a source cannot be represented this way, it is outside API2Agent scope.

## MVP Boundary

MVP remains API-first.

Supported in MVP:

- OpenAPI
- curl
- HTTP/REST endpoints
- generated capability package
- proxy execution
- credential resolution
- usage, ledger, metrics
- provider routing and failover
- output normalization
- region-aware routing metadata

Not supported in MVP:

- workflow engine execution
- local function runtime
- arbitrary script sandbox
- database query runtime
- human task routing
- agent-as-provider execution
- marketplace search
- payment or settlement

MVP may reserve schema fields or adapter interfaces for future sources, but it must not implement those sources as first-class runtimes yet.

## Long-Term Capability Sources

Future API2Agent can support multiple capability sources through adapters.

| Source | Examples | API2Agent Role |
| --- | --- | --- |
| API | REST, GraphQL, gRPC, webhooks, SaaS APIs | Compile and execute as routable capabilities |
| Workflow | Zapier, n8n, Temporal, Airflow, internal workflows | Call workflow endpoints; do not become the workflow engine |
| Local Function / Tool | Python function, CLI command, local script | Wrap as a controlled executor with input/output schema |
| Stateful System | database, CRM, ERP, ecommerce backend, transaction system | Expose safe actions as capabilities |
| Human / Hybrid | human review, expert task, annotation | Treat human completion as an execution provider |
| Agent-as-Provider | specialized agent, internal assistant | Wrap another agent behind a capability contract |

## Capability Execution Unit

The long-term unifying abstraction is a Capability Execution Unit.

Minimum fields:

- `capability_id`
- `source_type`
- `input_schema`
- `output_schema`
- `executor`
- `provider_id`
- `auth`
- `cost_model`
- `latency_profile`
- `success_metrics`
- `region_metadata`
- `execution_mode`

Initial `source_type` values:

- `api`
- `workflow`
- `local_function`
- `cli`
- `database`
- `human`
- `agent`

## Sequencing

Recommended sequence:

1. v0.1-alpha: API only, but keep execution abstractions source-neutral.
2. v0.2: Local Function adapter prototype.
3. v0.3: Workflow adapter prototype.
4. v1.0: multiple source types behind the same control, routing, metrics, and credential layers.

Do not build a workflow engine. API2Agent should sit above workflow systems and make them Agent-callable.

## Strategic Sentence

MVP:

> API2Agent starts with APIs only, but every API is modeled as an executable capability so future workflow, function, and tool sources can reuse the same control, routing, metrics, and economic layers.

Long term:

> API2Agent becomes the neutral capability execution layer that lets Agents discover, route, call, observe, and eventually pay for any external capability source.
