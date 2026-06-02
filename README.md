# API2Agent

API2Agent is the neutral infrastructure for turning APIs into Agent-callable capabilities.

Current focus: complete the Agent Capability Compiler release surface and dogfood real user onboarding paths. The release path stays narrow: convert API or API-equivalent descriptions into a local Agent capability package that can be inspected, diagnosed, smoke-tested, and exposed through MCP stdio.

Strategic priority: make API-to-Agent onboarding fast, reproducible, and safe enough to be the base layer for later routing, observability, hosted control, and commercial workflows.

RC3 status: published as a GitHub prerelease. Current follow-up work is limited to release-surface fixes, packaging/DX fixes, docs, and real-world dogfood findings.

Current implementation boundary: API-first. API2Agent supports OpenAPI, curl, HAR browser network capture, Postman Collection, Insomnia export, Bruno collection export, minimal gRPC/protobuf scaffolding, AsyncAPI HTTP webhook endpoints, workflow endpoint manifests, GraphQL endpoint manifests, and HTTP APIs today and must not become a workflow engine.

Implementation language boundary: Python remains the Tooling reference implementation and local dogfood harness; Go owns the production Data Plane and Control Plane direction. API2Agent's neutrality is protected by language-neutral protocol artifacts, not by treating Python as the only runtime.

v0.1 release candidate positioning:

```text
Agent Capability Compiler
```

Release candidate promise:

```text
OpenAPI / curl / HAR / Postman / Insomnia / Bruno / protobuf / AsyncAPI webhook / workflow endpoint / GraphQL endpoint -> Agent-callable capability package
```

The release candidate must prove that API2Agent can take an existing API description and produce artifacts an Agent developer can actually use: `capability.json`, `tools.json`, `runner.py`, `mcp_server.py`, generated docs, diagnostics, and smoke tests.

Marketplace, hosted SaaS, billing, workflow runtime, and Hosted Control Plane work are not part of the release candidate surface.

Current build target:

```text
OpenAPI 3.x / curl / HAR / Postman / Insomnia / Bruno / protobuf / AsyncAPI webhook / workflow endpoint / GraphQL endpoint
  -> API2Agent IR
  -> generated runner
  -> smoke test
  -> MCP server
```

## Install

The current public release candidate is distributed through GitHub Release assets:

- [v0.1.0rc3 release](https://github.com/jihongxing/API2Agent/releases/tag/v0.1.0rc3)
- `api2agent-0.1.0rc3-py3-none-any.whl`
- `api2agent-0.1.0rc3.tar.gz`

Install the wheel directly:

```bash
python -m pip install https://github.com/jihongxing/API2Agent/releases/download/v0.1.0rc3/api2agent-0.1.0rc3-py3-none-any.whl
api2agent --help
```

PyPI/TestPyPI publishing is not enabled yet. Until then, GitHub Release is the canonical public install path.

When verifying an installed wheel, run import/version checks outside the repository root so the local source tree does not shadow the installed package.

## Development

```bash
python -m pip install -e ".[dev]"
api2agent --help
pytest
```

## Docs

Core English docs:

- [Quickstart](docs/en-US/QUICKSTART.md)
- [Core Concepts](docs/en-US/CORE_CONCEPTS.md)
- [PRD](docs/en-US/PRD.md)
- [MVP Plan](docs/en-US/MVP.md)
- [API2Agent Protocol](docs/en-US/API2AGENT_PROTOCOL.md)
- [Technical Design](docs/en-US/TECHNICAL_DESIGN.md)
- [Implementation Plan](docs/en-US/IMPLEMENTATION_PLAN.md)
- [Roadmap](docs/en-US/ROADMAP.md)

Core Chinese docs:

- [Quickstart](docs/cn-ZH/QUICKSTART.md)
- [核心概念](docs/cn-ZH/CORE_CONCEPTS.md)
- [产品需求文档](docs/cn-ZH/PRD.md)
- [MVP 计划](docs/cn-ZH/MVP.md)
- [API2Agent Protocol](docs/cn-ZH/API2AGENT_PROTOCOL.md)
- [技术方案](docs/cn-ZH/TECHNICAL_DESIGN.md)
- [实施计划](docs/cn-ZH/IMPLEMENTATION_PLAN.md)
- [路线图](docs/cn-ZH/ROADMAP.md)

Project governance and active phase state:

- [Documentation Policy](docs/DOCUMENTATION_POLICY.md)
- [Hosted Control Plane Phase Log](docs/HOSTED_CONTROL_PLANE_PHASE_LOG.md) records the completed local v0 hosted-control work; it is not the current release-candidate focus.

Historical design, implementation, dogfood, and closeout reports remain in `docs/en-US/` and `docs/cn-ZH/`. They are intentionally no longer listed one by one in this README; use `rg` or the phase log when older evidence is needed.

## License

This repository is licensed under the Apache License 2.0.

API2Agent is planned as an open-core project: the local compiler, CLI, generated package templates, and related open-source code in this repository are Apache-2.0 licensed. Future hosted SaaS, managed registry, cloud execution, enterprise controls, or other proprietary services may be offered under separate commercial terms.

## First Demo

```bash
api2agent generate --curl="curl https://api.github.com/rate_limit" --name github_rate_limit --provider-region global --output api2agent-output --force
api2agent inspect api2agent-output
api2agent diagnose api2agent-output
api2agent test api2agent-output
```

The generated package contains:

- `capability.json` for API2Agent's neutral capability model
- `tools.json` for OpenAI-compatible tool definitions
- `runner.py` for local direct execution
- `mcp_server.py` for MCP stdio clients
- `smoke_test.py` and `manual_write_test.py`
- generated README, examples, diagnostics, and auth env template

Run the generated MCP server when you are ready to connect an MCP client:

```bash
api2agent run api2agent-output
```

`api2agent run` starts the generated MCP stdio server and keeps the process open for the client.

Generation refuses to write into a non-empty output directory unless you pass `--force`.

For real-world dogfood, start with a small read-only endpoint you control or a stable public endpoint, then run `generate`, `inspect`, `diagnose`, and only then `test`. A curl-generated package may still warn about weak tool descriptions because curl has less semantic metadata than OpenAPI. Public sample APIs can be stale or temporarily unavailable, so a failed smoke call is not always a compiler failure.

Postman Collection input is also supported:

```bash
api2agent generate --postman collection.json --output api2agent-postman-output --force
```

Insomnia and Bruno collection exports can be compiled through the same package path:

```bash
api2agent generate --insomnia insomnia-export.json --output api2agent-insomnia-output --force
api2agent generate --bruno bruno-collection.json --output api2agent-bruno-output --force
```

Protocol Buffers files can be compiled into minimal gRPC capability scaffolding. This extracts unary RPC schemas and tool metadata; generated gRPC tools require a future gRPC client or proxy transport before execution:

```bash
api2agent generate --proto service.proto --output api2agent-grpc-output --force
```

AsyncAPI HTTP webhook operations can be compiled as callable tools without turning API2Agent into an event bus:

```bash
api2agent generate --asyncapi asyncapi.yaml --output api2agent-asyncapi-output --force
```

Existing workflow endpoints can be compiled as one-tool capabilities without turning API2Agent into a workflow runtime:

```bash
api2agent generate --workflow workflow.json --output api2agent-workflow-output --force
```

GraphQL endpoints can be compiled from fixed operation manifests. The Agent supplies variables; the generated runner wraps them into the GraphQL request payload:

```bash
api2agent generate --graphql graphql.json --output api2agent-graphql-output --force
```

HAR browser network captures can be compiled when a real request exists but no formal API description is available:

```bash
api2agent generate --har capture.har --output api2agent-har-output --force
```

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
  --max-tools 20 \
  --provider-region us-east
```

Filtering rules:

- multiple values for the same option are ORed
- different filter types are intersected
- `--max-tools` applies after tag/path/operation filters
- `--include-path` accepts exact paths, substrings, or glob patterns

For large generated packages, `api2agent inspect` prints a bounded summary by default. Use `--all` to print every tool.

`--provider-region` is optional metadata for generated packages. Generated runners pass it to the local proxy as `provider_region`, and `API2AGENT_PROVIDER_REGION` can override it at runtime.

## Proxy, Usage, And Routing

Run a local proxy to observe and control generated API calls:

```bash
api2agent proxy --db api2agent-usage.sqlite --port 8765 --quota 1000
api2agent usage --db api2agent-usage.sqlite --project-id local
api2agent usage --db api2agent-usage.sqlite --credential-audit
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
