# Agent Capability Compiler Final Re-entry Closeout + Consolidation Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler re-entry phase 可以关闭。

按当前 API-first re-entry scope 计算，compiler 已足够完整，可以暂停在：

```text
100%
```

这不表示 compiler 没有未来 backlog，而是表示 re-entry goal 已满足：API2Agent 现在已经拥有更强的路径，把 OpenAPI/curl inputs 变成 Agent-ready、reviewable、deterministic 的 generated capability packages，并带有 diagnostics、examples、summaries、calibration evidence，以及进入默认 evidence loop 的 cached real public spec。

推荐下一项项目任务：

```text
Go Control Plane Hosted Admin Gateway Permission Source Design v0
```

这是 compiler re-entry 之前被暂停的 hosted-readiness task。Compiler 工作现在不再阻塞回到这条线。

## Re-entry Goal Review

Re-entry goal 是在不改变 API2Agent 产品边界的前提下强化 Agent capability compiler。

已遵守约束：

- API-first
- no workflow engine
- no hosted runtime dependency
- no marketplace/provider onboarding
- no vault
- no billing
- no public Control Plane CRUD
- compiler re-entry 期间不做 production gateway permission source work
- no automatic snapshot publish/reload

这些约束都保持住了。

## Completed Slices

### Compiler Expansion Design

选择 deterministic quality diagnostics 作为第一项 expansion slice。

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_EXPANSION_DESIGN.md`

### Quality Diagnostics

实现 deterministic package diagnostics、`diagnostics.json`、`api2agent diagnose`、README/inspect summaries 和 regression coverage。

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_IMPLEMENTATION_REPORT.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_QUALITY_DIAGNOSTICS_CLOSEOUT_PHASE_REVIEW.md`

### OpenAPI Real-World Hardening Chain

完成 OpenAPI hardening：

- examples/defaults propagation
- security requirement combinations
- server handling
- schema shaping
- discriminator handling
- response shape documentation
- bounded JSON Schema keyword coverage

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_EXAMPLES_DEFAULTS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SERVER_HANDLING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SCHEMA_SHAPING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_DISCRIMINATOR_HANDLING_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_RESPONSE_SHAPE_DOCUMENTATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_JSON_SCHEMA_KEYWORD_COVERAGE_CLOSEOUT_PHASE_REVIEW.md`

### Calibration And Evidence Loop

实现并校准本地 offline calibration harness：

- real-spec calibration harness
- diagnostics score calibration
- summary noise reduction
- generic example reduction
- cached real-spec corpus expansion

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_SPEC_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_DIAGNOSTICS_SCORE_CALIBRATION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SUMMARY_NOISE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_GENERIC_EXAMPLE_REDUCTION_CLOSEOUT_PHASE_REVIEW.md`
- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_CLOSEOUT_PHASE_REVIEW.md`

## Current Evidence

Latest full test suite：

```text
python -m pytest -q
221 passed
```

Latest calibration dogfood：

```text
OpenAPI real-spec calibration: 5 pass, 2 warn, 0 fail, 1 skipped
```

Default calibration corpus 现在包含：

- small reference fixture
- schema-rich fixture
- auth-rich fixture
- server-rich fixture
- write-heavy fixture
- synthetic large REST case
- committed cached Petstore real public spec excerpt
- optional user-provided cached real spec slot

两个 warning cases 被接受：

- `write_heavy_unsafe`：有意 write/delete-only，score 56
- `large_rest_synthetic`：有意超过 50 tools

Cached real public spec case 通过：

```text
cached_petstore_expanded: pass tools=4 score=82
generic_example_count=0
```

## What Improved

Compiler 现在提供：

- deterministic quality diagnostics
- compact human-readable quality summaries
- full-fidelity JSON diagnostics and inspect output
- source examples/defaults/enums/consts propagation
- name-aware deterministic examples
- server metadata and override guidance
- security combination metadata and runner handling for supported auth
- direction-aware schema shaping
- discriminator-aware summaries and examples
- response shape documentation
- bounded JSON Schema keyword coverage
- calibrated diagnostics scoring
- summary-density metrics
- generic example metrics
- cached real-spec source metadata and checksum validation
- offline calibration evidence

## Residual Risks

### Corpus Breadth

Corpus 现在包含一个 cached real public spec，但还不是 broad public API benchmark。未来应在有具体问题时再增加更多 cached specs。

### Runtime Validation

Compiler 会 document and shape schemas，但 generated runners 仍不做 full runtime schema validation。这是 re-entry 的有意 non-goal。

### OAuth And Complex Auth

OAuth/OpenID 在没有 supported credential injection mode 时仍是 metadata-oriented。完整 OAuth product semantics 属于 compiler re-entry 之外。

### Large Public Specs

Large specs 现在可测量且会明确 warning，但产品仍期望在 Agent 使用前 filtering。这符合当前 Agent usability boundary。

### Generated Examples Are Advisory

Examples 现在 deterministic 且更安全，但不是 provider-valid records。它们是 first-call aids，不是 data discovery。

### Hosted Platform Work Is Still Deferred

Compiler readiness 不解决 hosted permission issuance、public auth、production gateway deployment、tenant partitioning 或 hosted operational controls。这些正是下一条 lane。

## Closeout Judgment

Agent Capability Compiler 可以暂停。

项目不应默认继续增加 compiler slices。未来 compiler work 应由真实用户证据、新 real-spec calibration cases 或 hosted Control Plane integration needs 触发。

下一步最高价值动作是回到 hosted-readiness backlog 中此前暂停的 permission-source design。

## 推荐下一项任务

```text
Go Control Plane Hosted Admin Gateway Permission Source Design v0
```

范围应保持窄：

- permission source contract
- trusted gateway permission issuance assumptions
- principal/project/organization mapping
- endpoint permission lookup semantics
- audit/idempotency evidence
- fail-closed behavior
- local harness dogfood expectations

仍不要启动 marketplace、billing、vault、public CRUD、automatic propagation 或 workflow runtime work。
