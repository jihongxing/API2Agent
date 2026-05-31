# Agent Capability Compiler OpenAPI Security Requirement Combinations Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Security Requirement Combinations implementation slice 可以关闭。

Compiler 现在已经能较好保留真实 OpenAPI specs 中的 auth semantics，包括 public overrides、OR alternatives、AND credential groups、query API keys、cookie API keys 和 OAuth/OpenID metadata。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Server Handling Design v0
```

下一项设计应改进 multiple document/path/operation servers 的 server selection 和 environment/profile hints，同时保留 runtime base URL override compatibility。

## 现在已完成

### Design

已完成：

- documented OpenAPI security OR/AND semantics
- documented current flattening gaps
- defined additive IR metadata for auth schemes and security requirement alternatives
- defined deterministic primary auth selection
- defined bearer/header/query/cookie/OAuth scheme mappings
- defined generated runner、proxy、README、inspect、diagnostics、tests 和 dogfood effects
- preserved API-first non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_DESIGN.md`

### Implementation

已完成：

- additive `AuthConfig` metadata for location、name、scheme name、scopes、source、unsupported reason 和 combined credentials
- additive `SecurityAlternative` / `SecurityRequirements` IR models
- `Capability.security_requirements`
- `Tool.security_requirements`
- OpenAPI parser support for OR/AND security requirements
- query and cookie API key parser support
- OAuth/OpenID metadata-only preservation
- generated runner injection for query、cookie 和 supported combined auth
- generated runner `unsupported_auth` behavior for selected unsupported auth
- proxy payload additive `credentials` alongside legacy `credential`
- README 和 `auth.env.example` auth summaries
- inspect auth formatting compatibility for bearer plus location-aware new auth shapes
- diagnostics for alternatives、combined auth、query/cookie API keys、metadata-only OAuth 和 unsupported schemes
- regression fixture and tests

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_SECURITY_REQUIREMENT_COMBINATIONS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| OpenAPI OR alternatives are preserved in generated metadata | passed |
| OpenAPI AND groups are preserved in generated metadata | passed |
| primary auth selection is deterministic | passed |
| operation-level `security: []` public override works | passed |
| existing bearer/header API key behavior remains compatible | passed |
| query API key direct runner execution works | passed |
| cookie API key direct runner execution works | passed |
| supported combined auth direct runner execution works | passed |
| missing combined auth env vars are reported together | passed |
| OAuth/OpenID is preserved as metadata-only | passed |
| proxy credential intent remains backward compatible | passed |
| diagnostics explain auth alternatives and combined auth | passed |
| README and `auth.env.example` expose new auth shapes | passed |
| old generated package compatibility is preserved | passed |
| 未增加 OAuth flow、vault、workflow、marketplace、billing、hosted public CRUD、gateway permission source 或 automatic propagation | passed |

## Validation

已通过：

```text
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\parsers\curl.py api2agent\generators\package.py api2agent\generators\readme.py api2agent\generators\runner.py api2agent\diagnostics.py api2agent\cli.py
```

已通过：

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_runner_generation.py tests\test_diagnostics.py
```

结果：

```text
46 passed
```

已通过：

```text
pytest
```

结果：

```text
185 passed
```

Loopback dogfood 已通过：

- query API key auth
- cookie API key auth
- combined header + query API key auth

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Compiler 现在处理了一个主要 real-world OpenAPI auth gap，同时没有把 API2Agent 扩展成 hosted credential management 或 OAuth runtime behavior。

这让 generated packages 的 auth correctness 更好，并且仍然为 existing consumers 保留旧的 simple `auth` surface。

## Remaining Risks

### Multi-Credential Proxy Execution Needs Deeper Product Semantics

Generated proxy payloads 现在会输出 additive `credentials`，但 production-grade multi-credential resolution 仍需要 Control Plane 和 credential policy semantics 才适合 hosted usage。

### OAuth Is Metadata-Only

这是刻意选择。OAuth flows、refresh、consent 和 hosted token lifecycle 仍然 out of scope。Generated packages 不应暗示 OAuth automation。

### API Key Env Naming Is Still Coarse

同一个 spec 中多个 API key schemes 可能共享同一个 generated env name。v0 为兼容性接受这一点，但未来实现可能需要在 distinct secrets 场景下提供 per-scheme env naming。

### Real Specs May Combine Auth With Complex Server Layouts

Auth correctness 已改进，但许多真实 specs 同时依赖 multiple servers、staging/prod URLs、regional URLs 和 operation-level server choices。Server handling 是下一个明显 onboarding gap。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Server Handling Design v0
```

该设计应定义 document/path/operation servers、server variables、multiple server choices、environment/profile hints 和 runtime base URL overrides 如何进入 IR、README、diagnostics 和 generated runner behavior。
