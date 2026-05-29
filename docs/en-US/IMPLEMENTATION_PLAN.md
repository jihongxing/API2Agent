# API2Agent Implementation Plan

## 1. Current Build Target

The current repository implements the Free Tooling Layer:

```text
OpenAPI / curl
  -> API2Agent IR
  -> filtered capability package
  -> generated runner
  -> generated smoke test
  -> generated MCP server
```

This proves local usability. The next strategic build target is controlled execution through API2Agent Proxy.

## 2. Current Repository Structure

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

## 3. Completed Tooling Milestones

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

## 4. Remaining Tooling Reliability Work

These are still valuable, but they are no longer the strategic endpoint:

1. Endpoint-level auth
2. Base URL override
3. Manual write test path
4. Better curl naming
5. Large spec performance

Do not expand into many new input formats before proxy and metrics exist.

## 5. Next Major Build: Control Layer MVP

Goal:

```text
generated package
  -> API2Agent Proxy
  -> third-party API
  -> usage event
```

### Step 1: Usage Event Schema

Define a neutral event model:

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

Done when:

- event model can serialize to JSON
- tests cover success and failure events

### Step 2: Proxy Call Contract

Define:

```http
POST /v1/proxy/call
```

Request:

```json
{
  "capability_id": "github_repos",
  "tool_id": "list_repos",
  "provider_id": "github",
  "params": {}
}
```

Done when:

- contract is documented
- runner can be generated in direct mode or proxy mode

### Step 3: Local Proxy Prototype

Build a minimal local service first.

Suggested stack:

- FastAPI or simple ASGI app
- SQLite for usage events
- httpx for forwarding
- pytest for proxy tests

Done when:

- proxy forwards one generated tool call
- proxy records a usage event
- proxy returns structured success/error result

### Step 4: Quota MVP

Add project-level quota:

- max calls per project
- quota exceeded error
- usage count query

Done when:

- proxy blocks calls after quota
- quota event is recorded clearly

### Step 5: Metrics Report

Add CLI or endpoint report:

- total calls
- success rate
- average latency
- estimated cost
- error type counts

Done when:

- user can see whether an API capability is reliable and expensive

## 6. Capability Layer MVP

This layer starts with a minimal machine-readable schema.

Define:

- Capability Schema v0.1
- Provider Candidate model
- mapping from tool to capability
- metrics snapshot per candidate

Done when:

- two providers can map to one capability
- metrics can be compared

## 7. Routing Layer MVP

Routing v0 supports simple policies:

- random
- lowest estimated cost
- highest observed success rate
- lowest average latency
- balanced score

Done when:

- a capability request can route to one of two providers
- routing decision is logged
- failover can try a second provider

CLI:

```bash
api2agent route capability-registry.json \
  --capability-id image_generation \
  --strategy lowest_cost \
  --db api2agent-usage.sqlite
```

Minimal provider registry:

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

Credential orchestration comes before billing and marketplace work.

Define:

- Credential Schema v0.1
- owner types: user, project, platform, provider
- sources: env, config, inline, none
- resolver order
- injection patch contract
- usage event `credential_reference`
- redaction rules

Done when:

- one authenticated API can be called with a resolved local credential
- raw secrets are not stored in usage events
- replay warns when exact replay needs a credential that cannot be resolved
- ledger can preserve credential attribution without exposing secrets

Current implementation:

- Credential Schema v0.1 code models are implemented.
- Local resolver supports env/config/inline/none.
- Generated package execution can inject credentials.
- Usage events record `credential_reference`.
- Local package replay can re-resolve credentials from redacted metadata.
- Generated package proxy mode sends credential intent instead of provider secrets.
- Local proxy resolves credential intent and injects provider auth before forwarding.
- Local proxy can load JSON/YAML credential config through `--credential-config`.
- Config credentials can be used as provider-level fallback when payload credential intent is absent.
- Credential precedence is deterministic: inline, config, request/env intent, none.
- Config credential ownership prefers exact project owner, then local owner, then config order.
- Credential scope can restrict access by provider, capability, tool, or wildcard.
- Out-of-scope credentials fail with redacted `credential_scope_denied` errors.
- Credential lifecycle metadata supports status, expiry, and rotation hints.
- Disabled and expired credentials fail with redacted machine-readable errors.
- Usage CLI can print secret-safe credential audit events and failure counts.

Next engineering task:

```text
Authenticated proxy credential dogfood with a real API
```

## 9. Marketplace Is Later

Do not build a marketplace UI before:

- proxy works
- credential orchestration exists
- metrics exist
- capability abstraction exists
- routing works
- pricing metadata exists

Marketplace should be the result of routing plus economics, not the starting point.
