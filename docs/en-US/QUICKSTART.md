# API2Agent Quickstart

This quickstart proves the release-candidate path:

```text
OpenAPI 3.x / curl / Postman Collection
  -> API2Agent IR
  -> Agent capability package
  -> OpenAI tools schema
  -> local runner
  -> MCP stdio server
  -> smoke test
```

The current release focus is the Agent Capability Compiler. Routing, proxy usage, ledgers, failover, and hosted control are useful later layers, but they are not required to prove the first publishable version.

## 1. Install

```bash
python -m pip install -e ".[dev]"
python -m api2agent.cli --help
python -m pytest
```

Expected test result:

```text
242 passed
```

## 2. Generate From OpenAPI

```bash
python -m api2agent.cli generate examples/openapi/basic.yaml --output api2agent-output --force
```

Expected output:

```text
Generated capability package: api2agent-output
Diagnostics: pass ...
```

The generated directory contains:

- `capability.json`
- `tools.json`
- `diagnostics.json`
- `auth.env.example`
- `README.md`
- `runner.py`
- `smoke_test.py`
- `manual_write_test.py`
- `mcp_server.py`
- `examples/openai_agent.py`
- `examples/claude_desktop_config.json`

## 3. Inspect The Package

```bash
python -m api2agent.cli inspect api2agent-output
```

This shows the generated capability name, base URL, auth shape, safety summary, tool list, parameter requirements, and response summaries.

For raw JSON:

```bash
python -m api2agent.cli inspect api2agent-output --json
```

## 4. Diagnose Readiness

```bash
python -m api2agent.cli diagnose api2agent-output
```

Diagnostics are advisory by default. They are meant to tell you whether the generated package is safe and clear enough to wire into an Agent.

Common signals:

- missing provider region metadata
- missing or weak operation descriptions
- write/delete tools that require deliberate manual testing
- missing base URL or auth metadata
- schema or response-shape caveats

## 5. Run The Smoke Test

```bash
python -m api2agent.cli test api2agent-output
```

The default smoke test only runs a safe read-only path. If a generated package only contains write/delete tools, use `--allow-write` only against a target you control:

```bash
python -m api2agent.cli test api2agent-output --allow-write
```

You can also run one generated tool directly:

```bash
python -m api2agent.cli test api2agent-output --tool get_post --params "{\"post_id\": 1}"
```

## 6. Try OpenAI Tool Calling

The generated package includes a Responses API example that loads `tools.json` and dispatches tool calls through the generated runner:

```bash
python -m pip install openai
OPENAI_API_KEY=...
python api2agent-output/examples/openai_agent.py
```

The OpenAI SDK is optional for API2Agent itself; install it only when you want to run this example.

## 7. Run The MCP Server

```bash
python -m api2agent.cli run api2agent-output
```

This starts the generated MCP stdio server and keeps the process open for an MCP client.

For Claude Desktop-style wiring, start from:

```text
api2agent-output/examples/claude_desktop_config.json
```

## 8. Generate From curl

Use `--curl` when you do not have an OpenAPI file yet:

```bash
python -m api2agent.cli generate \
  --curl="curl https://api.example.com/items?verbose=true --json '{\"name\":\"demo\"}'" \
  --output api2agent-curl-output \
  --force

python -m api2agent.cli inspect api2agent-curl-output
python -m api2agent.cli diagnose api2agent-curl-output
```

curl-generated write tools intentionally produce stronger diagnostics. That is useful: the compiler should make risky generated packages visible before an Agent can call them.

## 9. Generate From Postman Collection

Use `--postman` when your API contract lives in a Postman Collection:

```bash
python -m api2agent.cli generate \
  --postman tests/fixtures/postman/basic_collection.json \
  --output api2agent-postman-output \
  --force

python -m api2agent.cli inspect api2agent-postman-output
python -m api2agent.cli diagnose api2agent-postman-output
```

Postman folders become tool tags, collection variables can provide the base URL, and request path/query/header/body shapes are compiled into the same generated package format.

## 10. Narrow Large APIs

Large OpenAPI specs often expose too many endpoints for Agent tool selection. Filter before generating:

```bash
python -m api2agent.cli generate api.github.com.json \
  --include-tag repos \
  --include-path /repos \
  --include-operation listRepos \
  --max-tools 20 \
  --provider-region us-east \
  --output github-repos-agent \
  --force
```

Filtering rules:

- values for the same option are ORed
- different filter types are intersected
- `--max-tools` applies after other filters
- `--include-path` accepts exact paths, substrings, or glob patterns

## 11. What This Proves

The release candidate proves that API2Agent can:

- parse OpenAPI, curl, and Postman Collection API descriptions
- compile them into a neutral capability model
- generate OpenAI-compatible tool definitions
- generate a runnable OpenAI Responses API tool-calling example
- generate a local runner
- generate an MCP stdio server
- generate docs, examples, diagnostics, and test files
- smoke-test safe generated read tools
- warn when generated packages need human review before Agent use

Out of scope for this release candidate:

- hosted SaaS
- marketplace and billing
- workflow runtime
- Hosted Control Plane
- production Data Plane deployment
- provider revenue share
