# Agent Capability Compiler RC2 Hardening Matrix

Purpose: close the source-expansion stage and prepare a publishable RC2.

## Scope

RC2 hardening focuses on:

- real-world or near-real dogfood for each supported source
- a compact compatibility matrix for source adapters
- generated package consistency across all sources
- CLI UX and error-message review
- package build and installed-console smoke

Out of scope:

- new source adapters
- hosted control-plane work
- event-bus, workflow-runtime, or gRPC-runtime implementation
- marketplace, billing, or SaaS control surfaces

## Source Matrix

| Source | CLI | Status | Executable Runner | Key Boundary |
| --- | --- | --- | --- | --- |
| OpenAPI | file argument | supported | yes | HTTP operations only |
| curl | `--curl` | supported | yes | one captured HTTP request |
| HAR | `--har` | supported | yes | browser request capture, no browser replay |
| Postman | `--postman` | supported | yes | Collection request import |
| Insomnia | `--insomnia` | supported | yes | export request import |
| Bruno | `--bruno` | supported | yes | JSON collection import |
| GraphQL endpoint | `--graphql` | supported | yes | fixed operations, no introspection/runtime |
| workflow endpoint | `--workflow` | supported | yes | one callable endpoint, no workflow engine |
| protobuf/gRPC | `--proto` | scaffold | no | unary schema import only; no gRPC transport |
| AsyncAPI webhook | `--asyncapi` | supported | yes | HTTP-bound publish/send only; no event bus |

## RC2 Readiness Checks

- all source adapters generate `capability.json`, `tools.json`, `runner.py`, `mcp_server.py`, docs, diagnostics, auth template, and examples
- OpenAI tool schemas do not leak internal `x-api2agent-*` metadata
- generated runner imports for every source package
- non-executable scaffolds fail clearly instead of pretending to execute
- `api2agent generate --help` lists every source option
- full test suite passes
- wheel builds and installed console script can generate a package
