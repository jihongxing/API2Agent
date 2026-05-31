# Go Control Plane Private Admin Import/Replace Endpoint Closeout + Phase Review v0

日期：2026-05-31

状态：complete

## 决策

private admin import/replace endpoint milestone 可以关闭。

推荐下一项任务：

```text
Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0
```

下一项任务应该验证 registry mutation 之后的完整 operator sequence：

```text
HTTP import/replace
  -> snapshot artifact export
  -> distribution publish
  -> Data Plane reload
  -> Data Plane execution uses replaced provider
```

这仍然是 dogfood 和 propagation validation。它不是 public CRUD、marketplace、billing、vault 或 provider onboarding。

## 现在已经完成了什么

### Endpoint Design

已完成：

- private admin method/path
- wrapper request body
- 必需 `X-Request-ID`
- 必需 `Idempotency-Key`
- optional actor identity
- 2 MiB request-size limit
- stable response shape
- stable error mapping
- 通过 registry 层完成 audit mapping
- 明确 snapshot boundary

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_DESIGN.md`

### Endpoint Implementation

已完成：

- `POST /v1/admin/registry/import-replace`
- 很窄的 `RegistryImportReplacer` seam
- `serve` 中只为 Postgres 注入 mutation wiring
- FileStore/unconfigured mutation rejection
- request/idempotency header enforcement
- wrapper request decoding
- `dry_run=true` rejection
- `RegistryMutationError` HTTP mapping
- request validation、status codes、options propagation 和 error mapping 的 unit tests

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_IMPLEMENTATION_REPORT.md`

### Live Postgres Dogfood

已通过 podman 完成：

- service 使用 `--registry-store postgres` 启动
- changed-registry HTTP import/replace 返回 `201`
- same-registry HTTP import/replace 返回 `200`
- service validation 看到了替换后的 registry
- service artifact export 看到了替换后的 registry
- exported snapshot provider 是 `httpbin_public_ip_v1`
- persistent audit counts 已断言

观测值：

```json
{
  "replace_status": 201,
  "replace_noop": false,
  "noop_status": 200,
  "second_noop": true,
  "snapshot_version": "snapshot_http_import_replace_live_v1",
  "provider_id": "httpbin_public_ip_v1",
  "audit_counts": {
    "registry_revisions": 3,
    "admin_audit_events": 4,
    "providers": 1
  }
}
```

参考：

- `docs/cn-ZH/GO_CONTROL_PLANE_PRIVATE_ADMIN_IMPORT_REPLACE_ENDPOINT_LIVE_POSTGRES_DOGFOOD_REPORT.md`

## 验收标准复盘

| Criterion | Status |
| --- | --- |
| Private admin endpoint contract documented | passed |
| Endpoint implemented behind admin auth | passed |
| Postgres-only mutation boundary enforced | passed |
| FileStore behavior unchanged | passed |
| `X-Request-ID` required | passed |
| `Idempotency-Key` required | passed |
| Wrapper request body implemented | passed |
| Request-size limit implemented | passed |
| Changed registry returns `201` | passed |
| Same-fingerprint no-op returns `200` | passed |
| Registry-layer audit remains authoritative | passed |
| Live Postgres HTTP replacement verified | passed |
| Service validation/export sees replaced registry | passed |
| Public CRUD remains out of scope | passed |
| Snapshot publish/reload remains separate | passed |

## Closeout 判断

这个 milestone 已完成。

项目现在已经有一条 controlled private write-side path，可以通过 service API 替换 persistent registry。

这很关键，因为 Control Plane 不再只是 persistent registry state 的 read-only surface；但 write boundary 仍然很窄、可审计，并且可以通过再次替换完整 registry document 来恢复。

## Remaining Risks

### Hosted Auth 仍然只是 Local-Admin 级别

当前 admin auth 是 bearer-token based，适合 local/private dogfood。

它还不是 hosted multi-admin identity model。

### Idempotency Key 必需但没有 Result Cache

endpoint 要求 `Idempotency-Key`，但 v0 idempotency 仍然基于 fingerprint。

未来 hosted mutation APIs 可能需要 request/idempotency table 来检测 key 冲突复用。

### Full Registry Replacement 很钝

这是 v0 的刻意设计。

Granular CRUD 继续 deferred，直到 full replacement path 证明稳定。

### Snapshot Propagation 仍然是手动的

Import/replace 不 publish 或 reload snapshots。

下一项最有价值的证明，是对完整手动 propagation sequence 做 E2E dogfood。

### Large Registry Limit 偏保守

2 MiB HTTP limit 足够当前 dogfood。

未来大型 hosted registries 可能需要 configurable limit 或 artifact-based upload。

## 仍然不允许

不要启动：

- public CRUD registry APIs
- provider self-onboarding
- marketplace provider submission
- credential vault writes
- plaintext secret storage
- billing or settlement state
- workflow engine support
- 没有 explicit propagation design 的 automatic publish/reload

## 下一项任务理由

下一项最高信号任务是：

```text
Go Control Plane Import/Replace Snapshot Propagation E2E Dogfood v0
```

原因：

- write-side endpoint 已证明
- snapshot export 和 publish 已存在
- Data Plane manual reload 已存在
- 缺失的证明是：changed registry 能传播到 Data Plane execution behavior

期望证明：

- HTTP import/replace 把 provider 从 `ipify_public_ip_v1` 换成 `httpbin_public_ip_v1`
- Control Plane export 并 publish 新 snapshot
- Data Plane reload distribution
- Data Plane execution records 使用 `httpbin_public_ip_v1`

## 验证

已通过：

```text
go test ./...
```

执行目录：

```text
services/control-plane
```

