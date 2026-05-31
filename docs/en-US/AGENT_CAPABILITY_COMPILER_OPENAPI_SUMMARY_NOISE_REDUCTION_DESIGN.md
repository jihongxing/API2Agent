# Agent Capability Compiler OpenAPI Summary Noise Reduction Design v0

Date: 2026-06-01

Status: complete

## Decision

The next Agent Capability Compiler implementation slice should be:

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Implementation v0
```

This slice should make generated README and `api2agent inspect` output easier to scan for metadata-rich OpenAPI packages by adding bounded summary budgets, repeated-finding folding, and risk-first prioritization. It should preserve raw capability data, diagnostics data, and full JSON output, while making default human-facing summaries compact enough for repeated use.

## Why This Slice Now

The real-spec calibration harness and diagnostics score calibration changed the evidence picture:

- metadata-rich schema/auth/server cases now score above the false-low threshold
- write-heavy and large-surface packages still remain visible warnings
- the next user-facing friction is no longer the numeric score, but summary density

Current output has become more capable, but also noisier:

- `inspect` prints aggregate schema hint counts, response categories, diagnostics, and then detailed parameters/body/responses per visible tool
- README prints every tool with auth, parameters, body, and response summaries
- schema-rich response summaries can expand large object shapes into long single lines
- repeated warnings such as missing success response schemas can dominate diagnostics detail
- large packages already truncate tool lists, but compact packages with rich schemas can still be hard to scan

The compiler should now keep the metadata, but present it with a clearer reading order.

## Current Baseline

Already present:

- `api2agent inspect --json` exposes full raw capability JSON
- `api2agent diagnose --json` exposes full raw diagnostics JSON
- default inspect output summarizes auth, servers, safety counts, top tags, path prefixes, schema hints, response categories, diagnostics, and tool details
- README contains auth, provider region, base URL override, tools, smoke test, runner, and proxy sections
- response shape documentation, schema keyword summaries, discriminator summaries, server metadata, and diagnostics are visible
- large tool lists can be truncated with `--limit` / `--all`

Important gaps:

- no shared summary budget for default human output
- no distinction between high-risk caveats and expected metadata notes in rendered summaries
- repeated per-operation findings are not folded in text output
- schema hint counts are emitted as one dense line
- long schema summaries can make a single response/body line hard to read
- README has no compact package-level tool overview before per-tool detail
- calibration harness captures excerpts, but does not measure summary density or repeated output patterns

## Goals

- make default README and inspect output scan-friendly
- keep full data available through existing JSON outputs and generated artifacts
- prioritize safety, auth, server, required input, and response caveats before metadata richness
- fold repeated diagnostics and repeated response/schema notes
- bound line length and per-tool detail volume
- preserve deterministic offline generation
- avoid hiding important risks
- add tests that lock in compact summaries without overfitting exact prose
- extend calibration evidence enough to track summary density regressions

## Non-Goals

Do not implement:

- parser behavior changes
- new OpenAPI schema semantics
- runtime request or response validation
- LLM-based summarization
- generated SDK types
- UI/browser report rendering
- provider execution
- hosted diagnostics service
- workflow runtime
- marketplace/provider onboarding
- vault, billing, public CRUD, production gateway permission source, or automatic propagation

## Noise Taxonomy

### Repeated Diagnostic Noise

Examples:

- `weak_tool_description` repeated once per operation
- `success_response_without_schema` repeated once per operation
- repeated metadata findings for response schemas or keyword visibility

Default text output should group these by finding id and show count plus one representative recommendation. Full diagnostics JSON remains unchanged.

### Dense Aggregate Noise

Examples:

- schema hint counts with many keys
- response categories plus schema hints plus top tags all emitted as long lines

Default output should show the highest-signal keys first, then `+N more` when the list exceeds a small budget.

### Long Shape Noise

Examples:

- response object summaries with many properties
- request body summaries that combine keyword markers, nullable markers, read/write markers, and object fields

Default output should preserve a compact preview and point to full JSON or a verbose mode for complete detail.

### Repeated Tool-Detail Noise

Examples:

- many tools with the same response caveat
- many tools with no required params and no response schema

Default output should show representative details for each visible tool and aggregate repeated package-level caveats.

## Output Model

Introduce a small rendering profile:

```text
api2agent.summary_profile.v0
```

The profile is for human-facing text only. It should not change `capability.json`, `diagnostics.json`, runner behavior, generated MCP schemas, or parser output.

Suggested helper shape:

```text
summarize_package_for_text(capability_json, diagnostics, profile) -> SummaryView
format_summary_view(view, target="inspect" | "readme") -> list[str]
```

This can start as local helpers in `api2agent.cli` and `api2agent.generators.readme`, then move to a shared module if duplication becomes real.

## Rendering Rules

### Risk First

Default output order:

1. package identity and execution basics
2. diagnostics status/score
3. blocking/action-required caveats
4. auth/server/runtime targeting notes
5. tool count and safety distribution
6. schema/response metadata summary
7. compact tool list

### Bounded Aggregate Lists

For schema hints, top tags, path prefixes, response categories, and repeated findings:

- show at most 5 keys by default
- sort by signal priority, then count, then name
- append `+N more` when omitted
- keep full values in JSON output

### Bounded Tool Details

For each visible tool in default inspect output:

- keep the one-line method/path/safety/required summary
- show at most 3 detail lines
- prefer required path/query/header params and required request body
- show response category/schema preview only when useful
- fold excess responses as `responses: 2 shown, 4 total`
- preserve `--all` for tool count expansion

Implementation can add a `--verbose` or `--detail full` option to print the older full detail format, but v0 should keep `--json` as the compatibility escape hatch regardless.

### README Structure

README should gain a package-level compact overview before detailed tool notes:

```text
## Package Overview

- Tools: 5
- Safety: read=5
- Diagnostics: warn score=62
- Key caveats: success_response_without_schema(5), weak_tool_description(5)
```

Tool detail should remain present, but repeated response/schema caveats should be grouped at package level when possible.

### Diagnostics Text Formatting

`api2agent diagnose` text output should group repeated finding ids:

```text
- [warning] success_response_without_schema x5: Success response has no documented schema.
  recommendation: Add a success response schema so generated docs can show Agents what a successful call returns.
```

JSON output remains one finding per occurrence.

## Summary Budgets

Suggested v0 budgets:

| Surface | Budget |
| --- | --- |
| inspect header before tools | 10 lines |
| aggregate list keys | 5 |
| visible tools default | existing `--limit` |
| per-tool detail lines | 3 |
| response summaries per tool | 2 |
| README package overview caveats | 5 |
| README per-tool response summaries | 2 |
| schema summary preview length | reuse existing schema summarizer bounds, add final line clipping only if needed |

These are defaults, not public protocol guarantees.

## Calibration Harness Effects

Extend the local calibration artifact with summary-density metrics:

```text
inspect_line_count
sample_tool_detail_line_count
max_inspect_line_chars
readme_tool_section_lines
repeated_finding_groups
```

Status classification should remain conservative in v0. Add recommendations when:

- inspect excerpt has very long lines
- sample tool details exceed the default detail budget
- README size grows unexpectedly
- repeated finding groups dominate diagnostics

## Test Plan

Add or update tests for:

- inspect output folds long schema hint lists
- inspect output caps per-tool response details while preserving required inputs
- inspect has a verbose/full escape hatch or JSON compatibility path
- README includes package overview before tool detail
- README groups repeated caveats
- diagnostics text groups repeated finding ids
- calibration harness captures summary-density metrics
- large package truncation behavior still works
- schema/auth/server/response/discriminator/keyword fixtures still expose high-signal caveats

Prefer assertions on stable markers and counts over exact full paragraphs.

## Dogfood Plan

Run:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Expected after implementation:

- no calibration case should fail solely from summary rendering changes
- `schema_rich_keywords` inspect excerpt should avoid very long schema hint lines
- repeated diagnostics in `auth_rich_security` should group clearly in text output
- `large_rest_synthetic` should still warn for `tool_count > 50`
- `write_heavy_unsafe` should still warn for write/delete-only behavior

## Compatibility Strategy

Compatibility is preserved by keeping:

- raw `capability.json`
- raw `diagnostics.json`
- `api2agent inspect --json`
- `api2agent diagnose --json`
- generated runner behavior
- generated MCP tool schemas
- existing diagnostics contract fields

Text output is allowed to become more compact because it is human-facing, but tests should protect important labels so scripts that read broad markers do not break unnecessarily.

## Acceptance Criteria

- summary noise reduction design is implemented without changing raw package contracts
- default inspect output is shorter and still exposes safety/auth/server/schema/response risks
- default diagnostics text groups repeated finding ids
- README has a compact package overview
- repeated response/schema caveats are folded or grouped
- JSON outputs remain full-fidelity
- calibration artifact includes summary-density metrics
- targeted and full test suites pass
- no production runtime, provider execution, hosted service, workflow, marketplace, vault, billing, public CRUD, gateway permission source, or automatic propagation is added

## Next Recommended Task

```text
Agent Capability Compiler OpenAPI Summary Noise Reduction Implementation v0
```
