# Routing Execution Dogfood Report

## 1. Goal

Validate the minimal local Routing Execution Loop:

```text
capability registry
  -> provider selection
  -> generated provider runner
  -> API2Agent Proxy
  -> third-party API
  -> output normalization
```

This is local-only. It is not a hosted routing service.

## 2. Capability

```text
public_ip_lookup
```

Provider candidates:

- ipify
- httpbin

Both providers were configured with `output_mapping` so their raw outputs normalize to:

```json
{
  "ip": "108.174.61.76"
}
```

## 3. Execution Results

### ipify via `cost_first`

Selected provider:

```text
ipify
```

Raw provider body:

```json
{
  "ip": "108.174.61.76"
}
```

Normalized body:

```json
{
  "ip": "108.174.61.76"
}
```

### httpbin via `first`

Selected provider:

```text
httpbin
```

Raw provider body:

```json
{
  "origin": "108.174.61.76"
}
```

Normalized body:

```json
{
  "ip": "108.174.61.76"
}
```

## 4. What Worked

- `api2agent call` selected a provider from registry metadata.
- The selected generated provider runner executed through API2Agent Proxy.
- Usage events were recorded by the proxy.
- Output normalization converted provider-specific raw bodies into one capability output shape.
- Routing decision output included selected provider, ranked providers, strategy/preset, and metrics.

## 5. What Remains

- Routing decision events are returned but not persisted.
- Failover path exists as an option but has not been dogfooded with a real failing provider.
- Provider package paths are currently local metadata, not registry-managed artifacts.
- Hosted routing is still out of scope.

## 6. Decision

Minimal local Routing Execution Loop is valid.

Next roadmap-aligned work should be:

1. persist routing decision events
2. correlate routing decision events with usage events
3. dogfood failover with one intentionally failing provider
4. only then consider hosted routing service design
