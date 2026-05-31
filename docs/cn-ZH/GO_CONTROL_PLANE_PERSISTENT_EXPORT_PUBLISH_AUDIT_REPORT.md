# Go Control Plane Persistent Export/Publish Audit Writes 报告

日期：2026-05-31

状态：已完成

## 摘要

`Go Control Plane Persistent Export/Publish Audit Writes v0` 为本地 Control Plane service 增加了持久化写侧审计。该能力只在 registry store 显式配置为 Postgres 时启用。

File-store mode 保持不变。Registry mutation APIs、hosted auth、vault、billing 和 marketplace 均不进入本次范围。

## 已实现

- 新增 `PersistentAuditSink` 边界。
- 新增 Postgres audit sink，写入：
  - `registry_revisions`
  - `snapshot_artifact_publications`
  - `admin_audit_events`
- 仅在 Postgres runtime path 中接入 audit sink。
- 为以下 admin 操作记录 audit events：
  - registry validation
  - artifact export
  - distribution publish
  - current pointer reads
- artifact export 成功后写入 registry revision。
- distribution publish 成功后写入 artifact publication。
- 对成功路径加入 fail-closed 行为：持久化 audit 写入失败时返回 `AUDIT_WRITE_FAILED`。
- failure path 的 audit 写入保持 best-effort，避免遮盖原始 caller-facing error。
- 加固 live Postgres dogfood 脚本：使用临时构建的 Control Plane binary 和动态服务端口，避免旧进程污染验证结果。

## 已验证

单元测试覆盖：

- registry validation audit event writes
- artifact export audit writes
- distribution publish audit writes
- current pointer read audit writes
- successful export work 后 audit 写入失败时返回 `AUDIT_WRITE_FAILED`

Podman live Postgres dogfood 已通过：

```json
{
  "admin_audit_events": 4,
  "registry_revisions": 2,
  "snapshot_artifact_publications": 1
}
```

live dogfood 覆盖：

- schema apply
- seed import
- file/Postgres snapshot parity
- CLI artifact export
- service health
- service registry validation
- service artifact export
- service distribution publish
- service current pointer read
- 通过 podman `psql` 直接断言 audit tables 计数

Dogfood 输出：

```text
.dogfood/go-control-plane-live-postgres/report.json
```

## 非目标

- 未增加 registry mutation API。
- 未增加 hosted persistence deployment。
- 未增加 credential vault。
- 未增加 billing 或 settlement logic。
- 未增加 marketplace feature。

## 下一项建议任务

```text
Go Control Plane Persistent Store Failure Semantics Hardening v0
```

原因：persistent audit writes 已经引入明确的 fail-closed 行为。在添加 mutation APIs 或更广泛的 hosted persistence 之前，项目应该先定义并测试 persistent-store 在 read、export、publish、audit 和 dogfood 路径上的失败语义。
