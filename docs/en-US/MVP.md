# API2Agent MVP Plan

## 1. MVP Definition

API2Agent now has a staged MVP.

```text
MVP-1: Usable
  OpenAPI/curl -> capability package -> runner/MCP -> successful local call

MVP-2: Controllable
  generated package -> API2Agent Proxy -> third-party API -> usage event / metrics / quota

MVP-2.5: Credential-aware
  generated package/proxy -> credential resolver -> provider API -> usage event with credential_reference
```

MVP-1 proves that APIs can become Agent-callable tools.

MVP-2 proves that API2Agent can observe and control the execution path, which is required before billing, routing, and marketplace.

MVP-2.5 proves that API2Agent can attribute API execution rights without becoming a payment system.

## 2. Current Implementation Status

MVP-1 status: implemented.

MVP-2 status: first local implementation is complete, pending dogfood.

Implemented MVP-2 capabilities:

- local `api2agent proxy`
- generated runner proxy mode via `API2AGENT_PROXY_URL`
- SQLite usage event storage
- `api2agent usage`
- project-level quota
- success/failure/status/latency/cost recording

Adjacent work already implemented:

- Capability Schema v0.1 code model
- Provider Candidate model
- Metrics Snapshot model
- Routing Policy model
- `api2agent route`

These adjacent pieces are not a license to continue beyond the roadmap. Routing execution loop must wait for the roadmap phase to be accepted.

Credential orchestration status: documented, not implemented.

## 3. MVP Promise

User-facing promise:

> Paste OpenAPI or curl. Get a working Agent tool package that can run directly or through API2Agent Proxy.

Internal promise:

> Make the first successful API call, then record whether it succeeded, how long it took, and what it may cost.

Strategic boundary:

> Payment, full billing, routing, and marketplace are not in MVP. Proxy, usage events, and quota are in MVP-2.

> Credential schema and local resolver are MVP-2.5 because credential ownership is required before API2Agent can become billing-ready infrastructure.

## 4. MVP Commands

Local tooling:

```bash
api2agent generate ./openapi.yaml --name my-api
api2agent inspect ./api2agent-output
api2agent test ./api2agent-output
api2agent run ./api2agent-output
```

Control layer:

```bash
api2agent proxy --db api2agent-usage.sqlite --port 8765 --quota 1000
api2agent usage --db api2agent-usage.sqlite --project-id local
```

Generated runners can use proxy mode through environment variables:

```bash
API2AGENT_PROXY_URL=http://127.0.0.1:8765
API2AGENT_PROJECT_ID=local
API2AGENT_PROVIDER_ID=example_api
```

## 5. MVP Output

Generated directory:

```text
api2agent-output/
  README.md
  capability.json
  tools.json
  mcp_server.py
  runner.py
  auth.env.example
  smoke_test.py
  examples/
    openai_agent.py
    claude_desktop_config.json
```

Proxy artifacts:

```text
api2agent-usage.sqlite
usage_events table
usage summary report
```

## 6. MVP-1 Functional Requirements: Usable

The CLI must:

- parse OpenAPI JSON/YAML
- parse curl commands
- normalize to API2Agent IR
- filter tools by tag/path/operation/max-tools
- generate a runnable capability package
- generate a local runner
- generate an MCP stdio server
- generate a smoke test

The generated runner must:

- validate required parameters
- substitute path parameters
- attach query parameters
- attach JSON body
- attach auth header from env var
- make direct HTTP requests by default
- return structured success/error results

## 7. MVP-2 Functional Requirements: Controllable

The proxy must:

- receive normalized call requests
- forward requests to third-party APIs
- measure latency
- record usage events
- classify success/failure
- estimate per-call cost when provided
- enforce project-level quota
- return structured success/error results

The generated runner must:

- keep direct mode as default
- switch to proxy mode when `API2AGENT_PROXY_URL` is set
- include project/capability/provider/tool metadata in proxy calls
- send a normalized HTTP request payload to the proxy

## 7.5 MVP-2.5 Functional Requirements: Credential-Aware

The credential resolver must:

- support env/config/inline sources
- represent credential owner and provider
- return an injection patch without exposing raw secrets
- attach `credential_reference` to usage events
- redact secrets from replay metadata and logs

The proxy path should:

- prefer proxy-side credential injection when possible
- keep generated packages from storing provider secrets in hosted mode

Usage reporting must show:

- total calls
- successful calls
- failed calls
- success rate
- average latency
- estimated cost
- error counts

## 8. MVP Non-Functional Requirements

### Reliability

- Generated Python files must run without syntax errors.
- Missing auth must produce clear instructions.
- Proxy errors must be structured.
- Quota exceeded must fail safely before forwarding.

### Developer Experience

- No SaaS signup.
- Local direct mode works without proxy.
- Proxy mode can run locally.
- README explains both paths.

### Safety

- Smoke tests default to read-only endpoints.
- Write/delete tools are not auto-tested by default.
- Proxy quota limits abuse.

### Neutrality

- MCP is the first runtime target, not the product boundary.
- API2Agent IR remains canonical.
- Proxy and usage events are model-neutral.

## 9. MVP Acceptance Tests

### Test 1: Local Usability

Expected:

- `api2agent generate examples/openapi/basic.yaml` works
- generated package includes runner/MCP/smoke test
- smoke test can call one safe endpoint

### Test 2: Tool Filtering

Expected:

- large specs can be narrowed before package generation
- selected tools appear in `capability.json`

### Test 3: Proxy Forwarding

Expected:

- generated runner sends a proxy payload when `API2AGENT_PROXY_URL` is set
- proxy forwards the request
- proxy returns structured result

### Test 4: Usage Event

Expected:

- every proxied call records a usage event
- event includes project, capability, provider, tool, success, status, latency, cost, and error type

### Test 5: Quota

Expected:

- proxy blocks calls after quota is exceeded
- quota failure is recorded and returned clearly

### Test 6: Credential Resolution

Expected:

- resolver can select an env/config credential for a provider
- execution injects the credential into the provider request
- usage event contains `credential_reference`
- raw secret is not stored in usage event metadata

## 10. MVP Exit Criteria

MVP-1 is complete when:

- local capability generation works
- generated runner works
- MCP server works
- smoke test works

MVP-2 is complete when:

- generated runner can call through API2Agent Proxy
- proxy records usage events
- proxy enforces quota
- usage report shows success/cost/latency

MVP-2.5 is complete when:

- credential schema is implemented
- local resolver supports env/config/inline sources
- execution can inject resolved credentials
- usage events safely record credential references

After MVP-2.5, the next phase is hardening capability naming and hosted control-plane design.
