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
4. dogfood 会先把 `current.json` 指向缺失的 snapshot，并调用 `POST /v1/admin/reload-snapshot`。
5. 失败 reload 返回 `SNAPSHOT_RELOAD_FAILED`、`reloaded=false` 和 `kept_snapshot_version=snapshot_control_plane_public_ip_v1`。
6. 写入 failed `snapshot_reload_event`。
7. `/healthz` 仍然返回 `snapshot_control_plane_public_ip_v1`。
8. Control Plane 导出并发布 snapshot v2 到同一个 distribution 目录。
9. Data Plane 接收 `POST /v1/admin/reload-snapshot`。
10. active snapshot 被替换前，先写入 successful `snapshot_reload_event`。
11. incompatible v3 snapshot 声明 `api2agent.protocol.v9` 并被拒绝。
12. `/healthz` 仍然停留在 `snapshot_control_plane_public_ip_v2`。
13. `/v1/execute` 成功。
14. RoutingDecision 和 UsageEvent 记录 `snapshot_control_plane_public_ip_v2`。

## 检查项

```json
{
  "health_before_reload_snapshot_version_matches": true,
  "failed_reload_rejected": true,
  "failed_reload_kept_previous_snapshot": true,
  "health_after_failed_reload_still_v1": true,
  "failed_reload_audit_event_recorded": true,
  "reload_response_success": true,
  "reload_previous_snapshot_version_matches": true,
  "reload_snapshot_version_matches": true,
  "successful_reload_audit_event_recorded": true,
  "incompatible_reload_rejected": true,
  "incompatible_reload_kept_v2": true,
  "incompatible_reload_audit_event_recorded": true,
  "health_after_incompatible_reload_still_v2": true,
  "distribution_current_after_reload_points_to_v2": true,
  "distribution_v2_artifact_snapshot_exists": true,
  "routing_snapshot_version_matches": true
}
```

## 结果

Snapshot Refresh / Reload Policy v0 通过。

这让生产默认行为保持保守，同时为 local Control Plane / Data Plane dogfood 提供了明确的 reload 机制。

Reload Failure Semantics v0 也通过：失败 reload 不会替换 active snapshot，并且失败响应是机器可读、可重试的。

Reload Audit Events v0 也通过：失败和成功 reload attempts 都会写入 append-only event stream。

Snapshot Version Compatibility Guard v0 也通过：不兼容 schema version 会被拒绝，并且不会替换 active snapshot。
