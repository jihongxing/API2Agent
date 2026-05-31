# Go Control Plane Admin Mutation Idempotency Store Implementation Report v0

日期：2026-05-31

状态：complete

## Summary

已经为 private admin registry mutations 实现第一版 Postgres-backed idempotency store。

implementation 只覆盖：

```text
POST /v1/admin/registry/import-replace
```

它不增加 public CRUD、automatic snapshot propagation、vault、billing、marketplace、workflow runtime 或 provider onboarding scope。

## What Changed

- 在 Postgres schema 中增加 `admin_mutation_idempotency_records`。
- 为 `project_id + actor_id + operation + Idempotency-Key` 增加 scoped key hashing。
- 为 import/replace requests 增加 canonical request fingerprinting。
- 增加 same-key same-request response replay。
- 增加 same-key different-request conflict detection。
- 将 idempotency records 链接到 `registry_revisions.id` 和 `admin_audit_events.id`。
- idempotency reservation、registry mutation、registry revision、admin audit success 和 cached outcome 保持在同一个 serializable transaction 中。
- 增加 HTTP replay headers：
  - `Idempotency-Replayed: true`
  - `Idempotency-Record-ID: <id>`
- 增加 idempotency conflicts 和 store failures 的稳定 HTTP error mapping。

## Transaction Semantics

对带 `Idempotency-Key` 的 request，`ReplacePersistentRegistry` 现在会：

1. Canonicalize 并 fingerprint incoming registry。
2. 计算 import/replace idempotency request fingerprint。
3. 开始现有 serializable transaction。
4. Reserve scoped idempotency key。
5. 如果 same key 和 same request fingerprint 已经有 committed result，则 replay。
6. 如果 same key 已被不同 request fingerprint 使用，则 reject。
7. 执行现有 registry replacement 或 no-op path。
8. 写入 registry revision 和 admin audit evidence。
9. 用 cached response 和 evidence links complete idempotency record。
10. 原子 commit。

如果 transaction rollback，idempotency reservation 也一起 rollback。

## Response Semantics

Same-key same-request replay：

- 不修改 registry tables
- 不创建第二条 registry revision
- 不创建第二条 mutation audit event
- 返回 cached `ImportReplaceResult`
- 保留原始 status behavior：
  - changed import：`201`
  - no-op import：`200`

Same-key different-request reuse 返回：

```text
409 IDEMPOTENCY_KEY_CONFLICT caller retryable=false
```

## Tests Added

- no-op import 会存 completed idempotency record，带 audit linkage，不带 registry revision linkage
- changed import 会存 completed idempotency record，带 audit 和 revision linkage
- raw idempotency keys 不会存入 scripted persistent rows
- same key plus same canonical request replay cached result，不再次 replace rows
- same key plus different request 返回 `IDEMPOTENCY_KEY_CONFLICT`
- HTTP replay response 包含 replay headers
- HTTP error mapping 覆盖 idempotency conflict、in-progress、store read/write 和 replay failures
- schema test 断言 idempotency table、unique key 和 audit/revision references

## Validation

已通过：

```text
go test ./...
```

目录：

```text
services/control-plane
```

## Next Recommended Task

```text
Go Control Plane Admin Mutation Idempotency Store Live Postgres Dogfood v0
```

dogfood 应该在真实 Postgres instance 上验证 replay 和 conflict semantics。
