# Go Control Plane Minimum Dogfood 报告

日期：2026-05-30

## 目标

验证新的最小 Go Control Plane 是否可以导出 versioned routing snapshot artifact，发布到本地 distribution 目录，并让现有 Go Data Plane 消费 distribution `current.json` 指针。

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

Control Plane 导出了一个 artifact 目录：

- `snapshot.json`
- `manifest.json`

随后 Control Plane 将 artifact 发布到 distribution 目录：

- `current.json`
- `artifacts/snapshot_control_plane_public_ip_v1/snapshot.json`
- `artifacts/snapshot_control_plane_public_ip_v1/manifest.json`

dogfood 随后会将 v2 artifact 发布到同一个 distribution，并触发 Data Plane manual reload。

manifest 记录了：

- `snapshot_version = snapshot_control_plane_public_ip_v1`
- `snapshot_source = pull`
- `snapshot_version_policy = explicit`
- `registry_fingerprint = sha256:<hash>`
- `artifact_version = api2agent.snapshot_artifact.v0`
- `registry_store = file`
- `snapshot_file = snapshot.json`
- validation summary 中 `valid = true`

snapshot 包含：

- 一个 capability
- 一个 active provider
- 零个 credential metadata entries

随后 Data Plane：

- 验证 manifest 引用了导出的 snapshot
- 验证 manifest registry fingerprint 与 snapshot compatibility checker 一致
- 通过 `api2agent-snapshot-check` 接受了 distribution 目录
- 将 `current.json` 解析到已发布 artifact snapshot
- 通过 `API2AGENT_SNAPSHOT=<distribution_dir>` 加载了 distributed snapshot
- 通过 `POST /v1/admin/reload-snapshot` 从 v1 reload 到 v2
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
Control Plane registry -> snapshot artifact export -> local distribution current pointer -> compatibility gate -> Data Plane consumption
```

## 检查项

```json
{
  "control_plane_export_success": true,
  "artifact_manifest_exists": true,
  "manifest_references_snapshot": true,
  "manifest_fingerprint_matches_snapshot_check": true,
  "manifest_validation_valid": true,
  "distribution_current_exists": true,
  "distribution_current_points_to_snapshot": true,
  "distribution_current_fingerprint_matches_manifest": true,
  "distribution_artifact_snapshot_exists": true,
  "health_before_reload_snapshot_version_matches": true,
  "reload_response_success": true,
  "reload_previous_snapshot_version_matches": true,
  "reload_snapshot_version_matches": true,
  "distribution_current_after_reload_points_to_v2": true,
  "distribution_v2_artifact_snapshot_exists": true,
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
