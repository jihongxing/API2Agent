# Go Control Plane Private Admin Import/Replace Endpoint Implementation v0

日期：2026-05-31

状态：complete

## 决策

private admin import/replace endpoint 已实现。

推荐下一项任务：

```text
Go Control Plane Private Admin Import/Replace Endpoint Live Postgres Dogfood v0
```

## 已实现 Endpoint

```text
POST /v1/admin/registry/import-replace
```

该 endpoint 是 registry-layer import/replace primitive 的薄 HTTP 包装。

它不实现 granular CRUD。

它不负责 export、publish 或 reload snapshots。

## 代码变更

实现位置：

- `services/control-plane/internal/httpapi/service.go`
- `services/control-plane/internal/httpapi/service_test.go`
- `services/control-plane/cmd/api2agent-controlplane/main.go`

文档更新：

- `services/control-plane/README.md`
- `README.md`
- `CHANGELOG.md`
- roadmap 和 implementation plan documents

## Runtime Wiring

`httpapi.Handler` 现在接收一个很窄的 import/replace dependency：

```go
type RegistryImportReplacer interface {
    ReplacePersistentRegistry(ctx context.Context, reg registry.Registry, opts registry.ImportReplaceOptions) (registry.ImportReplaceResult, error)
}
```

`serve` command 只在 runtime registry store 为 Postgres 时注入这个 dependency。

File-store mode 保持不变，不能通过该 endpoint 修改 registry files。

## Request Contract

必需：

- `Authorization: Bearer <admin-token>`
- `X-Request-ID`
- `Idempotency-Key`

可选：

- `X-Actor-ID`

Request body：

```json
{
  "registry": {},
  "source": "admin_http_import",
  "dry_run": false
}
```

行为：

- `source` 默认为 `admin_http_import`。
- `X-Actor-ID` 默认为 `admin`。
- `dry_run=true` 在 v0 被拒绝。
- request body 限制为 2 MiB。

## Response Contract

registry 发生替换：

```text
201 Created
```

same-fingerprint no-op：

```text
200 OK
```

两种响应都包含：

- `registry_store`
- `registry_fingerprint`
- `previous_registry_fingerprint`
- `snapshot_version`
- `noop`
- object counts

## Error Mapping

已实现稳定映射：

| Condition | HTTP | error_type |
| --- | ---: | --- |
| missing/invalid admin token | 401 | `AUTH_ERROR` |
| missing `X-Request-ID` | 400 | `INVALID_REQUEST` |
| missing `Idempotency-Key` | 400 | `INVALID_REQUEST` |
| invalid JSON / missing registry / `dry_run=true` | 400 | `INVALID_REQUEST` |
| body over 2 MiB | 413 | `REQUEST_BODY_TOO_LARGE` |
| file store or unconfigured mutator | 409 | `REGISTRY_MUTATION_UNAVAILABLE` |
| invalid registry graph | 400 | `REGISTRY_MUTATION_INVALID` |
| mutation conflict | 409 | `REGISTRY_MUTATION_CONFLICT` |
| persistent read/write failure | 503 | `PERSISTENT_STORE_READ_FAILED` / `PERSISTENT_STORE_WRITE_FAILED` |
| audit write failure | 500 | `AUDIT_WRITE_FAILED` |

未知 mutation errors 会 fail closed 为 `REGISTRY_MUTATION_FAILED`。

## Snapshot Boundary

该 endpoint 不推进 snapshots。

operator sequence 仍然是：

```text
import/replace persistent registry
  -> export artifact
  -> publish distribution
  -> Data Plane reload
```

## 新增测试

覆盖内容：

- admin token required
- `X-Request-ID` required
- `Idempotency-Key` required
- file-store mutation unavailable
- invalid JSON
- missing registry wrapper field
- `dry_run=true`
- request body larger than 2 MiB
- changed registry returns `201`
- no-op registry returns `200`
- actor/request/idempotency/source options 会传入 registry 层
- `RegistryMutationError` HTTP mappings

## 验证

已通过：

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
- no automatic snapshot export/publish/reload
- no Data Plane reads from mutable Control Plane tables

