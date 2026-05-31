# Agent Capability Compiler OpenAPI Examples + Defaults Propagation Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent capability compiler 的 OpenAPI examples/defaults propagation 已实现。

Generated packages 现在会把 OpenAPI 中可用的 sample data 保留进 IR，并复用到：

- generated README parameter/body details
- generated README first-call commands
- generated read-only smoke tests
- generated manual write tests
- generated `capability.json`

本 slice 未增加 workflow engine、marketplace、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## Files

Implementation：

- `api2agent/ir/models.py`
- `api2agent/parsers/openapi.py`
- `api2agent/generators/examples.py`
- `api2agent/generators/readme.py`
- `api2agent/generators/smoke_test.py`

Tests and fixtures：

- `tests/fixtures/openapi/examples_defaults.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_generators.py`

## Contract

IR model additions 是 backward-compatible additive 字段：

- `Parameter.example`
- `Parameter.examples`
- `RequestBody.example`
- `RequestBody.examples`

已有 generated package readers 继续可用，因为旧 packages 可以没有这些字段，新 packages 仍然序列化为普通 JSON capability data。

## Example Selection

Parameter example selection 是 deterministic：

1. explicit `parameter.example`
2. `parameter.examples` 中第一个 value
3. `schema.default`
4. `schema.example`
5. `schema.examples` 中第一个 value
6. `schema.enum` 中第一个 value
7. existing type fallback

Request body example selection 是 deterministic：

1. media `example`
2. media `examples` 中第一个 value
3. schema `default`
4. schema `example`
5. schema `examples` 中第一个 value
6. 使用 property defaults/examples/enums 为 required properties 构造 object
7. existing type fallback

对于没有 `required` list 的 object bodies，fallback 会保留所有 properties，以兼容旧的 curl-derived README 行为。

## Generated Artifact Effects

README 现在会在 source metadata 存在时显示 useful examples：

```text
path: user_id string required example=user_123
query: include string example=profile
header: X-Trace-Id string default=trace-123 required example=trace-123
body: object {sku:string, quantity:integer default=1, priority:string} required example={'sku': 'sku_123', 'quantity': 2}
```

README first-call commands 现在使用 source values：

```text
api2agent test . --tool get_user_by_example --params '{"user_id": "user_123", "include": "profile", "X-Trace-Id": "trace-123"}'
```

Generated tests 现在会在可用时使用 source examples/defaults，同时保留现有 manual write-test guard。

## Dogfood Evidence

已生成 examples/defaults package：

```text
python -m api2agent.cli generate tests\fixtures\openapi\examples_defaults.yaml --output tmp\openapi-examples-defaults --force
```

观察到：

```text
Generated capability package: tmp\openapi-examples-defaults
Diagnostics: warn score=72 errors=0 warnings=2 info=4
```

`inspect` 显示 3 个 generated tools，required parameters 和 defaults 符合预期。README 和 generated tests 包含：

- `user_123`
- `profile`
- `trace-123`
- `sku_123`
- `quantity: 2`
- `order_123`

Local generated runner dogfood 已通过 local loopback HTTP target：

```text
api2agent test tmp\openapi-examples-defaults --tool get_user_by_example --params '{"user_id":"user_123","include":"profile","X-Trace-Id":"trace-123"}'
```

结果：

```text
{'ok': True, 'status_code': 200, 'body': {'method': 'GET', 'path': '/users/user_123?include=profile', 'trace': 'trace-123', 'body': None}}
```

Manual write path 仍然保持 opt-in，并且也在 local safe target 上通过：

```text
api2agent test tmp\openapi-examples-defaults --tool create_order_with_example --allow-write --params '{"body":{"sku":"sku_123","quantity":2}}'
```

结果：

```text
{'ok': True, 'status_code': 200, 'body': {'method': 'POST', 'path': '/orders', 'trace': None, 'body': {'sku': 'sku_123', 'quantity': 2}}}
```

## Compatibility

实现是 additive：

- old capability JSON 仍然 valid
- curl-derived packages 保持 object-body fallback behavior
- write/delete tests 仍然需要 explicit opt-in
- diagnostics behavior 仍然是 advisory
- generation 和 regression tests 不依赖网络

## Validation

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
python -m py_compile api2agent\ir\models.py api2agent\parsers\openapi.py api2agent\generators\examples.py api2agent\generators\readme.py api2agent\generators\smoke_test.py
```

已通过：

```text
pytest
```

结果：

```text
179 passed
```

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Examples + Defaults Propagation Closeout + Phase Review v0
```

Closeout 应判断第一项 OpenAPI hardening slice 是否可以关闭，并决定下一项 compiler expansion 进入 OpenAPI security requirement combinations、server handling、schema shaping，还是 filtering diagnostics。
