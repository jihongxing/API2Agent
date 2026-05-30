# Go Data Plane Snapshot Reload Audit Events Dogfood 报告

日期：2026-05-31

## 目标

验证 manual snapshot reload 在影响 Data Plane execution 前是可审计的。

## 已实现

Data Plane 现在会为以下情况写入 `snapshot_reload_event`：

- failed reload attempts
- successful reload attempts

成功 reload 语义：

- load candidate snapshot
- 写入 `outcome=success` 的 `snapshot_reload_event`
- 替换 active snapshot
- 返回 reload response

失败 reload 语义：

- 保持 previous snapshot active
- 写入 `outcome=failure` 的 `snapshot_reload_event`
- 返回 `SNAPSHOT_RELOAD_FAILED`

## Audit 字段

event records 包含：

- `id`
- `schema_version`
- `outcome`
- `reload_policy`
- `previous_snapshot_version`
- success 时的 `target_snapshot_version`
- failure 时的 `kept_snapshot_version`
- `snapshot_path`
- `previous_resolved_to`
- `target_resolved_to`
- `error`
- `event_sequence_id`
- `created_at`

## 已验证流程

dogfood 验证了下面的事件顺序：

```text
snapshot_reload_event  # failed reload, v1 retained
snapshot_reload_event  # successful reload, v2 loaded
request_context
routing_decision
usage_event
decision_log
```

## 检查项

```json
{
  "failed_reload_audit_event_recorded": true,
  "successful_reload_audit_event_recorded": true,
  "event_order_is_graph": true
}
```

## 结果

Snapshot Reload Audit Events v0 通过。

reload 管理动作现在和 execution events 共享同一个 append-only event stream。
