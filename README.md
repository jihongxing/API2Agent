# API2Agent

API2Agent is the neutral infrastructure for turning APIs into Agent-callable capabilities.

Current focus: build API2Agent itself: compiler, capability package, proxy, metrics, routing, and execution reliability.

v0.1-alpha positioning:

```text
Local Agent API Execution + Observability Layer
```

Alpha product hook:

```text
Reliability + Observability
```

The alpha must prove that API2Agent makes Agent API calls more reliable, measurable, and debuggable than calling providers directly.

Marketplace is a far-term possibility, not the current product, MVP, or active implementation phase.

Current build target:

```text
OpenAPI 3.x / curl
  -> API2Agent IR
  -> generated runner
  -> smoke test
  -> MCP server
```

## Development

```bash
python -m pip install -e ".[dev]"
api2agent --help
pytest
```

## Docs

English:

- [Core Concepts](docs/en-US/CORE_CONCEPTS.md)
- [Quickstart](docs/en-US/QUICKSTART.md)
- [API2Agent Protocol](docs/en-US/API2AGENT_PROTOCOL.md)
- [PRD](docs/en-US/PRD.md)
- [MVP Plan](docs/en-US/MVP.md)
- [Roadmap](docs/en-US/ROADMAP.md)
- [v0.1-alpha Plan](docs/en-US/V0_1_ALPHA_PLAN.md)
- [Technical Design](docs/en-US/TECHNICAL_DESIGN.md)
- [Implementation Plan](docs/en-US/IMPLEMENTATION_PLAN.md)
- [Capability Schema](docs/en-US/CAPABILITY_SCHEMA.md)
- [Routing Policy](docs/en-US/ROUTING_POLICY.md)
- [Decision and Usage Contract](docs/en-US/DECISION_USAGE_CONTRACT.md)
- [Provider Registry Contract](docs/en-US/PROVIDER_REGISTRY_CONTRACT.md)
- [Credential Orchestration](docs/en-US/CREDENTIAL_ORCHESTRATION.md)
- [Credential Resolver Dogfood Report](docs/en-US/CREDENTIAL_RESOLVER_DOGFOOD_REPORT.md)
- [Real Two-Provider Dogfood Plan](docs/en-US/REAL_TWO_PROVIDER_DOGFOOD_PLAN.md)
- [Real Two-Provider Dogfood Report](docs/en-US/REAL_TWO_PROVIDER_DOGFOOD_REPORT.md)
- [Routing Execution Dogfood Report](docs/en-US/ROUTING_EXECUTION_DOGFOOD_REPORT.md)
- [Routing Ledger Dogfood Report](docs/en-US/ROUTING_LEDGER_DOGFOOD_REPORT.md)
- [Failover Ledger Dogfood Report](docs/en-US/FAILOVER_LEDGER_DOGFOOD_REPORT.md)
- [Failover Policy Dogfood Report](docs/en-US/FAILOVER_POLICY_DOGFOOD_REPORT.md)
- [E2E Core Loop Report](docs/en-US/E2E_CORE_LOOP_REPORT.md)
- [API2Agent Benchmark v0.1](docs/en-US/API2AGENT_BENCHMARK_V0_1.md)
- [SDK Failover Dogfood Report](docs/en-US/SDK_FAILOVER_DOGFOOD_REPORT.md)
- [Shadow Mode Dogfood Report](docs/en-US/SHADOW_MODE_DOGFOOD_REPORT.md)
- [Replay Dogfood Report](docs/en-US/REPLAY_DOGFOOD_REPORT.md)
- [Golden Trace Dogfood Report](docs/en-US/GOLDEN_TRACE_DOGFOOD_REPORT.md)
- [Generated Package Shadow + Replay Dogfood Report](docs/en-US/GENERATED_PACKAGE_SHADOW_REPLAY_DOGFOOD_REPORT.md)
- [Far-Term Economic Strategy](docs/en-US/ECONOMIC_MARKETPLACE_STRATEGY.md)
- [Dogfood Report](docs/en-US/DOGFOOD_REPORT.md)
- [Control Layer Dogfood Report](docs/en-US/CONTROL_LAYER_DOGFOOD_REPORT.md)
- [Capability Routing Dogfood Report](docs/en-US/CAPABILITY_ROUTING_DOGFOOD_REPORT.md)

中文：

- [核心概念](docs/cn-ZH/CORE_CONCEPTS.md)
- [Quickstart](docs/cn-ZH/QUICKSTART.md)
- [API2Agent Protocol](docs/cn-ZH/API2AGENT_PROTOCOL.md)
- [产品需求文档](docs/cn-ZH/PRD.md)
- [MVP 计划](docs/cn-ZH/MVP.md)
- [路线图](docs/cn-ZH/ROADMAP.md)
- [v0.1-alpha 计划](docs/cn-ZH/V0_1_ALPHA_PLAN.md)
- [技术方案](docs/cn-ZH/TECHNICAL_DESIGN.md)
- [实施计划](docs/cn-ZH/IMPLEMENTATION_PLAN.md)
- [Capability Schema](docs/cn-ZH/CAPABILITY_SCHEMA.md)
- [Routing Policy](docs/cn-ZH/ROUTING_POLICY.md)
- [Decision and Usage Contract](docs/cn-ZH/DECISION_USAGE_CONTRACT.md)
- [Provider Registry Contract](docs/cn-ZH/PROVIDER_REGISTRY_CONTRACT.md)
- [Credential Orchestration](docs/cn-ZH/CREDENTIAL_ORCHESTRATION.md)
- [Credential Resolver Dogfood 报告](docs/cn-ZH/CREDENTIAL_RESOLVER_DOGFOOD_REPORT.md)
- [真实 Two-Provider Dogfood 计划](docs/cn-ZH/REAL_TWO_PROVIDER_DOGFOOD_PLAN.md)
- [真实 Two-Provider Dogfood 报告](docs/cn-ZH/REAL_TWO_PROVIDER_DOGFOOD_REPORT.md)
- [Routing Execution Dogfood 报告](docs/cn-ZH/ROUTING_EXECUTION_DOGFOOD_REPORT.md)
- [Routing Ledger Dogfood 报告](docs/cn-ZH/ROUTING_LEDGER_DOGFOOD_REPORT.md)
- [Failover Ledger Dogfood 报告](docs/cn-ZH/FAILOVER_LEDGER_DOGFOOD_REPORT.md)
- [Failover Policy Dogfood 报告](docs/cn-ZH/FAILOVER_POLICY_DOGFOOD_REPORT.md)
- [E2E Core Loop 报告](docs/cn-ZH/E2E_CORE_LOOP_REPORT.md)
- [API2Agent Benchmark v0.1](docs/cn-ZH/API2AGENT_BENCHMARK_V0_1.md)
- [SDK Failover Dogfood 报告](docs/cn-ZH/SDK_FAILOVER_DOGFOOD_REPORT.md)
- [Shadow Mode Dogfood 报告](docs/cn-ZH/SHADOW_MODE_DOGFOOD_REPORT.md)
- [Replay Dogfood 报告](docs/cn-ZH/REPLAY_DOGFOOD_REPORT.md)
- [Golden Trace Dogfood 报告](docs/cn-ZH/GOLDEN_TRACE_DOGFOOD_REPORT.md)
- [Generated Package Shadow + Replay Dogfood 报告](docs/cn-ZH/GENERATED_PACKAGE_SHADOW_REPLAY_DOGFOOD_REPORT.md)
- [远期经济层策略](docs/cn-ZH/ECONOMIC_MARKETPLACE_STRATEGY.md)
- [Dogfood 报告](docs/cn-ZH/DOGFOOD_REPORT.md)
- [Control Layer Dogfood 报告](docs/cn-ZH/CONTROL_LAYER_DOGFOOD_REPORT.md)
- [Capability Routing Dogfood 报告](docs/cn-ZH/CAPABILITY_ROUTING_DOGFOOD_REPORT.md)

## License

This repository is licensed under the Apache License 2.0.

API2Agent is planned as an open-core project: the local compiler, CLI, generated package templates, and related open-source code in this repository are Apache-2.0 licensed. Future hosted SaaS, managed registry, cloud execution, enterprise controls, or other proprietary services may be offered under separate commercial terms.

## First Demo

```bash
api2agent generate examples/openapi/basic.yaml
api2agent inspect api2agent-output
api2agent test api2agent-output
api2agent run api2agent-output
```

`api2agent run` starts the generated MCP stdio server and will keep the process open for an MCP client.

Generation refuses to write into a non-empty output directory unless you pass `--force`.

## SDK Core Loop

The first hand-written E2E loop supports one real-world capability:

```python
from api2agent import call

result = call(
    capability="weather.get",
    input={"city": "San Francisco"},
)
```

This routes to a weather provider adapter, normalizes the weather response, records a routing decision, writes a usage event, and updates the local ledger.

Choose a specific weather provider:

```python
result = call(
    capability="weather.get",
    input={"city": "San Francisco"},
    provider_id="wttr_in",
)
```

After providers have usage history, the default SDK route uses the lowest observed latency for that capability. You can make routing policy explicit:

```python
result = call(
    capability="weather.get",
    input={"city": "San Francisco"},
    strategy="lowest_latency",
)
```

Enable local failover across ranked providers:

```python
result = call(
    capability="weather.get",
    input={"city": "San Francisco"},
    strategy="first",
    failover=True,
    max_attempts=2,
)
```

Failed attempts and successful fallback attempts share one routing decision and are both recorded in the local usage ledger.

Run a small repeated benchmark:

```python
from api2agent.benchmark import run_weather_benchmark

result = run_weather_benchmark(
    city="San Francisco",
    iterations=3,
    db=".dogfood/weather-benchmark-repeat.sqlite",
)
```

## Tool Filtering

Large OpenAPI specs usually expose too many endpoints for an Agent to use directly. Narrow the generated package before files are written:

```bash
api2agent generate api.github.com.json \
  --include-tag repos \
  --include-path /repos \
  --include-operation listRepos \
  --max-tools 20
```

Filtering rules:

- multiple values for the same option are ORed
- different filter types are intersected
- `--max-tools` applies after tag/path/operation filters
- `--include-path` accepts exact paths, substrings, or glob patterns

For large generated packages, `api2agent inspect` prints a bounded summary by default. Use `--all` to print every tool.

## Proxy, Usage, And Routing

Run a local proxy to observe and control generated API calls:

```bash
api2agent proxy --db api2agent-usage.sqlite --port 8765 --quota 1000
api2agent usage --db api2agent-usage.sqlite --project-id local
api2agent ledger --db api2agent-usage.sqlite --project-id local --month 2026-05
api2agent ledger --db api2agent-usage.sqlite --project-id local --group-by-mode
api2agent ledger --db api2agent-usage.sqlite --capability-id public_ip_lookup --provider-id ipify
api2agent ledger --db api2agent-usage.sqlite --golden-only
```

Generated runners use proxy mode when `API2AGENT_PROXY_URL` is set.
The proxy can also load project-level credentials without putting provider secrets into generated packages:

```bash
api2agent proxy --db api2agent-usage.sqlite --credential-config credentials.yaml
```

```yaml
credentials:
  - credential_id: github_token
    provider_id: github
    auth_type: bearer
    injection_mode: header
    injection_name: Authorization
    source: env
    secret_ref: GITHUB_TOKEN
```

Route a semantic capability to a provider candidate using observed metrics:

```bash
api2agent registry capability-registry.json
api2agent route capability-registry.json \
  --capability-id image_generation \
  --strategy lowest_cost \
  --db api2agent-usage.sqlite
```

Enable explicit failover policy for execution:

```bash
api2agent call capability-registry.json \
  --capability-id public_ip_lookup \
  --failover \
  --max-attempts 2 \
  --retry-on-status 500
```

Run generated package providers in shadow mode without changing the main result:

```bash
api2agent call capability-registry.json \
  --capability-id public_ip_lookup \
  --shadow
```

Minimal registry format:

```json
{
  "contract_version": "provider_registry.v0.1",
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

Registry JSON is schema-validated before routing or execution. Invalid provider entries fail fast instead of being silently ignored.

`api2agent route` and `api2agent call` persist routing decisions in the local usage database. When generated runners execute through the proxy, usage events include `routing_decision_id` so provider choice, success, latency, and estimated cost can be audited together.

`api2agent ledger` groups usage by project, capability, and provider. It is billing-ready measurement only: no payment flow, subscription logic, settlement, or marketplace behavior is included.

Inspect one routing decision and its correlated usage events:

```bash
api2agent decision <routing_decision_id> \
  --db api2agent-usage.sqlite \
  --json
```

Mark, list, and replay known-good usage events:

```bash
api2agent golden <usage_event_id> --db api2agent-usage.sqlite
api2agent golden --list --db api2agent-usage.sqlite --capability-id weather.get
api2agent replay <usage_event_id> --db api2agent-usage.sqlite --execute --record
```

## curl Input

Use `--curl=...` so shells do not confuse the curl command with the optional spec argument:

```bash
api2agent generate --curl="curl https://api.example.com/items?verbose=true --json '{\"name\":\"demo\"}'"
```

On PowerShell, wrap the whole option in single quotes:

```powershell
api2agent generate '--curl=curl https://api.example.com/items?verbose=true --json "{\"name\":\"demo\"}"'
```
