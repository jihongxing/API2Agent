# Go Data Plane Snapshot Version Compatibility Guard Dogfood 报告

日期：2026-05-31

## 目标

防止 Data Plane 加载或 reload 声明了不兼容 protocol schema version 的 snapshots。

## 已实现

Control Plane 导出的 snapshots 现在包含：

```json
{
  "metadata": {
    "schema_version": "api2agent.protocol.v0.2"
  }
}
```

Data Plane snapshot loading 会检查：

- 如果 `metadata.schema_version` 缺失，legacy local snapshots 仍然允许加载
- 如果 `metadata.schema_version` 存在，必须等于 `api2agent.protocol.v0.2`
- incompatible snapshots 会在 startup load、snapshot check 和 manual reload 时被拒绝

## 已验证流程

cross-plane dogfood 现在会验证：

1. v1 distribution 正常加载。
2. 损坏的 `current.json` reload 失败并保持 v1。
3. v2 distribution reload 成功。
4. v3 distribution 被修改为声明 `api2agent.protocol.v9`。
5. reload 拒绝 v3 incompatible snapshot。
6. `/healthz` 仍然停留在 v2。
7. execution 成功，并且 RoutingDecision 和 UsageEvent 记录 v2。

## 检查项

```json
{
  "snapshot_check_schema_version_matches": true,
  "incompatible_reload_rejected": true,
  "incompatible_reload_kept_v2": true,
  "incompatible_reload_audit_event_recorded": true,
  "health_after_incompatible_reload_still_v2": true,
  "routing_snapshot_version_matches": true
}
```

## 结果

Snapshot Version Compatibility Guard v0 通过。

这可以防止 distributed snapshot 静默跨过 Data Plane 无法理解的 protocol boundary。
