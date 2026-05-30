# Go Data Plane Snapshot Refresh / Reload Dogfood 报告

日期：2026-05-30

## 目标

验证由 Go Control Plane 分发的 snapshots 的第一版 reload policy。

## Policy v0

默认行为保持为：

```text
startup_only
```

也就是说 Data Plane 在启动时加载 `API2AGENT_SNAPSHOT`，不会自动刷新。

本地手动 reload 可以通过下面的环境变量开启：

```text
API2AGENT_SNAPSHOT_RELOAD_POLICY=manual
```

开启后，Data Plane 暴露：

```http
POST /v1/admin/reload-snapshot
```

如果配置了 `API2AGENT_PROJECT_KEY`，这个 endpoint 需要和 `/v1/execute` 一样的 bearer token。

## 已验证流程

cross-plane dogfood 现在会验证：

1. Control Plane 导出并发布 snapshot v1 到 local distribution 目录。
2. Data Plane 使用 `API2AGENT_SNAPSHOT=<distribution_dir>` 启动。
3. `/healthz` 返回 `snapshot_control_plane_public_ip_v1`。
4. Control Plane 导出并发布 snapshot v2 到同一个 distribution 目录。
5. Data Plane 接收 `POST /v1/admin/reload-snapshot`。
6. `/healthz` 返回 `snapshot_control_plane_public_ip_v2`。
7. `/v1/execute` 成功。
8. RoutingDecision 和 UsageEvent 记录 `snapshot_control_plane_public_ip_v2`。

## 检查项

```json
{
  "health_before_reload_snapshot_version_matches": true,
  "reload_response_success": true,
  "reload_previous_snapshot_version_matches": true,
  "reload_snapshot_version_matches": true,
  "distribution_current_after_reload_points_to_v2": true,
  "distribution_v2_artifact_snapshot_exists": true,
  "routing_snapshot_version_matches": true
}
```

## 结果

Snapshot Refresh / Reload Policy v0 通过。

这让生产默认行为保持保守，同时为 local Control Plane / Data Plane dogfood 提供了明确的 reload 机制。
