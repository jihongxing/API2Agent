# Go Data Plane Snapshot Manifest Consistency Dogfood 报告

日期：2026-05-31

## 目标

防止分发出去的 snapshot artifact 在以下文件之间出现 metadata 不一致：

- `snapshot.json`
- `manifest.json`
- `current.json`

这同时保护 publish-time artifact integrity 和 reload-time distribution integrity。

## 已实现

Control Plane 现在会在写入或发布 artifact 前校验 artifact consistency：

- `manifest.snapshot_version` 必须匹配 `snapshot.snapshot_version`
- `manifest.snapshot_source` 必须匹配 `snapshot.snapshot_source`
- `manifest.registry_fingerprint` 必须匹配 `snapshot.metadata.registry_fingerprint`
- `manifest.snapshot_version_policy` 必须匹配 `snapshot.metadata.snapshot_version_policy`

Data Plane 现在会在从 `current.json` 加载 snapshot 前校验 distribution consistency：

- `current.json` 必须和 `manifest.json` 一致
- `manifest.json` 必须指向和 `current.json` 相同的 snapshot 文件
- `manifest.json` 必须和 `snapshot.json` metadata 一致

## 已验证流程

cross-plane dogfood 现在会验证：

1. v1 distribution 正常加载。
2. v2 distribution reload 成功。
3. incompatible v3 schema reload 被拒绝，并保持 v2。
4. v4 先正常发布，然后篡改 distribution 中的 `snapshot.json`。
5. Data Plane reload 因 manifest/snapshot fingerprint mismatch 拒绝 v4，并保持 v2。
6. v5 artifact 在 publish 前篡改 `manifest.json`。
7. Control Plane 拒绝 v5 publish，且不会推进 `current.json`。

## 检查项

```json
{
  "manifest_consistency_reload_rejected": true,
  "manifest_consistency_reload_kept_v2": true,
  "manifest_consistency_reload_audit_event_recorded": true,
  "health_after_manifest_consistency_reload_still_v2": true,
  "manifest_mismatch_publish_rejected": true,
  "manifest_mismatch_publish_did_not_advance_current": true
}
```

## 结果

Snapshot Metadata Manifest Consistency Guard v0 通过。

本地 distribution path 现在可以在 Control Plane publish time 和 Data Plane reload time 同时拒绝 metadata drift。
