# API2Agent Hosted Control Plane Pause + Agent Capability Compiler Re-entry v0

Date: 2026-06-01

Status: complete

## Decision

Pause deeper hosted Control Plane work and return to expanding the Agent capability compiler.

The previously recommended task:

```text
Go Control Plane Hosted Admin Gateway Permission Source Design v0
```

is moved to the hosted-readiness backlog. It remains important, but it is no longer the immediate next task.

The next immediate task is:

```text
Agent Capability Compiler Expansion Design v0
```

This re-entry is intentionally constrained. API2Agent should strengthen the path from real APIs to Agent-ready capabilities without becoming a workflow engine, marketplace, hosted provider onboarding product, vault, billing system, or public Control Plane CRUD surface.

## Why Pause Hosted Work Now

The hosted Control Plane track has reached a credible pause point:

- persistent registry storage is dogfooded
- import/replace mutation is implemented
- admin mutation idempotency is durable
- hosted admin identity and trusted-gateway auth are implemented
- gateway secret rotation and key-id evidence are implemented
- local gateway contract harness proves public header stripping and trusted claim injection
- closeouts document remaining hosted-readiness risks

The next hosted tasks are deeper platform work:

- permission-source design
- real public auth
- production gateway deployment
- tenant-partitioned mutation semantics
- hosted operational controls

Those are valuable, but they are not the highest leverage next move while the Agent capability compiler still has obvious room to improve real API onboarding and generated capability quality.

## Why Return To The Compiler

API2Agent's core product loop is:

```text
real API input
  -> Agent capability compiler
  -> generated package
  -> observable execution
  -> usage, latency, error, credential, and routing data
  -> better reliability decisions
```

Improving the compiler has immediate product leverage:

- lowers time from API input to first successful Agent call
- increases the number of real APIs that can feed usage data
- improves generated tool names, schemas, docs, and safe tests
- improves proxy/observable execution adoption
- strengthens future Control Plane provider candidates without requiring hosted product work now

## Consolidated State

### Tooling / Compiler

Stable enough to expand:

- OpenAPI and curl inputs are supported.
- Generated packages include runner, smoke test, MCP server, README, and capability metadata.
- Direct and proxy execution paths are available.
- Credential intent, provider region, latency benchmark, base URL override, endpoint auth inference, manual write test path, and large-spec filtering have been hardened.

Main remaining opportunity:

- generated capability quality and real-world API onboarding still need systematic expansion.

### Go Data Plane

Stable enough to keep as execution contract:

- Protocol v0.2 records are emitted and validated.
- Retry/failover, timeout budget, quota, credential config, durable events, snapshot freshness, reload, and attempt correlation are dogfooded.
- Data Plane should continue consuming immutable/versioned snapshots, not mutable Control Plane tables.

### Go Control Plane

Stable enough to pause:

- persistent registry read/write primitives exist
- import/replace remains controlled and private
- idempotency and audit evidence are durable
- hosted/trusted-gateway admin path is proven through a local gateway contract harness

Remaining hosted risks are documented but intentionally deferred.

## Compiler Expansion Principles

### API-first

Continue focusing on:

- OpenAPI
- curl
- HTTP/REST APIs
- generated capability packages
- generated runners
- generated smoke/manual write tests
- generated MCP servers

### Quality Over Surface Area

Compiler expansion should improve whether generated capabilities are Agent-usable, not merely increase endpoint count.

Good expansion areas:

- better operation naming
- better parameter/schema shaping
- better auth inference
- better server/base URL handling
- generated docs that get to first call faster
- capability quality diagnostics
- safer generated tests
- observable/proxy execution defaults

### Preserve Control/Data Plane Boundaries

Do not make compiler work depend on hosted Control Plane features.

Generated artifacts should remain compatible with:

- proxy mode
- credential-safe execution
- usage event identity
- routing/provider metadata
- Data Plane snapshots where provider candidates overlap
- language-neutral protocol artifacts

## Recommended Expansion Tracks

### Track A: Capability Quality Diagnostics

Design a compiler report that scores or flags generated capabilities before a user runs them.

Candidate checks:

- vague capability/provider/tool names
- missing auth intent
- missing required parameters
- risky write operations
- overly broad large-spec output
- weak descriptions for Agent tool selection
- missing examples or smoke-test defaults

### Track B: OpenAPI Real-World Hardening

Improve support for common OpenAPI spec complexity:

- multiple servers and base paths
- security scheme combinations
- request bodies with nested schemas
- enum/default/example propagation
- operation filtering diagnostics
- schema cases that produce poor Agent-facing tool inputs

### Track C: curl Instant Onboarding

Make curl-derived packages more useful immediately:

- stronger auth inference
- better query/header/body default preservation
- better capability naming from host/path/action
- clearer generated README first-call path
- safer write-method handling

### Track D: Observable Execution Defaults

Make generated packages naturally feed usage data:

- proxy-mode guidance
- credential intent clarity
- latency benchmark hooks
- provider region metadata
- stable usage identity fields

## Recommended Next Slice

Start with design, not implementation:

```text
Agent Capability Compiler Expansion Design v0
```

The design should choose the first concrete compiler expansion slice and define:

- target user workflow
- accepted inputs
- generated artifact changes
- compatibility with existing generated packages
- tests and dogfood
- success metrics
- non-goals

Recommended first implementation candidate after that design:

```text
Agent Capability Compiler Quality Diagnostics v0
```

This is high leverage because it improves both OpenAPI and curl paths without prematurely adding a new runtime or hosted dependency.

## Frozen Scope

Still do not start:

- workflow engine execution
- non-API runtime adapters
- marketplace UI or provider submission
- billing or settlement
- credential vault writes
- hosted public CRUD
- real OAuth/OIDC implementation
- production gateway deployment
- automatic snapshot publish/reload
- Data Plane reads from mutable Control Plane tables

## Validation

This is a docs-only stage consolidation. Validation requirement:

```text
git diff --check
```
