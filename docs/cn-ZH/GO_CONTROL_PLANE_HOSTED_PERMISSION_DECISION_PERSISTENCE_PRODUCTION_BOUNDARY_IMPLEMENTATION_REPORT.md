# Go Control Plane Hosted Permission Decision Persistence Production Boundary Implementation Report v0

日期：2026-06-02

状态：complete

## 总结

local hosted admin gateway harness 现在实现了 production-shaped hosted permission decision persistence boundary。

gateway-owned writer 仍然同进程运行，会写入 canonical `evidence_fingerprint`，在 non-secret metadata 中记录 bounded timeout/retry 配置，在很小的预算内 retry transient write failures，并且在 persistence unavailable 或 timeout 时，让 allowed decisions 在 private Control Plane forwarding 前 fail closed。

本次没有部署真实 production gateway，没有加入 OAuth/OIDC、public CRUD、invitation/session lifecycle、marketplace/provider onboarding、vault writes、billing、workflow runtime、automatic propagation、policy write APIs，也没有让 Data Plane 读取 mutable Control Plane tables。

## 已实现

更新：

```text
services/control-plane/schema/postgres/001_persistent_registry_store.sql
services/control-plane/internal/registry/persistent_schema_test.go
scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py
tests/test_go_control_plane_hosted_admin_gateway_contract.py
```

新增 production-boundary schema hardening：

- `hosted_permission_decisions.evidence_fingerprint`
- `CHECK (evidence_fingerprint LIKE 'sha256:%')`
- 用于 tenant history 的 project/time query index
- subject/time query index
- 用于 retention scans 的 `created_at` index
- 用于 conflict investigation 的 policy fingerprint index

新增 gateway writer behavior：

- canonical controlled-evidence fingerprinting
- 每条 decision row 持久化 evidence fingerprint
- production boundary metadata version
- bounded write timeout evidence
- transient write retry budget evidence
- transient retry success path
- allowed decisions timeout fail-closed path

保持不变：

- duplicate-equivalent no-op behavior
- conflicting duplicate `PERMISSION_DECISION_INTEGRITY_CONFLICT`
- allowed conflict 在 forwarding 前 fail closed
- denied/source-unavailable caller semantics
- auth-failure persistence skips
- secret-safe metadata 和 artifacts

## Dogfood Artifact

Artifact：

```text
.dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
```

Observed：

- `status=passed`
- `audit_counts.hosted_permission_decisions=16`
- `permission_decision_rows_written_count=16`
- `permission_decision_retry_count=1`
- `permission_decision_timeout_count=1`
- `transient_retry_status=200`
- `persistence_timeout_status=503`
- `persistence_timeout_error_type=PERMISSION_DECISION_PERSISTENCE_UNAVAILABLE`
- `audit_rows_after_persistence_timeout=0`
- `hosted_permission_decision_rows_after_duplicate_equivalent=16`
- `integrity_conflict_status=503`
- `integrity_conflict_error_type=PERMISSION_DECISION_INTEGRITY_CONFLICT`
- `hosted_permission_decision_rows_after_integrity_conflict=16`
- 每条 persisted decision row 都有 `evidence_fingerprint`
- 每条 persisted decision row 都有 production boundary metadata
- rows 和 report artifact 中都没有 secret markers

## 验证

live dogfood 前已本地通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
go test ./internal/registry
go test ./...
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-permission-decision-persistence-production-boundary/report.json
```

## 下一项推荐任务

```text
Go Control Plane Hosted Permission Decision Persistence Production Boundary Live Dogfood + Closeout v0
```
