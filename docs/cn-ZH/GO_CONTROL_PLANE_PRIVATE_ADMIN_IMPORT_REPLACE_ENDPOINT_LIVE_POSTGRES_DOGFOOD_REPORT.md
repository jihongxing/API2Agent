# Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0

日期：2026-05-31

状态：complete

## 决策

private admin import/replace endpoint 已通过 live Postgres dogfood。

推荐下一项任务：

```text
Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0
```

## 范围

这次 dogfood 验证真实 service path：

```text
HTTP admin endpoint
  -> Go Control Plane service
  -> registry.ReplacePersistentRegistry
  -> live Postgres persistent registry tables
  -> validation/export after replacement
  -> persistent audit evidence
```

它不测试 public CRUD、provider onboarding、credential vault、billing、marketplace 或 automatic snapshot reload。

## 环境

- 使用 `podman` 启动 Postgres-compatible database
- 从 `services/control-plane/schema/postgres/001_persistent_registry_store.sql` 应用 schema
- service 使用 `--registry-store postgres` 启动
- admin auth 使用 `Authorization: Bearer dogfood-token`
- 被测 endpoint：

```text
POST /v1/admin/registry/import-replace
```

## Dogfood Steps

1. 用 podman 启动 live Postgres。
2. 应用 persistent registry schema。
3. seed baseline `network.public_ip.get` registry。
4. build 并启动连接 Postgres 的 Go Control Plane service。
5. 用 changed registry 调用 `POST /v1/admin/registry/import-replace`。
6. 用同一个 registry 再调用一次 endpoint，验证 no-op behavior。
7. replacement 后调用 service registry validation。
8. replacement 后通过 service export snapshot artifact。
9. 验证 exported snapshot 包含替换后的 provider。
10. 断言 persistent audit counts。

## 观测结果

```json
{
  "status": "passed",
  "replace_status": 201,
  "replace_noop": false,
  "noop_status": 200,
  "second_noop": true,
  "snapshot_version": "snapshot_http_import_replace_live_v1",
  "provider_id": "httpbin_public_ip_v1",
  "provider_base_url": "https://httpbin.org",
  "audit_counts": {
    "registry_revisions": 3,
    "admin_audit_events": 4,
    "providers": 1
  }
}
```

replacement 后的 registry fingerprint：

```text
sha256:3aa1851fde7accf093721be5a10f43229d54894625962c364fbd603a880a5cf5
```

## 验收标准复盘

| Criterion | Status |
| --- | --- |
| Live Postgres service starts with Postgres registry store | passed |
| Endpoint accepts changed registry through HTTP | passed |
| Changed registry returns `201` | passed |
| Changed registry returns `noop=false` | passed |
| Repeated same registry returns `200` | passed |
| Repeated same registry returns `noop=true` | passed |
| Service validation sees replaced registry | passed |
| Service export sees replaced registry | passed |
| Exported snapshot provider is `httpbin_public_ip_v1` | passed |
| Persistent registry revisions are asserted | passed |
| Persistent admin audit events are asserted | passed |
| No public CRUD API is introduced | passed |

## Audit Interpretation

预期 counts：

- `registry_revisions=3`
  - seed
  - successful import/replace
  - replacement 后的 service export
- `admin_audit_events=4`
  - successful import/replace
  - successful import/replace no-op
  - registry validation
  - artifact export
- `providers=1`
  - full replacement 后只保留一个 active provider row

## 验证

Dogfood command：

```text
python scripts/go_control_plane_import_replace_endpoint_dogfood.py --output tmp/go_control_plane_import_replace_endpoint_dogfood.json
```

Unit tests：

```text
go test ./...
```

执行目录：

```text
services/control-plane
```

## 保持的 Non-Goals

- no public CRUD registry API
- no provider self-onboarding
- no marketplace
- no billing or settlement
- no credential vault
- no plaintext secret storage
- no workflow engine
- no automatic snapshot publish or Data Plane reload
- no Data Plane reads from mutable Control Plane tables

