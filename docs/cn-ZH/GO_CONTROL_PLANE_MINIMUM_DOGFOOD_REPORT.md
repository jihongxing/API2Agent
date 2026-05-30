# Go Control Plane Minimum Dogfood 报告

日期：2026-05-30

## 目标

验证新的最小 Go Control Plane 是否可以导出 versioned routing snapshot，并且现有 Go Data Plane 可以在不修改 snapshot loader 的情况下直接消费。

本报告也验证 invalid registry relationships 会在 snapshot export 前被拒绝。

## 设置

Control Plane registry 包含：

- project model
- API key model
- capability registry model
- provider registry model
- credential metadata model
- routing policy
- snapshot export metadata

Data Plane：

- 现有 `api2agent-dataplane`
- 同一个 `/v1/execute` path
- 同一套 Protocol v0.2 execution graph

## Dogfood 命令

```bash
python scripts/go_control_plane_minimum_dogfood.py \
  --output .dogfood/go-control-plane-minimum/report.json
```

脚本会构建：

- `api2agent-controlplane`
- `api2agent-dataplane`
- `api2agent-snapshot-check`

## 观察结果

Control Plane 导出了一个 snapshot：

- `snapshot_version = snapshot_control_plane_public_ip_v1`
- `snapshot_source = pull`
- `snapshot_version_policy = explicit`
- `registry_fingerprint = sha256:<hash>`
- 一个 capability
- 一个 active provider
- 一个 credential metadata entry

随后 Data Plane：

- 通过 `api2agent-snapshot-check` 接受了导出的 snapshot
- 加载了导出的 snapshot
- 在 `/healthz` 返回同一个 snapshot version
- 执行了 `network.public_ip.get`
- 返回了本地 provider 的 fixed public IP
- 写入了有效 execution graph

Control Plane 也拒绝了一个 API key 引用 missing project 的 invalid registry：

```text
api_key "key_local_dev" references unknown project "missing_project"
```

## 结果

Go Control Plane Minimum v0 通过。

这证明了 Phase 6 的第一条边界：

```text
Control Plane registry -> versioned snapshot export -> Data Plane consumption
```

## 检查项

```json
{
  "control_plane_export_success": true,
  "snapshot_check_passed": true,
  "snapshot_check_has_registry_fingerprint": true,
  "snapshot_check_has_explicit_version_policy": true,
  "invalid_registry_rejected": true,
  "health_snapshot_version_matches": true,
  "response_success": true,
  "response_ip_matches_provider": true,
  "usage_has_attempt_id": true,
  "routing_snapshot_version_matches": true,
  "event_order_is_graph": true
}
```

## 非目标

本切片不包含：

- hosted database
- hosted credential vault
- billing
- marketplace
- multi-region hosted proxy
- dashboard
