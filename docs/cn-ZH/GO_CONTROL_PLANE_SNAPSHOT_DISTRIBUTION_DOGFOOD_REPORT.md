# Go Control Plane Snapshot Distribution Dogfood 报告

日期：2026-05-30

## 目标

验证第一条 local snapshot distribution 边界：

```text
Control Plane artifact -> local distribution current pointer -> Data Plane snapshot load
```

## 范围

这是 local stub，不包含 hosted distribution、remote pull、push delivery、object storage、signing 或 multi-region propagation。

## 已实现

- `api2agent-controlplane publish-artifact`
- local distribution layout：
  - `current.json`
  - `artifacts/<snapshot_version>/snapshot.json`
  - `artifacts/<snapshot_version>/manifest.json`
- Data Plane snapshot resolver 支持：
  - 裸 snapshot 文件路径
  - 包含 `current.json` 的 distribution 目录
  - 直接传入 `current.json` 路径

## 已验证

dogfood 脚本现在会：

- 导出 snapshot artifact
- 将 artifact 发布到 local distribution 目录
- 对 distribution 目录运行 `api2agent-snapshot-check`
- 使用 `API2AGENT_SNAPSHOT=<distribution_dir>` 启动 Go Data Plane
- 将第二个 artifact version 发布到同一个 distribution 目录
- 手动 reload Data Plane snapshot
- 验证 `/v1/execute` 可以通过 distributed snapshot 成功执行

## 检查项

```json
{
  "distribution_current_exists": true,
  "distribution_current_points_to_snapshot": true,
  "distribution_current_fingerprint_matches_manifest": true,
  "distribution_artifact_snapshot_exists": true,
  "reload_response_success": true,
  "distribution_current_after_reload_points_to_v2": true,
  "snapshot_check_passed": true,
  "health_snapshot_version_matches": true,
  "response_success": true
}
```

## 结果

Control Plane Snapshot Distribution Stub v0 通过。

项目现在具备了 Control Plane artifact publishing 和 Data Plane snapshot consumption 之间的 local distribution contract。
