# Routing Ledger Dogfood Report

Date: May 30, 2026

## Goal

Verify that API2Agent can execute a semantic capability through routing, proxy, usage tracking, routing-decision correlation, output normalization, and local usage ledger reporting.

This dogfood is about API2Agent itself. It does not validate marketplace behavior.

## Scenario

Capability:

- `public_ip_lookup`

Providers:

- `ipify`
  - source: `https://api.ipify.org?format=json`
  - output mapping: `ip <- $.ip`
  - estimated cost: `0.001`
- `httpbin`
  - source: `https://httpbin.org/ip`
  - output mapping: `ip <- $.origin`
  - estimated cost: `0.002`

Execution path:

```text
execute_capability
  -> route provider
  -> generated runner
  -> local API2Agent Proxy
  -> real provider API
  -> usage event with routing_decision_id
  -> normalized capability output
  -> local usage ledger
```

## Result

Both real providers succeeded through the proxy.

Normalized outputs:

```json
{
  "ipify": {
    "ip": "108.174.61.76"
  },
  "httpbin": {
    "ip": "108.174.61.76"
  }
}
```

Ledger rows:

```json
[
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "httpbin",
    "total_calls": 1,
    "successful_calls": 1,
    "failed_calls": 0,
    "success_rate": 1.0,
    "average_latency_ms": 5657.604599837214,
    "estimated_cost": 0.002
  },
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "ipify",
    "total_calls": 1,
    "successful_calls": 1,
    "failed_calls": 0,
    "success_rate": 1.0,
    "average_latency_ms": 2206.9931000005454,
    "estimated_cost": 0.001
  }
]
```

Usage summary:

```json
{
  "project_id": "local",
  "total_calls": 2,
  "successful_calls": 2,
  "failed_calls": 0,
  "success_rate": 1.0,
  "average_latency_ms": 3932.2988499188796,
  "estimated_cost": 0.003,
  "error_counts": {}
}
```

## Bugs Found

### 1. Semantic capability ID was not sent to proxy

Generated runners originally sent their package name as `capability_id`. Routing execution needs the semantic capability ID, such as `public_ip_lookup`.

Fix:

- `execute_capability` now sets `API2AGENT_CAPABILITY_ID`.
- generated runners prefer `API2AGENT_CAPABILITY_ID` before falling back to package name.

### 2. curl parameter defaults were not applied by generated runners

The ipify curl package preserved `format=json` as a parameter default, but the runner did not send default values when params were omitted. That made ipify return plain text instead of JSON, causing output normalization to fail.

Fix:

- generated runners now apply parameter defaults for query, header, and path parameters when explicit params are absent.

## Product Learning

The model stands:

- routing decision can be persisted
- proxy usage event can be correlated with `routing_decision_id`
- provider-specific success, latency, and estimated cost can be ledgered
- different provider response shapes can normalize into one capability output

The economic layer should continue as a measurement layer first. Payment, settlement, and marketplace mechanics remain out of current scope.

