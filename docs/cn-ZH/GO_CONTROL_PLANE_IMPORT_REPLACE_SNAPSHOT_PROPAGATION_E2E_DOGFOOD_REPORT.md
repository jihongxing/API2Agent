# Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0

日期：2026-05-31

状态：complete

## 决策

import/replace snapshot propagation E2E dogfood 已通过。

推荐下一项任务：

```text
Go Control Plane Import/Replace Snapshot Propagation Closeout + Phase Review v0
```

## 范围

这次 dogfood 验证完整的手动 propagation sequence：

```text
HTTP import/replace
  -> snapshot artifact export
  -> distribution publish
  -> Data Plane reload
  -> Data Plane execution uses replaced provider
```

这仍然是 operator-sequenced dogfood。它不引入 automatic publish、automatic reload、public CRUD、provider onboarding、credential vault、billing、marketplace 或 workflow runtime scope。

## 环境

- 使用 `podman` 启动 Postgres-compatible database
- 从 `services/control-plane/schema/postgres/001_persistent_registry_store.sql` 应用 schema
- Control Plane service 使用 `--registry-store postgres` 启动
- Data Plane 使用 `API2AGENT_SNAPSHOT=<distribution_dir>` 启动
- Data Plane reload policy 设置为 `API2AGENT_SNAPSHOT_RELOAD_POLICY=manual`
- replacement provider 使用本地 httpbin-like server，返回 `{"origin": "203.0.113.88"}`

## Dogfood Steps

1. 用 podman 启动 live Postgres。
2. 应用 persistent registry schema。
3. seed 初始 `network.public_ip.get` registry，provider 为 `ipify_public_ip_v1`。
4. 启动连接 Postgres 的 Go Control Plane service。
5. export 并 publish 初始 snapshot distribution。
6. 让 Go Data Plane 从 distribution directory 启动。
7. 验证 Data Plane 初始加载 `snapshot_propagation_ipify_v1`。
8. 用 `httpbin_public_ip_v1` replacement registry 调用 `POST /v1/admin/registry/import-replace`。
9. export 并 publish replacement snapshot。
10. 在 Data Plane 上调用 `POST /v1/admin/reload-snapshot`。
11. 通过 Data Plane 执行 `network.public_ip.get`。
12. 验证 execution output、usage event、decision log、reload event 和 persistent audit counts。

## 观测结果

```json
{
  "status": "passed",
  "initial_published_snapshot_version": "snapshot_propagation_ipify_v1",
  "replacement_published_snapshot_version": "snapshot_propagation_httpbin_v2",
  "reload_response": {
    "previous_snapshot_version": "snapshot_propagation_ipify_v1",
    "reloaded": true,
    "snapshot_version": "snapshot_propagation_httpbin_v2"
  },
  "execute_response": {
    "output": {
      "ip": "203.0.113.88"
    },
    "success": true
  },
  "usage_provider_id": "httpbin",
  "usage_snapshot_version": "snapshot_propagation_httpbin_v2",
  "decision_selected_provider_id": "httpbin_public_ip_v1",
  "reload_event_count": 1,
  "audit_counts": {
    "registry_revisions": 4,
    "admin_audit_events": 5,
    "providers": 1,
    "snapshot_artifact_publications": 2
  }
}
```

## 验收标准复盘

| Criterion | Status |
| --- | --- |
| HTTP import/replace changes the persistent registry provider | passed |
| Control Plane exports the replaced snapshot | passed |
| Control Plane publishes the replaced snapshot distribution | passed |
| Data Plane manually reloads the published distribution | passed |
| Data Plane execution uses the replaced provider | passed |
| Execution output comes from the replacement provider | passed |
| Usage event attributes the replaced provider | passed |
| Decision log selects `httpbin_public_ip_v1` | passed |
| Snapshot reload audit event is emitted | passed |
| Persistent audit counts are asserted | passed |
| Snapshot export/publish/reload remain manually sequenced | passed |
| No public CRUD, vault, billing, marketplace, or workflow scope is introduced | passed |

## Audit Interpretation

预期 persistent evidence：

- `registry_revisions=4`
  - initial seed
  - initial service export
  - successful import/replace
  - replacement service export
- `snapshot_artifact_publications=2`
  - initial distribution publish
  - replacement distribution publish
- `admin_audit_events=5`
  - initial artifact export
  - initial distribution publish
  - successful import/replace
  - replacement artifact export
  - replacement distribution publish
- `providers=1`
  - full replacement 后只保留一个 active provider row

预期 Data Plane evidence：

- `snapshot_reload_event`
- `request_context`
- `routing_decision`
- `usage_event`
- `decision_log`

## 验证

Dogfood command：

```text
python scripts/go_control_plane_import_replace_snapshot_propagation_dogfood.py --output tmp/go_control_plane_import_replace_snapshot_propagation_dogfood.json
```

Dogfood status：

```text
passed
```

## 保持的 Non-Goals

- no public CRUD registry API
- no provider self-onboarding
- no marketplace
- no billing or settlement
- no credential vault
- no plaintext secret storage
- no workflow engine
- no automatic snapshot publish
- no automatic Data Plane reload
- no Data Plane reads from mutable Control Plane tables
