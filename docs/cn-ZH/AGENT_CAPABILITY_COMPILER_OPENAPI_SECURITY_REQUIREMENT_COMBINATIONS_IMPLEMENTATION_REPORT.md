# Agent Capability Compiler OpenAPI Security Requirement Combinations Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

Agent capability compiler 已实现 OpenAPI security requirement combinations。

Generated packages 现在会把 OpenAPI OR/AND security requirement structure 作为 additive metadata 保留下来，同时继续保留已有 `auth` 字段作为 primary executable compatibility surface。

本实现支持：

- document-level auth inheritance
- operation-level public override with `security: []`
- OR auth alternatives preserved in metadata
- AND auth requirements preserved and executable when every scheme is supported
- bearer auth
- header API key auth
- query API key auth
- cookie API key auth
- OAuth/OpenID metadata-only preservation
- README、`auth.env.example`、inspect、proxy intent、runner 和 diagnostics updates

本 slice 未增加 OAuth browser flow、token refresh、credential vault、workflow runtime、marketplace/provider onboarding、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## Files

Implementation：

- `api2agent/ir/models.py`
- `api2agent/parsers/openapi.py`
- `api2agent/parsers/curl.py`
- `api2agent/generators/runner.py`
- `api2agent/generators/package.py`
- `api2agent/generators/readme.py`
- `api2agent/diagnostics.py`
- `api2agent/cli.py`

Tests and fixtures：

- `tests/fixtures/openapi/security_combinations.yaml`
- `tests/test_openapi_parser.py`
- `tests/test_runner_generation.py`
- `tests/test_generators.py`
- `tests/test_diagnostics.py`

## Contract

IR additions 是 additive：

- `AuthConfig.location`
- `AuthConfig.name`
- `AuthConfig.scheme_name`
- `AuthConfig.scopes`
- `AuthConfig.source`
- `AuthConfig.unsupported_reason`
- `AuthConfig.credentials`
- `SecurityAlternative`
- `SecurityRequirements`
- `Capability.security_requirements`
- `Tool.security_requirements`

已有 generated package consumers 可以继续读取：

```text
Capability.auth
Tool.auth
```

新 consumers 可以 inspect：

```text
security_requirements.alternatives
```

每个 alternative 表示一个 OpenAPI OR branch。每个 alternative 的 schemes 表示该 branch 的 AND group。空 alternatives list 表示 `security: []`。

## Parser Behavior

Supported executable schemes：

- bearer HTTP auth -> `Authorization: Bearer <token>`
- header API key -> configured header
- query API key -> configured query parameter
- cookie API key -> `Cookie: name=<token>`

Metadata-only schemes：

- OAuth2
- OpenID Connect
- unsupported or missing referenced schemes

Primary auth selection 是 deterministic：

1. operation security 缺失时继承 parent
2. `security: []` 选择 `none`
3. anonymous `{}` alternative 选择 `none`
4. 按 source order 选择第一个 fully supported alternative
5. 当每个 scheme 都 supported 时选择 combined alternatives
6. 否则选择 `unknown` 并保留 unsupported metadata

## Generated Runner Behavior

Direct runner execution 现在支持：

- bearer header injection
- header API key injection
- query API key injection
- cookie API key injection
- supported schemes 的 combined AND injection
- 对 combined auth 一次性报告所有 missing env vars
- 对 selected unsupported metadata-only auth 返回 `unsupported_auth`

Proxy mode 现在会在存在 auth credential intent 时，除了 legacy `credential` 字段，也输出 additive `credentials`。

## Generated Artifact Effects

`auth.env.example` 现在会包含 combined credentials 需要的 env vars，并去重。

README auth labels 现在包含 location/name details：

```text
auth: api_key via query:api_key env=SECURITY_COMBINATIONS_API_API_KEY
auth: api_key via cookie:session env=SECURITY_COMBINATIONS_API_API_KEY
auth: combined api_key via header:X-API-Key env=SECURITY_COMBINATIONS_API_API_KEY + api_key via query:api_key env=SECURITY_COMBINATIONS_API_API_KEY
```

`api2agent inspect` 保持旧 bearer display，同时对新 auth shapes 增加 location-aware formatting。

Diagnostics 现在报告：

- `auth_alternatives_present`
- `combined_auth_required`
- `query_api_key_auth`
- `cookie_api_key_auth`
- `metadata_only_oauth`
- `unsupported_auth_scheme`

## Dogfood Evidence

已生成 package：

```text
python -m api2agent.cli generate tests\fixtures\openapi\security_combinations.yaml --output tmp\openapi-security-combinations --force
```

观察到：

```text
Generated capability package: tmp\openapi-security-combinations
Diagnostics: warn score=30 errors=0 warnings=6 info=9
```

Loopback direct runner dogfood 已通过：

```text
api2agent test tmp\openapi-security-combinations --tool get_query_auth --params '{}'
api2agent test tmp\openapi-security-combinations --tool get_cookie_auth --params '{}'
api2agent test tmp\openapi-security-combinations --tool get_combined_auth --params '{}'
```

观察到：

```text
/query?api_key=combo-secret
Cookie: session=combo-secret
/combined?api_key=combo-secret with X-API-Key: combo-secret
```

## Compatibility

Compatibility 已保留：

- 没有 `security_requirements` 的旧 packages 仍然 validate
- 已有 bearer/header API key auth behavior 保持 compatible
- 现有 `credential` proxy payload field 仍然存在
- query/cookie/combined auth 是 additive
- OAuth/OpenID 是 metadata-only，不触发新的 OAuth runtime behavior

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

## 推荐下一项任务

```text
Agent Capability Compiler OpenAPI Security Requirement Combinations Closeout + Phase Review v0
```

Closeout 应判断这个 auth hardening slice 是否可以关闭，并决定下一项 OpenAPI hardening target 进入 server handling、schema shaping，还是 filtering diagnostics。
