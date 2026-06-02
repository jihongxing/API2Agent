# Agent Capability Compiler RC2 Hardening Matrix

目的：关闭 source adapter 横向扩展阶段，准备可发布的 RC2。

## 范围

RC2 hardening 聚焦：

- 每个 supported source 的真实或接近真实 dogfood
- source adapters 的 compact compatibility matrix
- 所有来源生成包的一致性
- CLI UX 和错误信息检查
- package build 与 installed console smoke

不包含：

- 新 source adapters
- Hosted Control Plane 工作
- event-bus、workflow-runtime 或 gRPC-runtime implementation
- marketplace、billing 或 SaaS control surfaces

## Source Matrix

| Source | CLI | Status | Executable Runner | Key Boundary |
| --- | --- | --- | --- | --- |
| OpenAPI | file argument | supported | yes | 仅 HTTP operations |
| curl | `--curl` | supported | yes | 单个 captured HTTP request |
| HAR | `--har` | supported | yes | browser request capture，不做 browser replay |
| Postman | `--postman` | supported | yes | Collection request import |
| Insomnia | `--insomnia` | supported | yes | export request import |
| Bruno | `--bruno` | supported | yes | JSON collection import |
| GraphQL endpoint | `--graphql` | supported | yes | fixed operations，不做 introspection/runtime |
| workflow endpoint | `--workflow` | supported | yes | 一个 callable endpoint，不做 workflow engine |
| protobuf/gRPC | `--proto` | scaffold | no | 仅 unary schema import；不接 gRPC transport |
| AsyncAPI webhook | `--asyncapi` | supported | yes | 仅 HTTP-bound publish/send；不做 event bus |

## RC2 Readiness Checks

- 所有 source adapters 都生成 `capability.json`、`tools.json`、`runner.py`、`mcp_server.py`、docs、diagnostics、auth template 和 examples
- OpenAI tool schemas 不泄漏内部 `x-api2agent-*` metadata
- 每种来源生成的 runner 都可以 import
- 不可执行的 scaffolds 必须清晰失败，不能伪装成可执行
- `api2agent generate --help` 列出所有 source options
- full test suite passes
- wheel builds，并且 installed console script 可以生成 package
