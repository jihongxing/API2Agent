# Agent Capability Compiler OpenAPI Server Handling Design v0

日期：2026-06-01

状态：complete

## 决策

下一项 OpenAPI hardening implementation slice 应为：

```text
Agent Capability Compiler OpenAPI Server Handling Implementation v0
```

这个 slice 应把 multiple OpenAPI server choices 作为 generated metadata 保留，改进 environment/profile hints，让 document/path/operation server selection 可见，并安全处理 relative server URLs。

它必须保持 API-first，不得增加 workflow runtime、marketplace/provider onboarding、vault、billing、hosted public CRUD、production gateway permission source 或 automatic snapshot propagation。

## 为什么现在做这个 slice

Compiler 已经处理 examples/defaults 和 security requirement combinations。下一个常见 real-spec onboarding gap 是 server layout。

真实 OpenAPI specs 经常包含：

- production、staging、sandbox、regional 或 versioned APIs 的 multiple document-level servers
- admin 或 alternate subdomains 的 path-level servers
- special routes 的 operation-level servers
- version、region、tenant 或 environment 的 server variables
- relative server URLs，例如 `/api/v3`
- 对 smoke tests 可能不安全的 ambiguous first-server choices

当前 generation 会在 server variable default substitution 后选择 first server。这个行为有用，但会丢掉 alternatives，也不会向 users 或 diagnostics 解释 server provenance。

## Current Baseline

已有：

- document-level first server URL extraction
- server variable default substitution
- path-level server override
- operation-level server override
- 当 path/operation server 不同于 document server 时设置 tool-level `base_url`
- generated runner `API2AGENT_BASE_URL`
- generated runner `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>`
- invalid override fail-fast
- joining override URL and path 时保留 base path
- inspect 显示 capability base URL 和 tool-level base override
- diagnostics detects missing base URL

重要 gaps：

- non-selected server choices 会被丢弃
- server descriptions 会被丢弃
- server variable metadata 在 default substitution 后会被丢弃
- relative server URLs 没有清晰解释
- generated README 不列出 server choices 或 selected provenance
- diagnostics 不能解释 multi-server ambiguity
- generated packages 不能暴露 staging/prod/sandbox/regional hints
- operation-level server summaries 过于简略
- runtime override semantics 没有指向 known server profiles

## Goals

- 在 generated package metadata 中保留所有 document/path/operation server choices
- 保持已有 `base_url` / `tool.base_url` behavior compatible
- 记录 selected server provenance：document、path、operation 或 runtime override
- 保留 server variables 及其 defaults 和 enums
- 推断 lightweight profile hints，例如 `production`、`staging`、`sandbox`、`regional`、`admin` 和 `relative`
- 让 relative server URLs 安全且显式
- 改进 generated README、inspect 和 diagnostics server summaries
- 保持 runner runtime override behavior unchanged and compatible
- 保持 generation deterministic and offline

## Non-Goals

不实现：

- network probing during generation
- automatic production/staging selection by LLM
- hosted server profile management
- dynamic tenant discovery
- DNS or TLS validation
- workflow composition
- marketplace/provider onboarding
- credential vault writes
- billing or settlement
- hosted public Control Plane CRUD
- automatic snapshot publish/reload

## Proposed IR Strategy

保留已有字段：

```text
Capability.base_url
Tool.base_url
```

新增 optional metadata：

```text
ServerVariable:
  default: str | None
  enum: list[str]
  description: str | None

ServerConfig:
  url: str
  resolved_url: str
  description: str | None
  variables: dict[str, ServerVariable]
  source: "document" | "path" | "operation"
  path: str | None
  operation_id: str | None
  profile_hints: list[str]
  is_relative: bool

Capability.servers: list[ServerConfig]
Tool.servers: list[ServerConfig]
Tool.server_source: "document" | "path" | "operation" | None
```

Generated `capability.json` 保持 backward compatible，因为这些字段都是 additive。旧 consumers 可以继续使用 `base_url` 和 `tool.base_url`。

## Server Selection Rules

Selection 应保持 deterministic：

1. operation-level first server wins for that operation
2. path-level first server wins when operation-level server is absent
3. document-level first server wins when neither operation nor path server exists
4. server variables 使用其 `default` 值生成 `resolved_url`
5. 如果没有 server，`base_url` 保持 empty，并由 diagnostics 报告 `missing_base_url`
6. relative server URLs 会被保留并标记 `is_relative=true`

Selected resolved URL 继续填充：

- `Capability.base_url` for the selected document-level first server
- 当 selected path/operation URL 不同于 capability base URL 时，填充 `Tool.base_url`

## Relative Server URL Policy

Relative server URLs 不应被静默当作完整 provider origins。

v0 中：

- 在 server metadata 中保留 relative URL
- 标记 `is_relative=true`
- 只有在具备足够 base context 时才保留 existing joined behavior
- diagnostics 应警告 `relative_server_url`
- README 应说明 user 需要设置 `API2AGENT_BASE_URL` 到真实 origin
- runner 继续对 invalid runtime overrides fail-fast

Generation 期间不要发明 origin。

## Profile Hints

Profile hints 是从 URL 和 description text 推断出的 deterministic string heuristics。

Examples：

- `production`: `prod`、`production`、`api.example.com`
- `staging`: `staging`、`stage`、`test`
- `sandbox`: `sandbox`
- `regional`: variables named `region`、host labels like `{region}` 或 regional descriptions
- `admin`: host/path/description 中的 `admin`
- `relative`: relative URL

Hints 只是 advisory metadata。v0 中不改变 selected runtime behavior。

## Generated Artifact Effects

README：

- 显示 selected default base URL
- 按 source 和 profile hints 列出 known server choices
- tool summary 中显示 path/operation server overrides
- 用 known server choices 解释 `API2AGENT_BASE_URL` 和 tool-specific override
- 对 relative server URLs 给出明确 warning

`api2agent inspect`：

- 像现在一样显示 default base URL
- 显示 server count 和 top profile hints
- 对 path/operation overrides 显示 tool server source

Diagnostics：

- `multiple_servers_present`
- `relative_server_url`
- `server_variables_present`
- `operation_server_override`
- `path_server_override`
- `ambiguous_server_profiles`

Generated runner：

- 保持当前 override precedence：

```text
API2AGENT_TOOL_BASE_URL_<TOOL_NAME>
-> API2AGENT_BASE_URL
-> tool.base_url
-> capability.base_url
```

- v0 中不自动切换 profiles
- 可以在 generated `CAPABILITY` 中包含 server metadata，供未来 profile-aware clients 使用

## Implementation Plan

1. 增加 additive `ServerVariable` 和 `ServerConfig` IR models。
2. 增加 `Capability.servers`、`Tool.servers` 和 `Tool.server_source`。
3. 将 first-server-only extraction 替换为 normalized server list extraction。
4. 保留 raw `url`、resolved URL、description、variables、source、path、operation id、profile hints 和 relative flag。
5. 保持已有 selected `base_url` / `tool.base_url` behavior compatible。
6. 更新 README server section。
7. 更新 inspect server summaries。
8. 增加 multi-server 和 relative/profile diagnostics。
9. 增加 fixtures 和 regression tests。
10. 使用 local fixtures dogfood multiple document servers、path/operation overrides、variables 和 relative servers。

## Tests

新增 fixtures：

- multiple document-level servers with descriptions
- server variables with default and enum
- path-level server override
- operation-level server override
- relative document server URL
- relative path/operation server URL
- regional variable server URL
- no server URL

Regression tests 应覆盖：

- parser preserves all server choices
- selected base URL remains compatible with current behavior
- path/operation selected server still populates `tool.base_url`
- server variables are preserved and default-substituted
- relative server URLs are marked and diagnosed
- README lists server choices and override guidance
- inspect shows server summaries
- runner override precedence remains unchanged
- old capability JSON without server metadata remains valid

## Dogfood

使用 local dogfood：

- existing `servers.yaml`
- new multi-server fixture
- Swagger Petstore-style `/api/v3` relative-server fixture
- generated runner with default base URL
- generated runner with `API2AGENT_BASE_URL`
- generated runner with `API2AGENT_TOOL_BASE_URL_<TOOL_NAME>`

不需要网络依赖。

## Success Metrics

Implementation 成功条件：

- generated package metadata exposes all relevant OpenAPI servers
- users can see why a default server was selected
- relative server URLs are explicit and actionable
- staging/sandbox/regional/admin hints are visible but do not change runtime behavior
- existing base URL override tests still pass
- full Python test suite passes

## Acceptance Criteria For This Design

- current server handling baseline and gaps 已文档化
- additive IR strategy 已定义
- deterministic server selection rules 已定义
- relative server URL policy 已定义
- profile hints 被定义为 advisory metadata
- generated README、inspect、diagnostics 和 runner effects 已定义
- tests and dogfood 已命名
- non-goals 保持 API-first compiler boundaries
