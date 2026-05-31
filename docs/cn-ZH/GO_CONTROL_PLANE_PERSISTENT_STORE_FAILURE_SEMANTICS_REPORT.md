# Go Control Plane Persistent Store Failure Semantics Hardening 报告

日期：2026-05-31

状态：已完成

## 摘要

`Go Control Plane Persistent Store Failure Semantics Hardening v0` 让本地 Control Plane service 可以区分 persistent-store 平台故障和 file-registry validation 失败。

默认 file-store 路径保持不变。Registry mutation APIs、hosted auth、vault、billing 和 marketplace 均不进入本次范围。

## 已实现

- 为 Postgres-backed service operations 增加稳定的 persistent registry load failure semantics。
- `registry-store=postgres` 读取失败现在返回：
  - HTTP status：`503`
  - `error_type`：`PERSISTENT_STORE_READ_FAILED`
  - `error_scope`：`platform`
  - `retryable`：`true`
- File-store 读取失败保持：
  - HTTP status：`400`
  - `error_type`：`REGISTRY_INVALID`
  - `error_scope`：`caller`
  - `retryable`：`false`
- 成功路径的 persistent audit write failures 继续 fail closed：
  - HTTP status：`500`
  - `error_type`：`AUDIT_WRITE_FAILED`
  - `error_scope`：`platform`
  - `retryable`：`true`
- Failure-path admin audit writes 保持 best-effort，避免遮盖原始 caller-facing errors。

## 已验证

Regression tests 覆盖：

- Postgres-backed registry validation read failures。
- Postgres-backed artifact export read failures。
- File-store read failures 仍然保持 `REGISTRY_INVALID`。
- registry validation 在 required audit write 失败时 fail closed。
- artifact export 在 required audit write 失败时 fail closed。
- distribution publish 在 required audit write 失败时 fail closed。
- current pointer read 在 required audit write 失败时 fail closed。

验证命令：

```text
services/control-plane: go test ./...
services/data-plane: go test ./...
repo root: python -m pytest
live Postgres dogfood: passed
```

Live Postgres dogfood 仍然验证 persistent audit rows：

```json
{
  "admin_audit_events": 4,
  "registry_revisions": 2,
  "snapshot_artifact_publications": 1
}
```

## 非目标

- 未增加 registry mutation API。
- 未增加 filesystem publish 和 audit writes 之间的 transaction bundling。
- 未增加 hosted persistence deployment。
- 未增加 credential vault。
- 未增加 billing 或 settlement logic。
- 未增加 marketplace feature。

## 下一项建议任务

```text
Go Control Plane Persistent Registry Mutation Boundary Review v0
```

原因：persistent read-side loading、runtime wiring、audit writes 和 failure semantics 已经足够稳定，下一步应先复盘 mutation boundary，再决定是否增加任何 write APIs。
