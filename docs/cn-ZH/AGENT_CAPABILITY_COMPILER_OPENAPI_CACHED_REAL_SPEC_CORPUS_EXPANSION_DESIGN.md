# Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 Agent Capability Compiler implementation slice 应是：

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Implementation v0
```

这一 slice 应为 OpenAPI calibration harness 增加一个小型、已提交、offline 的 cached real-spec corpus。目标是让 compiler 在 public、non-fixture OpenAPI shapes 上获得更广信心，同时保持 calibration deterministic、reviewable、legal-safe。

Implementation 不应依赖 network access，不应执行 providers，也不应新增 hosted runtime behavior、public CRUD、workflow execution、marketplace/provider onboarding、vault、billing、production gateway permission source 或 automatic propagation。

## 为什么现在做

Compiler 已关闭核心 OpenAPI hardening chain：

- diagnostics and package quality visibility
- examples/defaults propagation
- security requirement combinations
- server handling
- schema shaping
- discriminator handling
- response shape documentation
- bounded JSON Schema keyword coverage
- real-spec calibration harness
- diagnostics score calibration
- summary noise reduction
- generic example reduction

默认 calibration run 现在报告：

```text
OpenAPI real-spec calibration: 4 pass, 2 warn, 0 fail, 1 skipped
```

默认 generated cases 也报告：

```text
generic_example_count = 0
generic_first_call_params = []
```

剩余 compiler 风险是 confidence breadth。当前 corpus 稳定，但主要还是 local fixtures 加 synthetic large spec。Cached real public spec 可以暴露 handcrafted fixtures 可能遗漏的真实 operation naming、tag layouts、parameter conventions、response shapes、server metadata 和 auth combinations。

## Goals

- 增加一个或多个 cached real public OpenAPI specs 到 calibration
- 默认保持 harness offline and deterministic
- 保留清晰 source attribution 和 license/cache review record
- 避免提交 secrets、live credentials、user data 或 generated provider outputs
- 保持 checked-in fixtures 小到可 review
- 使用现有 calibration artifact contract 测量 cached case
- 暴露 real-spec behavior 是否改变 diagnostics score、summary density、generic examples、package size 或 filter guidance
- 保持 compiler API-first and local

## Non-Goals

不实现：

- normal tests 或 calibration 中的 network fetches
- real provider execution
- runtime request/response validation
- LLM-based schema interpretation
- broad OpenAPI corpus crawling
- automatic upstream refresh
- hosted service behavior
- provider marketplace onboarding
- credential vault writes
- billing or settlement
- public Control Plane CRUD
- production gateway permission source
- workflow runtime
- automatic snapshot publish/reload

## Corpus Policy

### Source Criteria

每个 cached real spec 必须满足：

- publicly available source
- license 或 explicit terms 允许 redistribution 或 repository inclusion
- 不包含 embedded secrets、tokens、user identifiers、private hostnames 或 live credentials
- 足够稳定，committed cache 有意义
- API-first HTTP/OpenAPI surface
- 至少覆盖一个 fixtures 尚未充分覆盖的 real-world dimension
- optional deterministic reduction 后大小合理

优先 source types：

- 带 permissive licenses 的 official public API OpenAPI documents
- 有明确 redistribution terms 的 public demo/reference API specs
- full specs 过大时，可使用 permissively licensed specs 的 small curated excerpts

避免：

- licensing ambiguous 的 specs
- private services 生成的 specs
- 包含真实 customer examples 的 specs
- 需要 auth 或 network calls 才能 inspect 的 specs
- 巨大但不增加新 compiler signal 的 specs

### Cache Metadata

每个 cached spec 应在 manifest entry 或 sidecar file 中有相邻 metadata：

```text
case_id
purpose
source_name
source_url
source_license
source_retrieved_at
cache_policy
reduction_policy
redaction_policy
sha256
notes
```

`source_retrieved_at` 只是 informational。Calibration input 是 cached file contents，而不是 live upstream URL。

### Redaction Policy

提交 cached spec 前：

- 删除或替换 secrets、bearer tokens、API keys、session ids 和 passwords
- 删除真实 email addresses，除非是 `user@example.com` 这类官方示例地址
- 删除 private hostnames、internal IPs 和 tenant/customer identifiers
- 在安全前提下保留 schema structure、operation ids、tags、parameters、examples 和 response metadata
- 在 metadata 中记录每个 intentional reduction 或 redaction

Redaction 必须 deterministic and reviewable。不把 LLM 或 opaque script 作为唯一 redaction evidence。

### Size Policy

默认目标：

```text
cached spec <= 500 KiB
generated capability.json <= 1 MiB
tool_count <= 100 unless the case is explicitly large-surface
```

如果完整 public spec 过大，优先做 deterministic reduced excerpt，并保留：

- original OpenAPI version
- license 允许时保留 original info title/version
- selected tags/paths/operations
- selected operations 需要的 components
- calibration 所需的 security/server/schema features

Reduction 应记录为 cache transformation，而不是隐藏成 original upstream copy。

## Artifact Location

推荐 layout：

```text
.dogfood/openapi-real-spec-calibration/inputs/
  cached-real/
    <case_id>.openapi.json
    <case_id>.metadata.json
```

现有 optional path 可以保持兼容：

```text
.dogfood/openapi-real-spec-calibration/inputs/cached_real.openapi.json
```

但 implementation 应优先使用 `cached-real/` 目录，以支持 multiple cases 和更清晰 attribution。

## Manifest Changes

用 named cached cases 替换或补充单一的 `optional_cached_real_spec`：

```text
cached_<source>_<purpose>
```

每个 case 应定义：

```text
case_id
purpose
source_path
metadata_path
filters
expected_status
optional
notes
```

推荐 purposes：

- `cached_real_small`
- `cached_real_auth`
- `cached_real_schema`
- `cached_real_large`

v0 中，如果一个 required cached real case 能增加 meaningful signal，就已经足够。其他 cases 可以继续 optional。

## Calibration Metrics

现有 artifact fields 保持兼容。每个 case 增加 cached-spec metadata fields：

```text
source_name
source_url
source_license
source_retrieved_at
cache_sha256
cache_policy
reduction_policy
redaction_policy
```

Harness 继续报告：

- `tool_count`
- `read_tools`、`write_tools`、`delete_tools`
- `required_parameter_count`
- `schema_hint_counts`
- `response_category_counts`
- `diagnostics_status`
- `diagnostics_score`
- `diagnostics_summary`
- `finding_counts`
- `repeated_finding_groups`
- `readme_bytes`
- `readme_tool_section_lines`
- `capability_bytes`
- `generation_ms`
- `inspect_line_count`
- `max_inspect_line_chars`
- `first_call_params`
- `generic_example_count`
- `generic_first_call_params`

## Status And Thresholds

Cached real cases 仍保持 report-oriented，但 v0 应分类明确 regressions。

推荐 fail conditions：

- required case 的 cached source file missing
- required cached case 的 metadata file missing or invalid
- metadata checksum 与 source file 不匹配
- generation fails
- generated package 缺少 `capability.json` 或 `diagnostics.json`
- source path resolves outside the calibration inputs directory
- redaction metadata 缺失

推荐 warn conditions：

- `tool_count > 100`
- `diagnostics_score < 60`
- `generic_example_count > 0`
- `max_inspect_line_chars > 180`
- `readme_bytes > 200_000`
- `generation_ms > 30_000`
- write/delete tools exist but no read tools exist
- source license metadata present 但标记为 `review_required`

推荐 pass conditions：

- required cached metadata validates
- package generation succeeds
- diagnostics are readable
- applicable 时 first-call params 被捕获
- no generic first-call params remain
- warnings 如果存在，是 expected and documented

## Implementation Plan

1. Add metadata model/helpers for cached calibration sources.
2. Add checksum verification for cached source files.
3. Add path containment checks under `.dogfood/openapi-real-spec-calibration/inputs`.
4. Extend `CalibrationCase` with optional `metadata_path`.
5. Add at least one required cached real case or a required curated public-spec excerpt with metadata.
6. Keep optional user-provided cached spec compatibility.
7. Extend `result.json` with safe source metadata.
8. Add regression tests for metadata validation、checksum mismatch、path containment、optional skips 和 status classification。
9. Run calibration dogfood and capture the new cached case in the implementation report.

## Test Plan

增加或更新 tests：

- valid cached metadata loads and appears in result artifact
- checksum mismatch fails the case
- missing metadata fails required cached cases
- optional cached cases still skip cleanly
- source paths cannot escape the calibration inputs directory
- redaction/license/cache policy fields are required for committed cached cases
- cached real case participates in summary counts
- generic example metrics remain present
- existing default fixture cases remain stable

## Dogfood Plan

运行：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Implementation 后预期：

- 至少一个 cached real case generated, not skipped
- `optional_cached_real_spec` 要么被 named cached cases 替换，要么保持 backward-compatible optional slot
- result artifact 包含 source metadata and checksum
- default summary 保持 `0 fail`
- generic example counts 保持 zero，或产生 explicit recommendations
- large/noisy real cases 产生 warnings，而不是 silent failures

## Acceptance Criteria

- cached real-spec corpus policy 已实现
- 至少一个 committed cached real/public-spec case 有 source metadata
- normal calibration 仍然 offline and deterministic
- required cached cases 会校验 checksum、metadata 和 path containment
- optional cached cases 缺失时仍 cleanly skipped
- result artifact 包含 safe source/cache metadata
- calibration recommendations 会包含 cached real-spec issues when present
- targeted and full test suites pass
- 未新增 LLM generation、provider execution、network-dependent tests、hosted service、workflow、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Implementation v0
```
