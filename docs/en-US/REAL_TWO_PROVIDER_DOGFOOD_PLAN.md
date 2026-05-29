# Real Two-Provider Dogfood Plan

## 1. Goal

Before implementing routing execution loop, API2Agent needs one real capability with two real providers.

This validates that the capability abstraction is not only synthetic.

## 2. Candidate Capability

Capability:

```text
public_ip_lookup
```

Agent intent:

> Return the caller's public IP address.

Why this capability:

- no API key required
- safe read-only behavior
- two public providers exist
- output schemas are simple but not identical, forcing normalization design

## 3. Providers

### Provider A: ipify

```text
GET https://api.ipify.org?format=json
```

Example output:

```json
{
  "ip": "203.0.113.10"
}
```

### Provider B: httpbin

```text
GET https://httpbin.org/ip
```

Example output:

```json
{
  "origin": "203.0.113.10"
}
```

## 4. Required Normalized Output

Both providers should normalize to:

```json
{
  "ip": "203.0.113.10"
}
```

This exposes the next product requirement: provider candidates need output normalization metadata before routing execution can be clean.

## 5. Dogfood Steps

1. Generate packages from both curl commands.
2. Run both through API2Agent Proxy.
3. Record usage metrics under `public_ip_lookup`.
4. Create a provider registry with both candidates.
5. Run routing strategies.
6. Confirm strategy changes selected provider.

## 6. Expected Learning

This dogfood should answer:

- can two real APIs map to one capability?
- what normalization metadata is required?
- can metrics compare real providers fairly?
- what must be added before routing execution loop?
