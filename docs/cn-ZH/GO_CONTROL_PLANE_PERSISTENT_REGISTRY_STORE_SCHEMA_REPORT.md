# Go Control Plane Persistent Registry Store Schema v0 报告

日期：2026-05-31

状态：已完成

## 总结

这一项任务把 persistent registry store design 推进为可以测试的 schema/load-parity contract。

它不会把 Control Plane runtime 切换到 Postgres。`registry.FileStore` 仍然是默认 runtime store。

## 已实现

- 新增 Postgres schema draft：`services/control-plane/schema/postgres/001_persistent_registry_store.sql`。
- 覆盖第一版 persistent registry tables：
  - `projects`
  - `api_keys`
  - `capabilities`
  - `providers`
  - `credential_metadata`
  - `routing_policies`
  - `snapshot_configs`
  - `registry_revisions`
  - `snapshot_artifact_publications`
  - `admin_audit_events`
- 为 v0 control-plane model 增加表级约束：
  - active providers 必须包含 `metadata.base_url`
  - routing policies 只允许一个 active global policy
  - snapshot configs 只允许一个 active config
  - snapshot artifact publications 不允许同一个 snapshot version 出现重复 active publication
  - API keys 包含 `key_hash`，为未来 hosted verification 预留；raw keys 仍然不进入 schema
- 新增 `MapRegistryToPersistentRows`，把当前 in-memory `registry.Registry` 映射为 persistent row-shaped structs。
- 新增 `CanonicalRegistry`，在 persistent mapping 和 fingerprint calculation 前对 registry collections 做确定性排序。

## 已验证

- SQL schema test 检查 required tables 和关键 constraints。
- 现有 `network.public_ip.get` file registry fixture 可以映射到 persistent row structs。
- 映射会保留 provider `base_url` metadata。
- File registry import 不会凭空生成 API key hash，也不会产生 raw secret fields。
- Persistent mapping 会生成 registry revision metadata，但不会凭空生成 artifact publication 或 admin audit rows。
- Canonical registry ordering 会排序 projects、API keys、capabilities、providers、provider regions、credential metadata 和 credential scopes，且不修改输入 registry。

## 非目标

这一项任务不实现：

- live Postgres connectivity
- `PostgresStore.Load(ctx)`
- hosted deployment
- registry mutation APIs
- credential vault
- billing
- marketplace features

## 验证

```text
go test ./...
```

在 `services/control-plane` 下已通过。

## 下一步建议

这份 schema report 后续由 `docs/cn-ZH/GO_CONTROL_PLANE_PERSISTENCE_PHASE_REVIEW.md` 承接。

阶段复盘已经把下一项 implementation slice 收窄为：

```text
Go Control Plane PostgresStore Load Parity v0
```
