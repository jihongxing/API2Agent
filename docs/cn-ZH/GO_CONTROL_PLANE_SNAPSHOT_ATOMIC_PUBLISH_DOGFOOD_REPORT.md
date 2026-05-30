# Go Control Plane Snapshot Atomic Publish Dogfood 报告

日期：2026-05-31

## 目标

避免 snapshot artifact publish 失败时留下 half-published distribution state。

这是 local distribution guard。它还不包含 remote object storage transaction 或 distributed locking。

## 已实现

Control Plane publish 现在会：

- 在写 distribution state 前校验 source artifact
- 拒绝重复的 `snapshot_version` artifact 目录
- 先把 `snapshot.json` 和 `manifest.json` 复制到 temporary artifact directory
- 两个文件都复制完成后才 commit artifact directory
- 通过 temporary file 写入 `current.json`，再替换
- 失败时清理 temporary artifact directory

## 已验证流程

cross-plane dogfood 现在会验证：

1. v10 artifact 成功 publish。
2. distribution `current.json` 推进到 v10。
3. 再次 publish 同一个 v10 artifact 会被拒绝，因为 target artifact 已存在。
4. 被拒绝的 duplicate publish 之后，`current.json` 仍然保持 v10。
5. rejection 后没有残留 temporary v10 artifact directory。

## 检查项

```json
{
  "atomic_publish_advanced_current_to_v10": true,
  "duplicate_atomic_publish_rejected": true,
  "duplicate_atomic_publish_kept_current_v10": true,
  "duplicate_atomic_publish_left_no_temp_artifacts": true
}
```

## 结果

Snapshot Distribution Atomic Publish Guard v0 通过。

local publisher 不再在 artifact 完整前把 artifact files 直接写入最终目录。
