# API2Agent Tooling Baseline Audit Report v0

日期：2026-05-31

状态：已完成

产物：

```text
.dogfood/tooling-baseline-audit/result.json
```

注意：这个 artifact 会在 baseline audit 复跑时被覆盖。原始 baseline 暴露了 root-path curl naming 偏弱的问题；后续 hardening report 记录了修复后的复跑结果。参见 `docs/cn-ZH/API2AGENT_OPENAPI_FILTERING_CURL_NAMING_HARDENING_REPORT.md`。

复现命令：

```bash
python scripts/api2agent_tooling_baseline_audit.py
```

## 决策

API2Agent Tooling Re-entry 可以继续使用 Python 作为 Tooling reference implementation。

当前 Tooling Layer 已经足够支持简单真实 API-backed Agent capabilities 的生成和执行，而且不需要手动修改生成源码。下一步不应该再做架构暂停，而应该加固这次审计暴露出的两个 onboarding 问题：

1. large OpenAPI specs 需要更好的默认 filtering 和 diagnostics
2. curl-derived root-path APIs 需要更好的 tool naming

下一项任务：

```text
API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0
```

## 范围

这次审计只衡量 API-first Tooling Layer：

- OpenAPI import
- curl import
- generated package quality
- generated direct execution
- no-auth read paths 的 generated proxy execution
- bearer auth 的 credential-safe generation
- latency visibility

没有实现 workflow execution、marketplace、billing、credential vault 或 non-API runtime。

## 总结

| 指标 | 结果 |
| --- | --- |
| curl inputs audited | 4 |
| curl generation success | 4/4 |
| curl first-call success | 4/4 |
| proxy first-call success | 3/3 |
| large OpenAPI generation success | yes |
| GitHub REST unfiltered tool count | 1186 |
| GitHub REST filtered tool count | 3 |

## 审计输入

| Case | Input | Generated tool | Direct result | Proxy result | Naming |
| --- | --- | --- | --- | --- | --- |
| `curl_ipify_public_ip` | `curl https://api.ipify.org?format=json` | `get` | 3/3 success, p50 2192.308 ms | 1/1 success, p50 2048.922 ms | weak |
| `curl_open_meteo_forecast` | Open-Meteo forecast curl | `get_v1_forecast` | 3/3 success, p50 2413.028 ms | 1/1 success, p50 2402.383 ms | good |
| `curl_github_repo_read` | GitHub repo read curl | `get_repos_octocat_hello_world` | 3/3 success, p50 2048.375 ms | 1/1 success, p50 6110.973 ms | good |
| `curl_httpbin_bearer` | httpbin bearer curl | `get_bearer` | 3/3 success, p50 2198.133 ms | not run | good |
| `openapi_github_large_spec` | GitHub REST OpenAPI | `1186 tools` unfiltered | generation only | generation only | needs filtering |

Latency 数字是当前本地环境下的 baseline samples，不是全球性能承诺。

## 发现

### 正向：curl onboarding 对审计过的 read-only APIs 可用

ipify、Open-Meteo、GitHub repo read 和 httpbin bearer 都可以不修改生成源码完成 generation，并实现第一次 direct execution 成功。

这支持当前 Tooling Re-entry 判断：Python 继续作为低成本 API-first onboarding 的 tooling reference implementation 是合理的。

### 正向：generated packages 已具备 observable-path readiness

Generated packages 已包含 proxy-mode docs、`API2AGENT_PROXY_URL` 支持、timeout defaults 和 credential intent code。no-auth proxy audit 已经为 ipify、Open-Meteo 和 GitHub repo read 成功记录 usage events。

### 正向：审计路径中 credential safety 成立

Bearer-auth case 生成的是 env-based auth contract，没有把 raw token 写死进生成代码。审计过的 proxy usage events 中没有出现 bearer token marker。

### 中等：large OpenAPI specs 仍会变成 endpoint dumps

GitHub REST OpenAPI 可以成功生成，但未过滤 package 包含 1186 个 tools。技术上正确，但对 Agent 不可用。

同一个 spec 过滤到 `/repos/{owner}/{repo}` 后只生成 3 个 tools，说明现有 filter path 可用，但需要更好的默认 guidance、diagnostics 或 presets。

### 中等：root-path curl naming 偏弱

`curl https://api.ipify.org?format=json` 生成的 tool name 是 `get`。这个名字对 Agent tool selection 太泛。

Capability name 因为审计传入了等价 `--name` 而表现良好，但 tool naming 仍然需要对 root-path APIs 引入 host/path intent。

### 中等：provider region metadata 缺失

Generated packages 当前不输出 provider region metadata。这不阻塞当前 execution，但会削弱 faster-response 和 location-aware routing 目标。

## 需求检查

| Requirement | Status |
| --- | --- |
| 至少 5 个真实 API onboarding attempts 被文档化 | passed |
| generation success measured | passed |
| first-call path measured | passed |
| manual edits measured | passed |
| naming quality measured | passed |
| proxy compatibility measured | passed |
| credential safety measured | passed |
| p50/p95 latency measured where safe | passed |
| API-first constraint preserved | passed |
| no workflow engine expansion | passed |

## 下一步修复排序

1. `API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0`
   - onboarding impact 最高。
   - 直接处理 1186-tool GitHub REST dump 和 `get` root-path curl tool name。

2. Generated package region metadata v0
   - 支持 faster-response 和未来 location-aware routing。
   - 应该保持 metadata-only，不启动新的 routing rewrite。

3. Proxy-mode credential dogfood expansion
   - 把 baseline proxy runs 扩展到 bearer/auth cases，并使用 local credential config。
   - 继续确保 raw provider secrets 不进入 generated files 和 events。

## 结论

Tooling Layer 已准备好进入 focused hardening。现在不应该为 re-entry 切到 Go，也不应该扩展到 non-API sources。

下一项 implementation slice 应该降低现有 API-first compiler 的 onboarding friction：

```text
API2Agent OpenAPI Filtering + curl Tool Naming Hardening v0
```

后续状态：已完成。审计中的 ipify root-path curl case 现在会生成 `get_ipify_public_ip`，large OpenAPI generation 在 package 仍然过大时会输出 warning。
