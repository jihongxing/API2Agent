# Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Implementation 报告 v0

日期：2026-06-01

状态：complete

## Summary

OpenAPI cached real-spec corpus expansion v0 已为 Agent Capability Compiler 实现。

Calibration harness 现在包含一个已提交的 offline cached real-spec case，并带有 source metadata、checksum verification、redaction/cache policy evidence、path containment checks 和 result artifact metadata。这让 compiler 在默认 calibration run 中拥有真实 public OpenAPI shape，同时不新增 network dependency、provider execution、hosted runtime behavior 或 non-API scope。

已实现：

- `CalibrationCase` 支持 cached source metadata
- required cached cases 的 metadata validation
- cached source files 的 SHA-256 checksum verification
- `.dogfood/openapi-real-spec-calibration/inputs` 下的 path containment checks
- calibration `result.json` 中的 safe source/cache metadata
- `.dogfood/openapi-real-spec-calibration/inputs/cached-real/` 下的 committed Swagger Petstore expanded excerpt
- valid metadata、checksum mismatch、missing metadata、path containment、optional skips 和 default manifest inclusion 的 regression coverage

未新增 LLM generation、provider execution、network-dependent tests、runtime validation、hosted service、workflow、marketplace、vault、billing、public CRUD、gateway permission source 或 automatic propagation。

## Files

Implementation：

- `scripts/api2agent_openapi_real_spec_calibration.py`

Cached corpus：

- `.dogfood/openapi-real-spec-calibration/inputs/cached-real/petstore_expanded.openapi.json`
- `.dogfood/openapi-real-spec-calibration/inputs/cached-real/petstore_expanded.metadata.json`

Tests：

- `tests/test_openapi_real_spec_calibration.py`

Design reference：

- `docs/cn-ZH/AGENT_CAPABILITY_COMPILER_OPENAPI_CACHED_REAL_SPEC_CORPUS_EXPANSION_DESIGN.md`

## Cached Source

Cached case：

```text
cached_petstore_expanded
```

Source metadata：

```text
source_name = OpenAPI Initiative Swagger Petstore expanded example
source_url = https://github.com/OAI/OpenAPI-Specification/blob/main/examples/v3.0/petstore-expanded.yaml
source_license = Apache-2.0
cache_sha256 = sha256:c41e9e47dabacb0837b78e6414bd46d24c7a78b24acdfd1ea7f80803e050b008
```

Cached file 是 deterministic JSON excerpt，保留 pets paths、server metadata、response schemas、component references、mixed read/write/delete tools 和 `allOf` schema shape。Contact email 和 externalDocs metadata 已省略。Metadata 记录 cache、reduction 和 redaction policies。

## Behavior Changes

Default manifest 现在包含一个 required cached real-spec case：

```text
cached_petstore_expanded
```

对于带 `metadata_path` 的 cases，harness 会校验：

- source path 位于 `.dogfood/openapi-real-spec-calibration/inputs` 下
- metadata path 位于 `.dogfood/openapi-real-spec-calibration/inputs` 下
- metadata file 存在且是 valid JSON
- required metadata fields 都存在
- metadata `case_id` 与 calibration case 匹配
- metadata `sha256` 与 source file bytes 匹配

现有 backward-compatible optional user-provided slot 保留：

```text
optional_cached_real_spec
```

不带 `metadata_path` 的 cases 保持之前行为。

## Dogfood Evidence

运行：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

观察到：

```text
OpenAPI real-spec calibration: 5 pass, 2 warn, 0 fail, 1 skipped
- small_reference_basic: pass tools=1 score=87
- schema_rich_keywords: pass tools=2 score=70
- auth_rich_security: pass tools=5 score=62
- server_rich_choices: pass tools=3 score=62
- write_heavy_unsafe: warn tools=2 score=56 - diagnostics_score < 60; no read tools when write/delete tools exist
- large_rest_synthetic: warn tools=60 score=82 - tool_count > 50
- cached_petstore_expanded: pass tools=4 score=82
- optional_cached_real_spec: skipped tools=0 score=None - optional source_path is not present
```

Cached Petstore case evidence：

```text
tool_count = 4
read_tools = 2
write_tools = 1
delete_tools = 1
diagnostics_score = 82
schema_hint_counts = numeric_constraints=1, schema_keywords=10, string_constraints=10
response_category_counts = default=4, success=4
generic_example_count = 0
generic_first_call_params = []
```

## Validation

已通过：

```text
python -m py_compile scripts\api2agent_openapi_real_spec_calibration.py
```

已通过：

```text
python -m pytest tests\test_openapi_real_spec_calibration.py -q
```

结果：

```text
9 passed
```

Local dogfood 已通过：

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

观察到：

```text
OpenAPI real-spec calibration: 5 pass, 2 warn, 0 fail, 1 skipped
```

## Compatibility

Compatibility 已保持：

- existing fixture calibration cases 保持 unchanged
- optional cached user-provided spec behavior 继续支持
- calibration artifact contract 是 additive
- generated package contracts unchanged
- generated runner behavior unchanged
- diagnostics behavior unchanged

有意 behavior change 是 default calibration corpus 更广，并为 committed real-spec cases 增加 source/cache metadata。

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Cached Real-Spec Corpus Expansion Closeout + Phase Review v0
```

Closeout 应判断一个 required cached case 对 v0 是否足够、additional cached cases 是否应留到 final consolidation 后，以及 Agent Capability Compiler 是否可以进入最终 re-entry closeout。
