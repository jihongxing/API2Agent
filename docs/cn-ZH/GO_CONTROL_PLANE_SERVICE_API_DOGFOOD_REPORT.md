# Go Control Plane Service API Dogfood 报告

日期：2026-05-31

## 目标

验证第一版 local Control Plane service boundary，并且不改变 snapshot protocol semantics。

这个 dogfood 验证的是现有 registry validation、artifact export 和 distribution status code paths 外面的 HTTP wrapper。

## 已实现

Go Control Plane 现在支持：

- `serve` command，用于启动 local HTTP service
- public `GET /healthz`
- 非 health endpoints 的 admin bearer token guard
- `POST /v1/admin/registry/validate`
- `POST /v1/admin/snapshots/export-artifact`
- `GET /v1/admin/distribution/current`

这个 service 仍然是 local-first。它不包含 hosted persistence、remote object storage、vault、billing 或 marketplace flows。

## 已验证流程

dogfood 脚本会：

1. 构建 Go Control Plane binary。
2. 写入 local file registry。
3. 通过现有 CLI commands 创建 initial artifact 和 local distribution。
4. 使用 admin token 启动 Control Plane service。
5. 无 auth 调用 `/healthz`。
6. 验证 unauthenticated admin call 会被 `AUTH_ERROR` 拒绝。
7. 通过 HTTP validate registry。
8. 通过 HTTP export snapshot artifact。
9. 通过 HTTP 读取 current distribution pointer。

## 检查项

```json
{
  "health_is_public_and_ok": true,
  "unauthorized_admin_rejected": true,
  "registry_validation_passed": true,
  "artifact_export_created_manifest": true,
  "artifact_export_created_snapshot": true,
  "distribution_current_reported": true
}
```

## 结果

Go Control Plane Service API Skeleton v0 通过。

Control Plane 不再只是 CLI-only。它现在有了第一版 local service boundary，同时仍然复用已经验证过的 registry、artifact 和 distribution primitives。
