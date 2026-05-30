# Go Control Plane Service API 阶段收口

日期：2026-05-31

状态：已完成

判断：local Go Control Plane service API 里程碑已经收口。API2Agent 可以进入 hosted persistence design，但还不应该直接开始 database implementation。

## 1. 里程碑范围

这个里程碑收口的是第一版 local Control Plane service boundary：

```text
file registry
  -> Control Plane service
  -> registry validation
  -> artifact export
  -> distribution publish
  -> current pointer read
```

本阶段不做：

- registry mutation APIs
- Postgres persistence
- remote object storage
- distributed publish locks
- Control Plane admin audit log
- per-project hosted authorization
- credential vault
- billing
- marketplace

## 2. 已完成能力

Go Control Plane service 现在支持：

- `api2agent-controlplane serve`
- public `GET /healthz`
- `/v1/admin/*` 的 admin bearer token guard
- `POST /v1/admin/registry/validate`
- `POST /v1/admin/snapshots/export-artifact`
- `POST /v1/admin/distribution/publish`
- `GET /v1/admin/distribution/current`
- 通过现有 registry exporter 做 HTTP artifact export
- 通过现有 atomic local publisher 做 HTTP distribution publish
- duplicate publish 会在推进 `current.json` 前被拒绝
- service dogfood 覆盖 HTTP validate -> export -> publish -> current

## 3. 证据

最近实现提交：

```text
64085da Add control plane service publish endpoint
839ef8e Add control plane service API skeleton
f4b56ae Document snapshot distribution closeout
efa0dd1 Add snapshot distribution atomic publish guard
```

Dogfood 证据：

- `docs/cn-ZH/GO_CONTROL_PLANE_SERVICE_API_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_SNAPSHOT_DISTRIBUTION_CLOSEOUT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_SNAPSHOT_ATOMIC_PUBLISH_DOGFOOD_REPORT.md`

当前验证基线：

```text
go test ./...
python -m pytest
python scripts/go_control_plane_service_api_dogfood.py --output .dogfood/go-control-plane-service-api/report.json
python scripts/go_control_plane_minimum_dogfood.py --output .dogfood/go-control-plane-minimum/report.json
```

## 4. 退出标准检查

| 标准 | 状态 | 说明 |
|---|---|---|
| Control Plane 可以作为 local HTTP service 运行 | 通过 | `serve` 可以基于现有 file registry 启动。 |
| Health endpoint 是 public | 通过 | `/healthz` 报告 service、protocol、registry source 和 distribution metadata。 |
| Admin endpoints 有 guard | 通过 | 未认证 admin calls 返回 `AUTH_ERROR`。 |
| Registry validation 可以通过 HTTP 执行 | 通过 | service 返回 validation counts 和 registry fingerprint。 |
| Artifact export 可以通过 HTTP 执行 | 通过 | service 通过现有 exporter code 写入 `snapshot.json` 和 `manifest.json`。 |
| Distribution publish 可以通过 HTTP 执行 | 通过 | service 通过现有 atomic publish code 发布 artifact。 |
| Duplicate publish 是安全的 | 通过 | duplicate publish 返回 `DISTRIBUTION_ARTIFACT_EXISTS`，并保持 `current.json` 不变。 |
| Distribution state 可读取 | 通过 | service 返回 current distribution pointer。 |
| 现有 CLI 和 cross-plane dogfood 保持稳定 | 通过 | 原有 Control Plane minimum dogfood 仍然通过。 |

## 5. Hosted Persistence Readiness

已具备：

- Control Plane 已经有真实 service boundary。
- Registry loading 已经位于 `registry.Store` 后面。
- Snapshot export semantics 不依赖 file store。
- Local artifact 和 distribution semantics 已经足够稳定，可以在后续 storage backends 中保留。
- Admin endpoints 已经有第一版 auth guard。

尚未具备：

- 没有 Postgres schema。
- 没有 migration plan。
- 没有 registry reads、artifact exports 和 publish records 的 transaction model。
- 没有持久化的 Control Plane admin audit events。
- 没有 registry mutation API。
- 没有超出 local admin token 的 per-project authorization model。
- 没有 remote artifact storage 或 compare-and-swap publish protocol。
- 没有 credential vault。

## 6. 阶段判断

API2Agent 不应该直接跳到 Postgres implementation。

下一阶段应该开始：

```text
Go Control Plane Persistent Registry Store Design v0
```

这是 design task，不是 database implementation task。

## 7. 建议的下一项入口任务

范围：

1. 定义 persistent registry store contract。
2. 起草第一版 Postgres table model，覆盖 projects、API keys、capabilities、providers、credential metadata、routing policy、snapshot metadata、artifact publications 和 admin audit events。
3. 定义 registry load、artifact export 和 distribution publish 的 transaction boundaries。
4. 定义 database-backed registry state 的 versioning 和 fingerprint rules。
5. 定义从 file registry 到 persistent registry 的 migration 和 dual-store strategy。
6. 保持 snapshot export output 与 file-store path 完全兼容。

退出标准：

- Persistent store design 有英文和中文文档。
- Database implementation scope 在写代码前明确。
- Snapshot export compatibility rules 被保留。
- 不包含 hosted deployment、vault、billing 或 marketplace 工作。

## 8. 战略判断

项目已经从 local Control Plane CLI 进入 local Control Plane service。

下一步最重要的问题已经不是：

```text
Can Control Plane operations be exposed through HTTP?
```

这件事已经被证明了。

下一步的问题是：

```text
Can API2Agent persist Control Plane state without changing the Data Plane snapshot contract?
```

这才是正确的下一阶段。
