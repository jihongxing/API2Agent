# Go Control Plane Snapshot Distribution 阶段收口

日期：2026-05-31

状态：已完成

判断：本地 Go Control Plane snapshot distribution 里程碑已经收口。API2Agent 可以从 CLI-only Control Plane operations 进入 local Control Plane service boundary。

## 1. 里程碑范围

这个里程碑收口的是本地 snapshot distribution 链路：

```text
registry.json
  -> routing snapshot
  -> snapshot artifact
  -> local distribution/current.json
  -> Go Data Plane startup or manual reload
```

本阶段不做：

- hosted SaaS
- remote object storage distribution
- distributed locking 或 multi-writer publish
- Postgres-backed registry persistence
- KMS-backed credential vault
- billing 或 marketplace flows
- public provider onboarding

## 2. 已完成能力

Go Control Plane 和 Go Data Plane 现在支持：

- 本地 Control Plane registry models，包含 projects、API keys、capabilities、providers、credential metadata、routing policy 和 snapshot metadata
- `registry.Store` 作为 Control Plane state source boundary
- 本地 file-backed registry loading
- export 前 registry validation
- Data Plane-compatible routing snapshot export
- 通过 Go Data Plane checker 做 snapshot compatibility checking
- explicit snapshot version policy 和 deterministic registry fingerprints
- 带 `snapshot.json` 和 `manifest.json` 的 snapshot artifact export
- artifact write 和 publish 前的 manifest validation
- 使用 `current.json` 和 versioned artifact directories 的本地 snapshot distribution
- Data Plane 可以从 bare snapshot file、distribution directory 或 direct `current.json` path 加载
- manual Data Plane snapshot reload policy
- reload failure semantics，失败时保留 previous serving snapshot
- durable event stream 中的 reload audit events
- schema version compatibility checks
- strict Control Plane metadata requirements
- manifest、pointer、snapshot metadata 和 content digest consistency checks
- artifact 和 distribution metadata 的 path safety checks
- 通过 temporary artifact directories 和 temporary `current.json` writes 实现 local atomic publish behavior
- duplicate `snapshot_version` 会在推进 `current.json` 前被拒绝

## 3. 证据

最近实现提交：

```text
efa0dd1 Add snapshot distribution atomic publish guard
f317e55 Add snapshot artifact path safety guard
9e8c586 Add snapshot artifact content digest guard
01553f1 Add snapshot manifest consistency guard
52fed35 Add snapshot strict metadata requirement
0245963 Add snapshot version compatibility guard
cc9cb82 Add snapshot reload audit events
a6ccf79 Add snapshot reload failure semantics
191618e Add data plane snapshot reload policy
6a88b1e Add control plane snapshot distribution stub
90e02c3 Add control plane snapshot export artifact
5114862 Add control plane snapshot versioning metadata
6ae8df9 Add control plane registry store
78ca3f6 Add control plane snapshot compatibility gate
e19af2b Harden control plane registry validation
e287ac5 Implement Go control plane minimum
```

Dogfood 证据：

- `docs/cn-ZH/GO_CONTROL_PLANE_MINIMUM_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_SNAPSHOT_DISTRIBUTION_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_RELOAD_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_RELOAD_AUDIT_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_COMPATIBILITY_GUARD_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_STRICT_METADATA_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_MANIFEST_CONSISTENCY_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_CONTENT_DIGEST_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_DATAPLANE_SNAPSHOT_PATH_SAFETY_DOGFOOD_REPORT.md`
- `docs/cn-ZH/GO_CONTROL_PLANE_SNAPSHOT_ATOMIC_PUBLISH_DOGFOOD_REPORT.md`

当前验证基线：

```text
go test ./...
python -m pytest
python scripts/go_control_plane_minimum_dogfood.py --output .dogfood/go-control-plane-minimum/report.json
```

## 4. 退出标准检查

| 标准 | 状态 | 说明 |
|---|---|---|
| Control Plane 可以生成 Data Plane-compatible snapshot | 通过 | `export-snapshot` 输出可以被 `api2agent-snapshot-check` 和 Go Data Plane 接受。 |
| Snapshot artifacts 明确且可审计 | 通过 | Artifacts 包含 `snapshot.json`、`manifest.json`、registry fingerprint、version policy 和 content digest。 |
| Local distribution 可以暴露 current snapshot | 通过 | `current.json` 指向 versioned artifact directory。 |
| Data Plane 可以消费 distributed snapshots | 通过 | Startup、snapshot check 和 manual reload 使用同一个 resolver。 |
| Failed reloads 保持 active snapshot 稳定 | 通过 | Broken 或 incompatible distributed snapshots 不会替换 serving snapshot。 |
| Reload attempts 可审计 | 通过 | 失败和成功 reload 都会写入 `snapshot_reload_event`。 |
| Snapshot metadata 可用于生产审计 | 通过 | Schema version、registry fingerprint、version policy、manifest consistency 和 digest 都会校验。 |
| Distribution metadata 具备 path safety | 通过 | Absolute paths 和 `..` traversal 会在文件读取前被拒绝。 |
| Local publish 避免 half-published state | 通过 | Artifacts 通过 temp dirs 复制，duplicate versions 会被拒绝，`current.json` 通过 temp file 更新。 |

## 5. 剩余缺口

这些缺口是预期内的，应进入后续 Control Plane 阶段。

- 只有 local filesystem distribution
- 没有 remote object storage publish protocol
- 没有用于 concurrent publishers 的 compare-and-swap 或 distributed lock
- `current.json` replacement 是 best-effort local atomic behavior，不是 cross-filesystem transaction
- 没有 signed artifacts 或 provenance chain
- 没有 Postgres-backed registry store
- 没有 Control Plane HTTP service API
- 没有用于 Control Plane operations 的 hosted API key enforcement
- 没有 KMS-backed credential vault
- 没有 hosted analytics API
- 没有 billing
- 没有 marketplace

## 6. 阶段判断

API2Agent 不应该默认继续增加更多 local snapshot distribution guards。

当前本地 distribution 链路已经足够支撑这个 architecture phase：

```text
Control Plane registry -> artifact -> distribution -> Data Plane reload
```

下一阶段应该开始：

```text
Go Control Plane Service API Skeleton v0
```

这个判断是有条件的：

- 可以开始创建 local Control Plane service boundary
- 可以把现有 registry validation、artifact export 和 distribution status 包到 HTTP process 后面
- 还不能进入 hosted public alpha
- 还不能做 remote object storage distribution
- 还不能做 billing 或 marketplace

## 7. 建议的下一项入口任务

下一项 implementation slice 应该是：

```text
Go Control Plane Service API Skeleton v0
```

范围：

1. Local Control Plane HTTP process。
2. `GET /healthz` 返回 service、protocol 和 registry source metadata。
3. Read-only registry validation endpoint。
4. 基于现有 exporter 的 snapshot artifact export endpoint。
5. Distribution status endpoint，读取 `current.json`，且不暴露 secrets。
6. 非 health endpoints 使用 admin bearer token guard。

退出标准：

- Service 可以基于现有 local file registry 启动。
- Service 可以通过 HTTP validate registry。
- Service 可以通过 HTTP 使用现有 registry/exporter code 导出 artifact。
- Service 可以通过 HTTP 报告当前 local distribution pointer。
- 现有 CLI commands 和 dogfood 继续通过。
- 不包含 hosted database、vault、billing 或 marketplace 工作。

## 8. 战略判断

项目已经从 local Data Plane primitive 进入 local Control Plane distribution primitive。

下一步最重要的问题已经不是：

```text
Can the Control Plane produce a snapshot for the Data Plane?
```

这件事已经被证明了。

下一步的问题是：

```text
Can API2Agent expose Control Plane operations as a stable service boundary without changing the protocol semantics?
```

这才是正确的下一阶段。
