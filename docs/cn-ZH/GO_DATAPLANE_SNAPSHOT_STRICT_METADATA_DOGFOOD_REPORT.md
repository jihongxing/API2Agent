# Go Data Plane Snapshot Strict Metadata Dogfood 报告

日期：2026-05-31

## 目标

要求 Control Plane 导出的 snapshots 必须携带 audit、replay 和 distribution safety 所需的 metadata。

暂时仍然允许没有 Control Plane metadata 的 legacy local snapshots。

## 已实现

Data Plane snapshot compatibility 现在会通过以下 metadata 判断 snapshot 是否是 Control Plane/exported snapshot：

- `exporter`
- `registry_fingerprint`
- `snapshot_version_policy`

只要命中这个条件，snapshot 必须包含：

```json
{
  "metadata": {
    "schema_version": "api2agent.protocol.v0.2",
    "registry_fingerprint": "sha256:...",
    "snapshot_version_policy": "explicit"
  }
}
```

缺少 required metadata 时，startup load、`api2agent-snapshot-check` 和 manual reload 都会失败，因为三条路径使用同一个 snapshot loader。

## 已验证流程

cross-plane dogfood 现在会验证：

1. v1 distribution 正常加载。
2. 损坏的 `current.json` reload 失败并保持 v1。
3. v2 distribution reload 成功。
4. v3 distribution 携带 incompatible `schema_version`，会被拒绝并保持 v2。
5. v4 distribution 缺少 `registry_fingerprint`，会被拒绝并保持 v2。
6. strict metadata reload failure 会写入 `snapshot_reload_event`。
7. execution 仍然在 v2 上成功，并且 routing decision 记录 v2。

## 检查项

```json
{
  "strict_metadata_reload_rejected": true,
  "strict_metadata_reload_kept_v2": true,
  "strict_metadata_reload_audit_event_recorded": true,
  "health_after_strict_metadata_reload_still_v2": true,
  "snapshot_check_has_registry_fingerprint": true,
  "snapshot_check_has_explicit_version_policy": true,
  "snapshot_check_schema_version_matches": true
}
```

## 结果

Snapshot Strict Metadata Requirement v0 通过。

Control Plane snapshot 现在必须携带足够 metadata，说明它来自哪里、目标 protocol contract 是什么、代表哪份 registry state。
