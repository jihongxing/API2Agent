# API2Agent Control Layer Dogfood Report

## 1. Goal

This dogfood round validates Phase 2 of the roadmap:

```text
generated runner
  -> API2Agent Proxy
  -> third-party API
  -> usage event / metrics / quota
```

The goal is not marketplace routing yet. The goal is to verify that generated packages can run through the API2Agent control point and produce useful execution data.

## 2. Setup

Local proxy:

```bash
api2agent proxy --db .dogfood/usage.sqlite --port 8765 --quota 3
```

Generated runners used proxy mode:

```bash
API2AGENT_PROXY_URL=http://127.0.0.1:8765
API2AGENT_PROJECT_ID=phase2-dogfood
API2AGENT_ESTIMATED_COST=0.001
```

## 3. Samples

| Sample | Input | Tool | Expected |
|---|---|---|---|
| JSONPlaceholder | `curl https://jsonplaceholder.typicode.com/posts/1` | `get_posts_1` | public read success |
| GitHub | `curl https://api.github.com/rate_limit` | `get_rate_limit` | public read success |
| httpbin | `curl https://httpbin.org/get?source=api2agent` | `get_get` | query param forwarded |
| JSONPlaceholder quota check | repeat first call | `get_posts_1` | blocked by quota |

## 4. Results

| Sample | Proxy Result | Status | Notes |
|---|---:|---:|---|
| JSONPlaceholder | success | 200 | body returned through proxy |
| GitHub | success | 200 | rate limit body returned through proxy |
| httpbin | success | 200 | query param preserved |
| JSONPlaceholder quota check | blocked | quota exceeded | proxy blocked before forwarding |

Usage summary:

```json
{
  "project_id": "phase2-dogfood",
  "total_calls": 4,
  "successful_calls": 3,
  "failed_calls": 1,
  "success_rate": 0.75,
  "average_latency_ms": 2772.82,
  "estimated_cost": 0.003,
  "error_counts": {
    "quota_exceeded": 1
  }
}
```

## 5. Observations

### What Worked

- Generated runners successfully switched to proxy mode through environment variables.
- Proxy forwarded real third-party API requests.
- Usage events were recorded for successful and blocked calls.
- Query parameters survived the runner -> proxy -> API path.
- Quota was enforced before forwarding the fourth call.
- Usage summaries were useful enough to expose success rate, latency, cost estimate, and error counts.

### What Is Still Weak

- The proxy currently receives ready-to-forward HTTP request payloads from the generated runner. This is fine for local MVP, but hosted mode should move credentials into a vault.
- Cost is caller-provided through `API2AGENT_ESTIMATED_COST`; it is not yet tied to provider pricing metadata.
- Quota is simple call count per project, not per capability/provider.
- Usage events and routing decisions are not yet correlated because routing execution loop is not implemented.
- No hosted multi-project isolation exists yet.

## 6. Decision

Phase 2 local Control Layer MVP is valid.

Do not jump to marketplace.

Next roadmap-aligned work should be:

1. Dogfood proxy mode with at least one authenticated API.
2. Improve provider/capability metadata so cost no longer depends on an env var.
3. Define a routing decision event before implementing routing execution loop.
4. Keep hosted proxy as a later phase until local proxy semantics are stable.

## 7. Authenticated API Follow-Up

Additional sample:

```text
curl https://httpbin.org/bearer -H "Authorization: Bearer dogfood-token"
```

Generated package:

```text
capability: httpbin_bearer
tool: get_bearer
auth env: HTTPBIN_BEARER_TOKEN
```

Proxy mode environment:

```bash
API2AGENT_PROXY_URL=http://127.0.0.1:8765
API2AGENT_PROJECT_ID=auth-dogfood
API2AGENT_ESTIMATED_COST=0.002
HTTPBIN_BEARER_TOKEN=dogfood-token
```

Result:

```json
{
  "ok": true,
  "proxied": true,
  "status_code": 200,
  "body": {
    "authenticated": true,
    "token": "dogfood-token"
  }
}
```

Usage summary:

```json
{
  "project_id": "auth-dogfood",
  "total_calls": 1,
  "successful_calls": 1,
  "failed_calls": 0,
  "success_rate": 1.0,
  "average_latency_ms": 2548.44,
  "estimated_cost": 0.002,
  "error_counts": {}
}
```

Missing auth behavior:

```json
{
  "ok": false,
  "error": {
    "type": "missing_auth",
    "env": "HTTPBIN_BEARER_TOKEN"
  }
}
```

Observation:

- Bearer auth works through generated runner -> proxy -> third-party API.
- Missing auth fails before proxy forwarding, so no third-party call is made and no usage event is recorded.
- This is safe for MVP, but future hosted mode may want to record local preflight failures separately.
