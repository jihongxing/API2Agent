# API2Agent OpenAPI Filtering + curl Tool Naming Hardening Report v0

Date: 2026-05-31

Status: complete

## Summary

This hardening slice addressed the two highest-priority Tooling Baseline Audit findings without expanding scope beyond API-first tooling:

1. root-path curl APIs generated generic tool names like `get`
2. large OpenAPI specs could generate technically valid but Agent-hostile endpoint dumps

The implementation preserves backward compatibility for existing non-root curl paths and OpenAPI generation behavior.

## Changes

### curl root-path tool naming

Root-path curl inputs now include capability intent in the generated tool name.

Before:

```text
curl https://api.ipify.org?format=json
  -> tool: get
```

After:

```text
curl https://api.ipify.org?format=json
  -> tool: get_ipify_public_ip
```

Non-root curl paths keep the existing path-based behavior:

```text
curl https://api.example.com/items?format=json
  -> tool: get_items
```

This keeps existing generated package behavior stable while making root-path APIs easier for Agents to choose.

### Large OpenAPI generation diagnostics

OpenAPI generation now emits a warning when the generated package contains more than 50 tools:

```text
Warning: generated package contains N tools, which is likely too many for Agent tool selection.
Narrow the package with --include-tag, --include-path, --include-operation, or --max-tools.
```

This is intentionally diagnostic-only:

- no default truncation
- no hidden filtering
- no change to generated artifacts
- no workflow or non-API expansion

The goal is to lower onboarding cost by telling developers when they need a bounded package flow.

## Re-run Results

The Tooling Baseline Audit script was re-run after the hardening:

```bash
python scripts/api2agent_tooling_baseline_audit.py
```

Result summary:

| Measure | Result |
| --- | --- |
| curl generation success | 4/4 |
| curl first direct-call success | 4/4 |
| no-auth proxy first-call success | 3/3 |
| GitHub REST OpenAPI generation | success |
| GitHub REST unfiltered tool count | 1186 |
| GitHub REST filtered tool count | 3 |
| root-path ipify tool name | `get_ipify_public_ip` |

The large OpenAPI risk remains visible by design, but developers now receive an explicit warning when generating an oversized package through the CLI.

## Tests

Added regression coverage for:

- root-path curl naming uses capability intent
- non-root curl naming remains path-based
- large OpenAPI generation emits a warning when unbounded
- bounded large OpenAPI generation with `--max-tools` does not warn

Validated:

```text
python -m pytest tests/test_curl_parser.py tests/test_cli.py
python scripts/api2agent_tooling_baseline_audit.py
```

## Remaining Gap

Provider region metadata is still missing from generated packages.

This is now the highest-priority Tooling Re-entry gap because it directly supports the "faster Agent API responses" goal and future location-aware routing.

Next task:

```text
Generated Package Region Metadata v0
```

