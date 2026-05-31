# Agent Capability Compiler OpenAPI Discriminator Handling Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent capability compiler 已实现 OpenAPI discriminator handling。

Generated packages 现在会保留 raw discriminator metadata，同时让 discriminator-aware polymorphic schemas 在 README、inspect、generated examples、OpenAI tool schemas 和 diagnostics 中更清楚。

本实现支持：

- 从 raw schema dictionaries 提取 discriminator
- discriminator-aware `oneOf` / `anyOf` summaries
- 在 bounded polymorphic summaries 中显示 mapping keys
- 从 discriminator mapping deterministic 选择 request example branch
- 在 generated request examples 中设置 discriminator property
- polymorphic branches 内的 request-direction readOnly filtering
- generated request body examples 和 tool schemas 中保留 writeOnly
- inspect schema hints 中显示 discriminator counts
- diagnostics for discriminator presence、mappings、missing `propertyName`、discriminator without polymorphism、unresolved mappings 和 untagged branches

本 slice 未增加 full JSON Schema validator、OpenAPI 3.1 dialect engine、runtime branch validation、LLM branch selection、SDK type generation、UI form rendering、workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## Files

Implementation：

- `api2agent/schema_shaping.py`
- `api2agent/generators/examples.py`
- `api2agent/diagnostics.py`

已有 generated artifact paths 复用 shared schema shaping helpers：

- `api2agent/generators/readme.py`
- `api2agent/generators/tools.py`
- `api2agent/cli.py`

Tests and fixtures：

- `tests/fixtures/openapi/discriminator.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`
- `tests/test_cli.py`

## Contract

没有新增 required IR fields。

现有 raw schema fields 仍然是 compatibility source of truth：

```text
Parameter.schema_
RequestBody.schema_
Response.schema_
```

Discriminator facts 从 raw schemas 派生：

```text
discriminator.propertyName
discriminator.mapping
oneOf / anyOf branches
branch title / tag property values
```

旧 generated `capability.json` files 仍然 valid。

## Generated Artifact Effects

README 和 inspect 现在显示 discriminator-aware schema summaries：

```text
body: oneOf[discriminator=method: card=>CardPayment | bank_transfer=>BankTransfer | cash=>CashPayment] required
```

Generated manual write examples 现在会选择第一个 discriminator mapping，并设置 discriminator property：

```text
{'body': {'method': 'card', 'card_number': 'example', 'token': 'example'}}
```

Generated OpenAI tools schemas 会保留 discriminator metadata 和 request-direction shaping。在 discriminator fixture 中，card branch 的 `readOnly` `id` field 被排除，`writeOnly` `token` 被保留。

`api2agent inspect` 现在包含 discriminator hints：

```text
Schema hints: discriminator_mappings=3, discriminators=3, polymorphic=2, read_only=2, write_only=2
```

## Diagnostics

新增 diagnostics：

- `discriminator_present`
- `discriminator_mapping_present`
- `discriminator_missing_property`
- `discriminator_without_polymorphism`
- `discriminator_mapping_unresolved`
- `discriminator_branch_without_tag`

这些 findings 是 deterministic，属于 advisory/warning level。它们不做 runtime branch payload validation。

## Dogfood Evidence

已生成 package：

```text
python -m api2agent.cli generate tests\fixtures\openapi\discriminator.yaml --output tmp\openapi-discriminator-handling --force
```

观察到：

```text
Generated capability package: tmp\openapi-discriminator-handling
Diagnostics: warn score=10 errors=0 warnings=8 info=12
```

`inspect` 显示：

```text
Schema hints: discriminator_mappings=3, discriminators=3, polymorphic=2, read_only=2, write_only=2
body: oneOf[discriminator=method: card=>CardPayment | bank_transfer=>BankTransfer | cash=>CashPayment] required
```

`diagnose` 显示新增 discriminator findings：

```text
discriminator_present
discriminator_mapping_present
discriminator_mapping_unresolved
discriminator_branch_without_tag
discriminator_missing_property
discriminator_without_polymorphism
```

Generated manual write example 包含 selected discriminator value：

```text
{'body': {'method': 'card', 'card_number': 'example', 'token': 'example'}}
```

## Compatibility

Compatibility 已保留：

- raw discriminator dictionaries remain in generated schemas
- existing schema shaping behavior remains compatible
- request-direction readOnly/writeOnly handling is preserved inside selected branches
- OpenAI tools schemas are still generated from shaped request schemas
- generated examples still prefer explicit examples/defaults/enums before discriminator fallback
- generated runner behavior is unchanged
- old capability JSON without discriminator metadata remains valid

## Validation

已通过：

```text
python -m py_compile api2agent\schema_shaping.py api2agent\generators\examples.py api2agent\diagnostics.py api2agent\cli.py
```

已通过：

```text
pytest tests\test_openapi_parser.py tests\test_generators.py tests\test_diagnostics.py tests\test_cli.py
```

结果：

```text
79 passed
```

已通过：

```text
pytest
```

结果：

```text
197 passed
```

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Discriminator Handling Closeout + Phase Review v0
```

Closeout 应判断这个 discriminator handling slice 是否可以关闭，并决定下一项 OpenAPI hardening target 是 richer response documentation、deeper JSON Schema keyword coverage，还是另一个 real-spec friction point。
