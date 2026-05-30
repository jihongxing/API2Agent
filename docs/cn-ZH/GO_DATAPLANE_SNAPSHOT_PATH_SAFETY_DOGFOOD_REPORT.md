# Go Data Plane Snapshot Path Safety Dogfood 报告

日期：2026-05-31

## 目标

防止 artifact 和 distribution metadata 通过不安全文件引用逃逸出预期目录。

保护范围：

- `manifest.snapshot_file`
- `current.snapshot_file`
- `current.manifest_file`

## 已实现

Control Plane 现在会在写入或发布 artifact 前拒绝不安全 artifact 引用：

- 拒绝绝对路径
- 拒绝 `..` 路径穿越
- 文件引用必须留在 artifact 目录内

Data Plane 在解析 distributed snapshot 时也执行同样规则：

- `current.json` 引用必须留在 distribution 目录内
- `manifest.json` 的 snapshot 引用必须留在 artifact 目录内

直接传入 `API2AGENT_SNAPSHOT=<snapshot.json>` 的路径行为不变。这个 guard 只作用于 distribution metadata 内的引用。

## 已验证流程

cross-plane dogfood 现在会验证：

1. v8 artifact 使用 `manifest.snapshot_file="../snapshot.json"`。
2. Control Plane 在推进 `current.json` 前拒绝 v8 publish。
3. v9 正常发布。
4. 随后把 distribution `current.json` 修改为 `snapshot_file="../outside.json"`。
5. Data Plane reload 拒绝 unsafe pointer path，并保持 v2 active。

## 检查项

```json
{
  "unsafe_manifest_path_publish_rejected": true,
  "unsafe_manifest_path_publish_did_not_advance_current": true,
  "unsafe_pointer_path_reload_rejected": true,
  "unsafe_pointer_path_reload_kept_v2": true,
  "unsafe_pointer_path_reload_audit_event_recorded": true,
  "health_after_unsafe_pointer_path_reload_still_v2": true
}
```

## 结果

Snapshot Artifact Path Safety Guard v0 通过。

Snapshot distribution 现在会在读取或发布引用文件前拒绝路径穿越。
