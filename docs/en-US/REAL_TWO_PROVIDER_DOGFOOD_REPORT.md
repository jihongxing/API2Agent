# Real Two-Provider Dogfood Report

## 1. Goal

Validate whether the current Capability / Provider / Metrics / Routing model works with two real APIs mapped to one capability.

Capability:

```text
public_ip_lookup
```

Providers:

- ipify: `GET https://api.ipify.org?format=json`
- httpbin: `GET https://httpbin.org/ip`

## 2. Setup

Both generated packages used the same capability name:

```text
public_ip_lookup
```

Provider identity was set through:

```bash
API2AGENT_PROVIDER_ID=ipify
API2AGENT_PROVIDER_ID=httpbin
```

Both providers were called through API2Agent Proxy three times.

## 3. Raw Provider Outputs

ipify:

```json
{
  "ip": "108.174.61.76"
}
```

httpbin:

```json
{
  "origin": "108.174.61.76"
}
```

They fulfill the same intent, but they do not return the same output shape.

## 4. Metrics

| Provider | Total Calls | Success Rate | Avg Latency | Estimated Cost / Call |
|---|---:|---:|---:|---:|
| `ipify` | 3 | 100% | 2445 ms | 0.001 |
| `httpbin` | 3 | 100% | 3007 ms | 0.002 |

## 5. Routing Results

| Routing Policy | Selected Provider | Reason |
|---|---|---|
| `lowest_cost` | `ipify` | lower cost |
| `lowest_latency` | `ipify` | lower latency |
| `reliability_first` | `ipify` | both had 100% success, so latency/cost broke the tie |
| `cost_first` | `ipify` | lower cost |

## 6. What This Validates

- Two real APIs can map to one capability.
- Proxy usage events can aggregate under the same `capability_id` while preserving separate `provider_id`.
- Routing can select a provider using real observed metrics.
- Routing decision events include selected provider, ranked providers, strategy/preset, and metrics.

## 7. What This Exposes

Output normalization is now required before routing execution loop.

Target normalized output:

```json
{
  "ip": "108.174.61.76"
}
```

Provider-specific mappings:

```json
{
  "ipify": {
    "ip": "$.ip"
  },
  "httpbin": {
    "ip": "$.origin"
  }
}
```

Without this metadata, routing execution can choose a provider but cannot guarantee stable capability output for the Agent.

## 8. Decision

The current Capability / Provider / Metrics / Routing model stands up to the first real two-provider dogfood.

Roadmap-aligned follow-up is Capability Schema v0.2:

- output normalization metadata
- provider-specific output mapping
- normalized result contract

Do not implement routing execution loop until normalization metadata exists.

Status:

- v0.2 output normalization metadata has now been defined in `docs/en-US/CAPABILITY_SCHEMA.md`.
