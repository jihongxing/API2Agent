# API2Agent curl Naming Residual Review v0

Date: 2026-05-31

Status: complete

## Summary

The curl naming residual review found one real remaining issue:

```text
api.github.com -> capability: api
```

Root-path tool naming had already been fixed, but default capability/provider naming for generic subdomains such as `api.github.com` was still too vague. This also produced generic credential env names such as `API_TOKEN`.

This review closes that residual without reopening the broader naming strategy.

Scope stayed constrained:

- curl input only
- API-first only
- no workflow engine
- no hosted registry or control-plane change
- preserve explicit `--name`
- preserve non-root path-based tool naming

## What Changed

curl-derived capability names now skip generic leading subdomains:

```text
api.github.com -> github_api
www.example.com -> example_www
```

This improves generated provider/capability identity and credential env names.

Example:

```text
curl https://api.github.com/rate_limit -H 'Authorization: Bearer token'
```

Before:

```text
capability: api
tool: get_rate_limit
auth env: API_TOKEN
```

After:

```text
capability: github_api
tool: get_rate_limit
auth env: GITHUB_API_TOKEN
```

Existing guarantees remain:

- explicit `--name` still wins
- root-path curl tools still include capability intent
- non-root path tools remain path-based for backward compatibility

## Dogfood

Repro command:

```bash
python scripts/api2agent_curl_naming_residual_review.py
```

Artifact:

```text
.dogfood/curl-naming-residual-review/result.json
```

Dogfood cases:

| Case | Expected |
| --- | --- |
| `curl https://api.github.com/rate_limit -H 'Authorization: Bearer token'` | `github_api`, `get_rate_limit`, `GITHUB_API_TOKEN` |
| `curl https://api.ipify.org?format=json` | `ipify_api`, `get_ipify_api` |
| same ipify curl with explicit `--name ipify_public_ip` | `ipify_public_ip`, `get_ipify_public_ip` |
| `curl https://api.example.com/items?format=json` | `example_api`, `get_items` |

## Result

The dogfood passed.

Key checks:

```json
{
  "all_cases_generated": true,
  "capability_names_match": true,
  "tool_names_match": true,
  "auth_envs_match": true,
  "explicit_name_still_wins": true,
  "non_root_path_stays_path_based": true
}
```

## Why This Matters

This closes the remaining naming friction in the Tooling Re-entry backlog:

- provider/capability ids are less generic by default
- credential env names are more meaningful
- Agents still get stable path-based tool names for non-root APIs
- developers can still override naming explicitly with `--name`

## Phase Closeout

The active Tooling Re-entry backlog is now closed, and the Tooling Re-entry Closeout + Phase Review is complete.

Next task:

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```
