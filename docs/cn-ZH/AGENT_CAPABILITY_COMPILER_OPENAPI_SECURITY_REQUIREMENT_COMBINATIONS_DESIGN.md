# Agent Capability Compiler OpenAPI Security Requirement Combinations Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 OpenAPI hardening implementation slice 应为：

```text
Agent Capability Compiler OpenAPI Security Requirement Combinations Implementation v0
```

这个 slice 应保留 OpenAPI security requirement semantics，而不是把它们压扁成第一个识别到的 scheme。

它必须保持 API-first，不得增加 OAuth browser flows、hosted credential vaults、workflow runtime、marketplace/provider onboarding、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## 为什么现在做这个 slice

Examples/defaults propagation 让 generated first calls 更可用。下一个真实 OpenAPI blocker 是 auth correctness。

很多 specs 会使用：

- OR alternatives：`security: [{ bearerAuth: [] }, { apiKeyAuth: [] }]`
- AND requirements：`security: [{ apiKeyHeader: [], apiKeyQuery: [] }]`
- public operation overrides：`security: []`
- API keys in `query` 或 `cookie`
- OAuth/OpenID scopes 作为 descriptive metadata

当前 parser 会从第一个可用 requirement 中选第一个 recognized scheme。这个行为 deterministic，但会丢失 auth 是 optional、alternative、combined 还是 unsupported。

## Current Baseline

已有：

- document-level `security`
- operation-level `security` override
- bearer HTTP auth 映射为 `AuthConfig(type="bearer", header="Authorization")`
- header API key 映射为 `AuthConfig(type="api_key", header=<header name>)`
- public operation override via `security: []`
- generated runner env-backed bearer/header injection
- proxy credential intent for bearer/header API key
- README 和 `auth.env.example` 输出 env names
- diagnostics findings for unknown auth and missing env names
- tools 有 auth overrides 时输出 mixed-auth summary

重要 gaps：

- OR alternatives 会被压扁成一个 selected scheme
- AND requirements with multiple schemes 会被压扁成一个 selected scheme
- query API keys 会被视为 unknown
- cookie API keys 会被视为 unknown
- OAuth/OpenID scopes 不会作为 metadata 保留
- diagnostics 还不能解释 spec 有 optional/alternative/combined auth
- README 不能总结 auth alternatives 或 combined credentials
- generated runner 不能为一个 operation 注入 multiple auth credentials

## OpenAPI Security Semantics

OpenAPI `security` 是 Security Requirement Objects 的数组：

- outer array 是 OR
- 每个 object 内部的 scheme names 是 AND
- empty object `{}` 表示 anonymous access 是一个允许的 alternative
- empty array `[]` 表示该 scope 不需要 auth
- operation-level `security` 覆盖 document-level `security`
- operation-level `security` 缺失时继承 document-level `security`

这个设计应在 generated package metadata 中保留这些 semantics，即使 runner 只能执行其中一部分。

## Goals

- 在 IR 中保留 OR/AND security requirement structure
- 保持已有 single `auth` behavior 对 old consumers 兼容
- 在 deterministic 时支持 header API key、query API key、cookie API key 和 bearer token execution
- 当所有 schemes 都是 env-backed 且 supported 时，支持 generated runner 和 proxy intent 的 combined AND credentials
- OAuth/OpenID scopes 只作为 metadata 保留
- 改进 README、`auth.env.example`、inspect 和 diagnostics auth summaries
- 保持 generation deterministic and offline

## Non-Goals

不实现：

- OAuth authorization-code/device/browser flows
- token refresh
- hosted credential vault writes
- production gateway permission source
- user/project permission issuance
- workflow composition
- marketplace/provider onboarding
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed IR Strategy

保留当前 `Capability.auth` 和 `Tool.auth` 作为 backward-compatible primary executable auth surface。

新增 metadata 来保留完整 OpenAPI security structure：

```text
AuthConfig.location: "header" | "query" | "cookie" | "authorization" | "unknown" | null
AuthConfig.name: original header/query/cookie parameter name, when applicable
AuthConfig.scheme_name: OpenAPI security scheme key
AuthConfig.scopes: list[str]
AuthConfig.source: "openapi" | "curl" | "manual" | null
AuthConfig.unsupported_reason: string | null

SecurityRequirement.alternatives:
  - each alternative is one AND group
  - each group contains one or more AuthConfig-like scheme records
  - an empty group represents anonymous access

Capability.security_requirements
Tool.security_requirements
```

`auth` 继续表示 primary selected execution plan：

- 不需要 auth 时为 `none`
- selected requirement 只有一个 scheme 时为 single supported scheme
- implementation 增加 multi-credential runner support 后，可表示 combined supported requirement
- 只有 unsupported requirements 时为 `unknown`

Generated `capability.json` 保持 additive：旧 packages 不需要 `security_requirements`，旧 consumers 也可以继续读取 `auth`。

## Primary Auth Selection

Primary executable auth selection 必须 deterministic：

1. security 缺失时继承 parent scope
2. security 为 `[]` 时选择 `none`
3. 如果任一 alternative 是 anonymous `{}`，选择 `none`，并在 metadata 中保留其它 alternatives
4. 按 source order 选择第一个 fully supported alternative
5. fully supported alternative 可以包含：
   - bearer HTTP token
   - header API key
   - query API key
   - cookie API key
6. 如果没有 fully supported alternative，则保留所有 alternatives，并选择 `unknown`

这样既保持 behavior predictable，也让过去丢失的 semantics 可见。

## Scheme Mapping

### Bearer

OpenAPI：

```yaml
type: http
scheme: bearer
```

Execution mapping：

- location: `authorization`
- name/header: `Authorization`
- env: `<CAPABILITY>_API_TOKEN`
- injection: `Authorization: Bearer <token>`

### Header API Key

OpenAPI：

```yaml
type: apiKey
in: header
name: X-API-Key
```

Execution mapping：

- location: `header`
- name/header: `X-API-Key`
- env: `<CAPABILITY>_API_KEY`
- injection: `X-API-Key: <token>`

### Query API Key

OpenAPI：

```yaml
type: apiKey
in: query
name: api_key
```

Execution mapping：

- location: `query`
- name: `api_key`
- env: `<CAPABILITY>_API_KEY`
- injection: query parameter `api_key=<token>`

### Cookie API Key

OpenAPI：

```yaml
type: apiKey
in: cookie
name: session
```

Execution mapping：

- location: `cookie`
- name: `session`
- env: `<CAPABILITY>_API_KEY`
- injection: `Cookie: session=<token>`

Cookie support 应保持 conservative，并在 generated README guidance 中明确提示，因为 cookie auth 可能需要 OpenAPI 没描述的 additional cookie attributes。

### OAuth2 / OpenID Connect

Execution mapping：

- 保留 scheme name、type、flows、scopes 和 description 作为 metadata
- 不生成 OAuth flows
- 不声明 direct runner execution support
- diagnostics 应报告 metadata-only OAuth auth

## Generated Runner Behavior

Runner 应支持：

- no auth
- bearer header injection
- header API key injection
- query API key injection
- cookie API key injection
- 当每个 required scheme 都 supported 且有 env name 时，支持 AND groups

对于 OR alternatives，runner 只执行 selected primary alternative。README 和 diagnostics 应让这个 selection 可见。

如果 selected AND group 缺少 env vars，runner 应一次性报告所有 missing auth env names。

如果只存在 unsupported alternatives，runner 应返回 `unsupported_auth`，而不是静默无 auth 调用。

## Proxy Credential Intent

Proxy payloads 应保留现有 single `credential` field 以兼容旧 behavior。

Additive future shape：

```text
credentials: [
  {
    credential_id,
    owner_type,
    owner_id,
    provider_id,
    auth_type,
    injection_mode,
    injection_name,
    source,
    secret_ref
  }
]
```

对于 single-scheme auth，可以在 compatibility window 同时输出 old `credential` 和 new `credentials[0]`。

对于 AND groups，输出包含所有 required supported credentials 的 `credentials`。如果 local proxy 尚未安全支持 multi-credential intent，可以先交付 direct runner support，并把 proxy gap 写入 remaining gaps。

## Generated Artifact Effects

README：

- 总结 package default auth
- 总结 per-tool overrides
- 显示 selected primary alternative
- OR 存在时显示 auth alternatives
- AND 存在时显示 combined credentials
- OAuth/OpenID 显示为 metadata-only

`auth.env.example`：

- 包含 selected executable alternatives 需要的所有 env vars
- 对 metadata-only unsupported schemes 写 comment
- 避免重复 env names

`inspect`：

- 显示 compact auth summary
- 显示 auth 是 optional、alternative、combined 还是 unsupported

Diagnostics：

- `auth_alternatives_present`
- `combined_auth_required`
- `unsupported_auth_scheme`
- `metadata_only_oauth`
- `query_api_key_auth`
- `cookie_api_key_auth`
- `auth_env_missing` should include all missing env vars for a selected combined requirement

## Implementation Plan

1. 增加 additive IR metadata，描述 auth scheme location/name/scheme/scopes 和 security requirement alternatives。
2. 扩展 OpenAPI security scheme extraction，支持 header/query/cookie API keys 和 OAuth/OpenID metadata。
3. 将 document 和 operation security 解析成保留 OR/AND requirement metadata。
4. 继续用 `Capability.auth` / `Tool.auth` 填充 selected primary executable plan。
5. 扩展 runner auth injection，支持 query 和 cookie API keys。
6. 当所有 schemes supported 时，扩展 runner 处理 selected AND groups。
7. Proxy credential intent 只扩展到 local proxy 可以安全支持的范围；任何 remaining multi-credential proxy gap 都要文档化。
8. 更新 README、`auth.env.example`、inspect 和 diagnostics summaries。
9. 增加 fixtures 和 regression tests。
10. 使用 local loopback targets dogfood header/query/cookie 和 combined auth。

## Tests

新增 fixtures：

- document-level bearer auth inherited by operations
- operation-level `security: []` public override
- OR auth alternatives with bearer or header API key
- AND auth requiring header API key plus query API key
- query API key only
- cookie API key only
- OAuth2 scopes metadata-only
- unsupported scheme only
- mixed public/authenticated operations

Regression tests 应覆盖：

- parser preserves OR/AND requirement metadata
- primary auth selection is deterministic
- generated runner injects query API key
- generated runner injects cookie API key
- generated runner injects all supported credentials for an AND group
- generated runner reports all missing auth env vars for combined auth
- README 和 `auth.env.example` summarize alternatives and combined auth
- diagnostics report auth combinations without blocking generation
- old capability JSON without new security metadata remains valid

## Dogfood

使用 local loopback HTTP targets，而不是 external APIs，做 deterministic auth assertions：

- bearer request includes `Authorization`
- header API key request includes configured header
- query API key request includes configured query parameter
- cookie API key request includes `Cookie`
- combined auth request includes all required credentials
- public override sends no auth

同时 rerun mixed-auth existing fixture tests，确保当前 endpoint-level behavior 继续 compatible。

## Success Metrics

Implementation 成功条件：

- OR/AND security requirements 在 generated package metadata 中可见
- generated direct runner 可以执行 supported single and combined auth requirements
- query 和 cookie API keys 不再 classified as unknown
- OAuth/OpenID scopes 被保留，但不执行 OAuth flows
- README、inspect 和 diagnostics 可以清楚解释 auth shape
- old generated package compatibility 保持
- full Python test suite passes

## Acceptance Criteria For This Design

- OpenAPI security OR/AND semantics 已文档化
- current parser baseline 和 flattening gaps 已文档化
- additive IR strategy 已定义
- primary auth selection order 是 deterministic
- bearer、header API key、query API key、cookie API key 和 OAuth/OpenID metadata 的 scheme mappings 已定义
- generated runner/proxy artifact effects 已定义
- diagnostics、README、inspect 和 `auth.env.example` effects 已定义
- tests and dogfood 已命名
- non-goals 保持 API-first compiler boundaries
