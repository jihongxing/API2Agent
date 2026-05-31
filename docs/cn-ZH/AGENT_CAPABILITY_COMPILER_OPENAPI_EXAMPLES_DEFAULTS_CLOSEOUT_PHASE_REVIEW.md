# Agent Capability Compiler OpenAPI Examples + Defaults Propagation Closeout + Phase Review v0

日期：2026-06-01

状态：complete

## 决策

Agent Capability Compiler OpenAPI Examples + Defaults Propagation implementation slice 可以关闭。

Compiler 现在可以把 OpenAPI source sample data 从 parsing 传递到 generated package artifacts，让首次本地 Agent/API 调用不再那么 generic，并且更可能直接可用。

推荐下一项任务：

```text
Agent Capability Compiler OpenAPI Security Requirement Combinations Design v0
```

下一项设计应处理真实 OpenAPI auth semantics，尤其是 OR vs AND security requirements、query/cookie API keys 和 per-tool auth summaries。它必须保持 API-first，不得增加 workflow execution、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## 现在已完成

### Design

已完成：

- 选择 examples/defaults propagation 作为第一项 OpenAPI hardening implementation slice
- 指定 parameters 和 request bodies 需要保留的 source fields
- 指定 additive IR model changes
- 定义 deterministic example selection order
- 定义 README/test artifact effects
- 命名 tests、dogfood 和 non-goals

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_REAL_WORLD_HARDENING_DESIGN.md`

### Implementation

已完成：

- additive `Parameter.example`
- additive `Parameter.examples`
- additive `RequestBody.example`
- additive `RequestBody.examples`
- parser preservation for OpenAPI parameter `example` and `examples`
- parser preservation for request body media `example` and `examples`
- shared example selection helper，覆盖 parameters、request bodies、schemas、defaults、examples、enums 和 type fallbacks
- README parameter/body details 显示 source examples
- README first-call params 使用 source examples/defaults/enums
- generated read smoke tests 使用 source examples
- generated manual write tests 使用 source body examples，同时保留 explicit write opt-in
- regression fixture 覆盖 parameter examples、examples maps、defaults、body examples、property examples/defaults 和 enum fallback

参考：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_EXAMPLES_DEFAULTS_IMPLEMENTATION_REPORT.md`

## Acceptance Criteria Review

| Criterion | Status |
| --- | --- |
| parameter `example` is preserved | passed |
| parameter `examples` are normalized and preserved | passed |
| request body media `example` is preserved | passed |
| request body media `examples` are normalized and preserved | passed |
| schema defaults/examples/enums feed generated params | passed |
| README first-call commands use source examples/defaults | passed |
| README parameter/body details show useful examples | passed |
| generated smoke tests use source examples for required read inputs | passed |
| generated manual write tests use source body examples | passed |
| write/delete execution remains explicitly opt-in | passed |
| curl-derived object fallback behavior is preserved | passed |
| old capability JSON remains compatible | passed |
| 未增加 workflow、marketplace、vault、billing、hosted public CRUD、gateway permission source 或 automatic propagation | passed |

## Validation

已通过：

```text
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\generators\examples.py api2agent\generators\readme.py api2agent\generators\smoke_test.py
```

已通过：

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_runner_generation.py tests\test_diagnostics.py
```

结果：

```text
40 passed
```

已通过：

```text
pytest
```

结果：

```text
179 passed
```

Local generated-runner dogfood 已在 loopback HTTP target 上通过：

- read call 使用 `user_123`、`profile` 和 `trace-123`
- opt-in write call 使用 `sku_123` 和 `quantity: 2`

已通过：

```text
git diff --check
```

## Closeout Judgment

这个 implementation slice 已完成。

Examples/defaults propagation 现在已经成为可靠的 OpenAPI hardening primitive：

- generated package examples 不再那么 generic
- required path/query/header/body inputs 拥有更好的 first-call values
- README guidance 和 generated tests 保持一致
- write safety 仍然 explicit
- IR change 是 additive 且 compatible

这关闭了第一项 OpenAPI hardening implementation slice，并让 compiler 更适合继续处理 auth、server 和 schema complexity。

## Remaining Risks

### Schema Example Coverage Is Still Conservative

当前实现覆盖常见 schema defaults、examples、example arrays、enums 和 object properties。深层 polymorphic schemas、nullable shapes 和 `oneOf` / `anyOf` readability 仍需要后续 schema shaping work。

### Diagnostics Do Not Yet Score Example Quality

现在 source examples 已被保留，diagnostics 可以利用更丰富的 evidence，但这个 slice 没有新增 diagnostics findings 来区分“required input 有可用 source sample”和“required input 仍是 generic fallback”。

### Real Specs May Use Complex Example Objects

OpenAPI examples objects 可能包含 metadata、external references 或 media-specific structures。v0 刻意保持 deterministic and local extraction，只在可用时使用 inline `value`。

### Auth Semantics Are Now The Bigger Onboarding Gap

Examples/defaults 之后，许多真实 OpenAPI specs 仍会因为 security requirement combinations 复杂而难以正确使用。Multiple alternatives、API key locations、cookies 和 OAuth scope metadata 需要先做 dedicated design 再实现。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Security Requirement Combinations Design v0
```

该设计应定义 OpenAPI document/path/operation security requirements 如何映射到 per-tool auth metadata、README guidance、diagnostics evidence 和 generated runner/proxy behavior，同时保持 API-first compiler boundaries。
