# API2Agent curl Naming Residual Review v0

日期：2026-05-31

状态：已完成

## 总结

这次 curl naming residual review 找到一个真实残留问题：

```text
api.github.com -> capability: api
```

Root-path tool naming 之前已经修好，但 `api.github.com` 这类 generic subdomain 的默认 capability/provider naming 仍然太泛。这也会生成 `API_TOKEN` 这类泛 credential env name。

这次 review 在不重新打开整体 naming strategy 的前提下关闭了这个 residual。

范围保持克制：

- 只处理 curl input
- API-first only
- 不做 workflow engine
- 不改 hosted registry 或 control-plane
- 保持显式 `--name` 优先
- 保持 non-root path-based tool naming

## 改动

curl-derived capability names 现在会跳过 generic leading subdomains：

```text
api.github.com -> github_api
www.example.com -> example_www
```

这提升了 generated provider/capability identity 和 credential env names 的可读性。

示例：

```text
curl https://api.github.com/rate_limit -H 'Authorization: Bearer token'
```

之前：

```text
capability: api
tool: get_rate_limit
auth env: API_TOKEN
```

现在：

```text
capability: github_api
tool: get_rate_limit
auth env: GITHUB_API_TOKEN
```

已有保证保持不变：

- 显式 `--name` 仍然优先
- root-path curl tools 仍然包含 capability intent
- non-root path tools 为 backward compatibility 继续保持 path-based

## Dogfood

复现命令：

```bash
python scripts/api2agent_curl_naming_residual_review.py
```

产物：

```text
.dogfood/curl-naming-residual-review/result.json
```

Dogfood cases：

| Case | Expected |
| --- | --- |
| `curl https://api.github.com/rate_limit -H 'Authorization: Bearer token'` | `github_api`, `get_rate_limit`, `GITHUB_API_TOKEN` |
| `curl https://api.ipify.org?format=json` | `ipify_api`, `get_ipify_api` |
| same ipify curl with explicit `--name ipify_public_ip` | `ipify_public_ip`, `get_ipify_public_ip` |
| `curl https://api.example.com/items?format=json` | `example_api`, `get_items` |

## 结果

Dogfood 已通过。

关键 checks：

```json
{
  "all_cases_generated": true,
  "capability_names_match": true,
  "tool_names_match": true,
  "auth_envs_match": true,
  "explicit_name_still_wins": true,
  "non_root_path_stays_path_based": true
}
```

## 为什么重要

这关闭了 Tooling Re-entry backlog 中剩余的 naming friction：

- provider/capability ids 默认不再那么泛
- credential env names 更有意义
- Agents 对 non-root APIs 仍然获得稳定的 path-based tool names
- 开发者仍然可以用 `--name` 显式覆盖 naming

## 阶段收口

当前 Tooling Re-entry backlog 已关闭，并且 Tooling Re-entry Closeout + Phase Review 已完成。

下一项任务：

```text
Go Control Plane Persistent Registry Import/Replace Transaction Design v0
```
