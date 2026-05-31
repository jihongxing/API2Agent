# API2Agent Tooling Baseline Audit Report v0

Date: 2026-05-31

Status: complete

Artifact:

```text
.dogfood/tooling-baseline-audit/result.json
```

Note: this artifact is overwritten when the baseline audit is re-run. The original baseline exposed weak root-path curl naming; the follow-up hardening report records the post-fix rerun. See `docs/en-US/API2AGENT_OPENAPI_FILTERING_CURL_NAMING_HARDENING_REPORT.md`.

Repro command:

```bash
python scripts/api2agent_tooling_baseline_audit.py
```

## Decision

API2Agent Tooling Re-entry can continue in Python as the Tooling reference implementation.

The current Tooling Layer is strong enough to generate and execute simple real API-backed Agent capabilities without manual source edits. The next work should not be another architecture pause; it should harden the two onboarding problems exposed by this audit:

1. large OpenAPI specs need better default filtering and diagnostics
2. curl-derived root-path APIs need better tool naming

Next task:

```text
API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0
```

## Scope

This audit measured the API-first Tooling Layer only:

- OpenAPI import
- curl import
- generated package quality
- generated direct execution
- generated proxy execution for no-auth read paths
- credential-safe generation for bearer auth
- latency visibility

It did not implement workflow execution, marketplace work, billing, credential vaults, or non-API runtimes.

## Summary

| Measure | Result |
| --- | --- |
| curl inputs audited | 4 |
| curl generation success | 4/4 |
| curl first-call success | 4/4 |
| proxy first-call success | 3/3 |
| large OpenAPI generation success | yes |
| GitHub REST unfiltered tool count | 1186 |
| GitHub REST filtered tool count | 3 |

## Inputs Audited

| Case | Input | Generated tool | Direct result | Proxy result | Naming |
| --- | --- | --- | --- | --- | --- |
| `curl_ipify_public_ip` | `curl https://api.ipify.org?format=json` | `get` | 3/3 success, p50 2192.308 ms | 1/1 success, p50 2048.922 ms | weak |
| `curl_open_meteo_forecast` | Open-Meteo forecast curl | `get_v1_forecast` | 3/3 success, p50 2413.028 ms | 1/1 success, p50 2402.383 ms | good |
| `curl_github_repo_read` | GitHub repo read curl | `get_repos_octocat_hello_world` | 3/3 success, p50 2048.375 ms | 1/1 success, p50 6110.973 ms | good |
| `curl_httpbin_bearer` | httpbin bearer curl | `get_bearer` | 3/3 success, p50 2198.133 ms | not run | good |
| `openapi_github_large_spec` | GitHub REST OpenAPI | `1186 tools` unfiltered | generation only | generation only | needs filtering |

Latency numbers are baseline samples from the current local environment, not global performance claims.

## Findings

### Positive: curl onboarding works for audited read-only APIs

ipify, Open-Meteo, GitHub repo read, and httpbin bearer all generated without manual source edits and achieved first successful direct execution.

This supports the current Tooling Re-entry decision: Python remains useful for low-cost API-first onboarding.

### Positive: generated packages are already observable-path ready

Generated packages include proxy-mode docs, `API2AGENT_PROXY_URL` support, timeout defaults, and credential intent code. The no-auth proxy audit recorded usage events successfully for ipify, Open-Meteo, and GitHub repo read.

### Positive: credential safety holds in audited paths

The bearer-auth case generated an env-based auth contract instead of hardcoding the raw token. The audited proxy usage events did not contain the bearer token marker.

### Medium: large OpenAPI specs still become endpoint dumps

GitHub REST OpenAPI generated successfully, but the unfiltered package contained 1186 tools. That is technically correct but not Agent-usable.

Filtering the same spec down to `/repos/{owner}/{repo}` produced 3 tools, proving the existing filter path works but needs better default guidance, diagnostics, or presets.

### Medium: root-path curl naming is weak

`curl https://api.ipify.org?format=json` generated a tool named `get`. This is too generic for Agent tool selection.

The capability name was good because the audit passed `--name` equivalent input, but tool naming still needs host/path intent for root-path APIs.

### Medium: provider region metadata is absent

Generated packages do not currently emit provider region metadata. This does not block current execution, but it weakens the faster-response and location-aware routing goals.

## Requirements Check

| Requirement | Status |
| --- | --- |
| at least five real API onboarding attempts documented | passed |
| generation success measured | passed |
| first-call path measured | passed |
| manual edits measured | passed |
| naming quality measured | passed |
| proxy compatibility measured | passed |
| credential safety measured | passed |
| p50/p95 latency measured where safe | passed |
| API-first constraint preserved | passed |
| no workflow engine expansion | passed |

## Ranked Next Fixes

1. `API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0`
   - Highest onboarding impact.
   - Directly addresses the 1186-tool GitHub REST dump and the `get` root-path curl tool name.

2. Generated package region metadata v0
   - Supports faster-response and future location-aware routing.
   - Should remain metadata-only, not a new routing rewrite.

3. Proxy-mode credential dogfood expansion
   - Extend baseline proxy runs to bearer/auth cases using local credential config.
   - Keep raw provider secrets out of generated files and events.

## Conclusion

The Tooling Layer is ready for focused hardening. It should not pivot to Go for this re-entry and should not expand into non-API sources.

The next implementation slice should reduce onboarding friction in the existing API-first compiler:

```text
API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0
```

Follow-up status: complete. Root-path curl naming now emits `get_ipify_public_ip` for the audited ipify case, and large OpenAPI generation now warns when the generated package remains oversized.
