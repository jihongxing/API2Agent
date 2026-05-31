# API2Agent Proxy-mode Credential Dogfood Expansion Report v0

Date: 2026-05-31

Status: complete

## Summary

Generated authenticated API packages can now be dogfooded through proxy mode with local credential config while keeping provider secrets out of generated packages, proxy payloads, usage events, and dogfood reports.

This closes the Tooling Re-entry authenticated proxy gap without changing the implementation boundary:

- API-first only
- no workflow engine
- no marketplace or billing
- no credential vault
- local proxy and local provider stub only

## What Was Verified

The new dogfood script runs this local path:

```text
generated curl package
  -> generated runner proxy mode
  -> local API2Agent proxy
  -> local credential config resolver
  -> local authenticated provider stub
  -> SQLite usage event
```

The generated package sends credential intent only. The request-side credential env var is intentionally absent. The proxy resolves a config credential, injects `Authorization: Bearer ...` into the provider request, and records only credential-safe attribution.

## Dogfood

Repro command:

```bash
python scripts/api2agent_proxy_credential_dogfood.py
```

Artifact:

```text
.dogfood/proxy-credential/result.json
```

Dogfood checks:

- generated runner returns a successful proxied response
- local provider is called exactly once
- proxy injects the config-sourced bearer credential
- one proxy usage event is recorded
- usage event records `credential_reference == "config:cred_proxy_dogfood"`
- credential metadata records source, scope, status, and rotation hint
- generated provider region is recorded as `local`
- raw secret is not written to usage events or dogfood report output
- request-side credential secret is not required
- scope remains API-first and no-vault

## Result

The dogfood passed.

Key observed values:

```json
{
  "credential_reference": "config:cred_proxy_dogfood",
  "provider_region": "local",
  "execution_mode": "proxy",
  "success": true
}
```

## Why This Matters

This task confirms that API2Agent can keep generated packages lightweight while still making authenticated calls observable through the proxy path.

That matters for the current Tooling Layer goals:

- more real execution data: authenticated calls can enter usage/ledger
- lower onboarding cost: developers do not need to edit generated runner source
- faster future routing: credential-safe usage events now preserve provider/region metadata needed for latency comparison

## Remaining Gap

The next Tooling Re-entry gap is speed measurement for generated packages.

Region metadata exists and authenticated proxy dogfood is now covered. The next task should make direct/proxy latency measurable for generated packages, including p50/p95 output.

Next task:

```text
Generated Package Latency Benchmark Helper v0
```
