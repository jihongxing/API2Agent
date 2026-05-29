# API2Agent v0.1-alpha Plan

Status: planned

## 1. Alpha Positioning

API2Agent v0.1-alpha is:

> A local Agent API execution and observability layer for reliable multi-provider API calls.

The sharp user-facing promise is not "turn APIs into tools."

The sharper promise is:

> Make Agent API calls more reliable, measurable, and debuggable than calling providers directly.

Marketplace remains out of scope.

## 2. Required Product Hook

The alpha must prove why a developer should use API2Agent instead of calling APIs directly.

The chosen alpha hook is:

```text
Reliability + Observability
```

In plain terms:

- if one provider fails, API2Agent can fail over
- if two providers offer the same capability, API2Agent can compare them
- if a call fails in production, API2Agent can show what happened
- if provider quality changes over time, API2Agent has data for future routing

## 3. Alpha Demo

The primary alpha demo should be:

```text
one capability
  -> two providers
  -> primary failure
  -> fallback success
  -> usage ledger
  -> benchmark comparison
```

Suggested demo capability:

- `weather.current.get`

Suggested providers:

- `open_meteo`
- `wttr_in`

The demo must output:

- attempts
- selected provider
- fallback provider
- success rate
- p50/p95 latency
- ledger rows
- routing decision

The demo should make the product value visible:

```text
without API2Agent: direct provider call can fail silently
with API2Agent: failure is recorded, fallback succeeds, metrics are retained
```

## 4. Alpha Scope

Must include:

- local compiler
- SDK call path
- provider adapters
- routing strategy
- failover
- usage events
- ledger
- benchmark helper
- replay design
- capability naming rule
- execution mode matrix

May include:

- local replay command
- shadow execution mode
- golden trace marker

Must not include:

- marketplace UI
- hosted SaaS
- payment
- provider revenue share
- public provider onboarding

## 5. Capability Naming Rule

Alpha should enforce a minimum naming convention:

```text
<domain>.<resource>.<action>
```

Examples:

- `weather.current.get`
- `github.repo.list`
- `payment.charge.create`
- `crm.contact.lookup`

Temporary legacy IDs such as `weather.get` may remain for compatibility, but new docs and examples should prefer the alpha naming rule.

## 6. Execution Mode Matrix

API2Agent execution modes:

| Mode | Status | Purpose |
| --- | --- | --- |
| `direct` | implemented | local execution without proxy |
| `proxy` | implemented | controlled execution through API2Agent Proxy |
| `shadow` | planned | call extra providers for benchmark data without affecting the main result |
| `race` | future | call providers concurrently and return the best eligible result |

`shadow` is the key bridge from benchmark tooling to routing data.

## 7. Replay

Replay is a required alpha design item.

Goal:

```text
api2agent replay <usage_event_id>
```

Replay should help developers:

- debug failed calls
- reproduce provider behavior
- create regression tests from real calls
- audit routing decisions

Minimum replay requirements:

- usage event lookup
- routing decision lookup
- request metadata reconstruction
- safe redaction of credentials
- clear warning when exact replay is impossible

## 8. Golden Trace

Golden traces are selected executions that are known-good references.

Draft field:

```json
{
  "is_golden": true
}
```

Uses:

- regression testing
- provider scoring
- routing evaluation
- future benchmark baselines

Golden traces are not required in the first code slice, but the contract should not block them.

## 9. Alpha Exit Criteria

v0.1-alpha is complete when:

- the repo has a clean baseline commit
- `pytest` passes
- README and Quickstart reproduce the alpha demo
- one capability runs through two providers
- failover records failed and successful attempts
- benchmark reports p50/p95 latency and success rate
- ledger can inspect calls by provider and execution mode
- replay is designed and either implemented locally or explicitly marked as the next alpha task

## 10. Next Implementation Order

1. repo baseline and CHANGELOG
2. alpha quickstart
3. capability naming validation warning
4. replay design and local command
5. shadow execution mode
6. golden trace field
7. SDK and CLI demo cleanup
