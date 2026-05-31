# API2Agent OpenAPI Filtering + curl Tool Naming Hardening Report v0

日期：2026-05-31

状态：已完成

## 总结

这个 hardening slice 处理了 Tooling Baseline Audit 中优先级最高的两个问题，同时没有扩展出 API-first tooling 范围：

1. root-path curl APIs 会生成 `get` 这类泛 tool names
2. large OpenAPI specs 可能生成技术上正确但对 Agent 不友好的 endpoint dumps

实现保持了现有 non-root curl paths 和 OpenAPI generation 行为的 backward compatibility。

## 改动

### curl root-path tool naming

Root-path curl inputs 现在会把 capability intent 放进生成的 tool name。

之前：

```text
curl https://api.ipify.org?format=json
  -> tool: get
```

之后：

```text
curl https://api.ipify.org?format=json
  -> tool: get_ipify_public_ip
```

Non-root curl paths 保持现有 path-based behavior：

```text
curl https://api.example.com/items?format=json
  -> tool: get_items
```

这样既保持现有 generated package 行为稳定，又让 root-path APIs 更容易被 Agent 选择。

### Large OpenAPI generation diagnostics

当 OpenAPI generation 生成超过 50 个 tools 时，CLI 现在会输出 warning：

```text
Warning: generated package contains N tools, which is likely too many for Agent tool selection.
Narrow the package with --include-tag, --include-path, --include-operation, or --max-tools.
```

这刻意保持为 diagnostic-only：

- 不做默认截断
- 不做隐式 filtering
- 不改变 generated artifacts
- 不扩展 workflow 或 non-API scope

目标是通过明确告诉开发者何时需要 bounded package flow，降低 onboarding cost。

## 复跑结果

Hardening 后已重新运行 Tooling Baseline Audit script：

```bash
python scripts/api2agent_tooling_baseline_audit.py
```

结果总结：

| 指标 | 结果 |
| --- | --- |
| curl generation success | 4/4 |
| curl first direct-call success | 4/4 |
| no-auth proxy first-call success | 3/3 |
| GitHub REST OpenAPI generation | success |
| GitHub REST unfiltered tool count | 1186 |
| GitHub REST filtered tool count | 3 |
| root-path ipify tool name | `get_ipify_public_ip` |

Large OpenAPI risk 按设计仍然可见，但开发者现在通过 CLI 生成 oversized package 时会获得明确 warning。

## 测试

新增 regression coverage：

- root-path curl naming 使用 capability intent
- non-root curl naming 继续保持 path-based
- large OpenAPI generation 在 unbounded 时输出 warning
- 使用 `--max-tools` bounded large OpenAPI generation 不输出 warning

已验证：

```text
python -m pytest tests/test_curl_parser.py tests/test_cli.py
python scripts/api2agent_tooling_baseline_audit.py
```

## 剩余缺口

Generated packages 仍然缺少 provider region metadata。

这现在是 Tooling Re-entry 最高优先级缺口，因为它直接服务于“更快 Agent API 响应”目标和未来 location-aware routing。

下一项任务：

```text
Generated Package Region Metadata v0
```

