# Go Control Plane Admin Mutation Idempotency Store Design v0

日期：2026-05-31

状态：complete

## 决策

在增加更多 mutation endpoints 或 operator convenience features 之前，为 private admin mutation requests 增加 Postgres-backed idempotency record。

第一位 consumer 是：

```text
POST /v1/admin/registry/import-replace
```

这份设计还不实现 table 或 service code。它定义下一项 implementation slice 必须遵守的 durable semantics。

设计被接受后的推荐下一项任务：

```text
Go Control Plane Admin Mutation Idempotency Store Implementation v0
```

## 目标

idempotency store 必须让这些情况变成确定行为：

- same key plus same request 返回第一次 committed response
- same key plus different request 返回稳定 conflict
- client timeout after server success 后可以安全 retry
- response replay 不再执行 registry mutation
- registry revision 和 admin audit evidence 可以链接到 idempotency record
- records 通过显式 cleanup 过期，而不是在 request-time 出现模糊语义

## Non-Goals

- no public registry CRUD APIs
- no provider self-onboarding
- no marketplace provider submission
- no credential vault writes
- no plaintext secret storage
- no billing、settlement 或 revenue-share state
- no workflow engine
- no automatic snapshot export、publish 或 Data Plane reload
- no direct Data Plane reads from Control Plane mutable tables

## Key Scope

idempotency key 的 scope 是：

```text
project_id + actor_id + operation + idempotency_key_hash
```

对当前 local/private import-replace endpoint：

- 在 hosted project identity 存在前，`project_id` 是 `control_plane`。
- `actor_id` 来自 authenticated admin principal。当前 local endpoint 中是 `X-Actor-ID` 或 `admin`。
- `operation` 是 `registry.import_replace`。
- raw `Idempotency-Key` header 会 trim、hash，不能单独作为 global key 使用。

durable table 不应该存 raw idempotency key。只存：

- `idempotency_key_hash`
- 用于 debug 的短 `idempotency_key_prefix`
- hash algorithm，初始为 `sha256`

现有 audit metadata 当前会带 `idempotency_key`。implementation slice 应该把新的 mutation audit metadata 迁移成 `idempotency_key_hash` 和 `idempotency_key_prefix`，避免长期保存 caller-supplied tokens。

## Request Fingerprint

request fingerprint 是 canonical mutation intent 的 hash，不是 raw HTTP body 的 hash。

对 `registry.import_replace`，计算：

```json
{
  "version": "admin-mutation-idempotency-v0",
  "operation": "registry.import_replace",
  "method": "POST",
  "path": "/v1/admin/registry/import-replace",
  "registry_fingerprint": "sha256:...",
  "source": "admin_http_import",
  "dry_run": false
}
```

规则：

- JSON field order、whitespace 和等价 registry ordering 不应该改变 fingerprint。
- `X-Request-ID` 不进入 fingerprint，这样 retry 可以使用新的 request id。
- `Idempotency-Key` 不进入 fingerprint，因为它是 lookup key。
- `actor_id` 和 `project_id` 不进入 fingerprint，因为它们已经在 key scope 里。
- `source` 进入 fingerprint，因为它会改变 audit evidence。
- `dry_run=true` 继续不支持，并且在 mutation 前被拒绝。

implementation 可以复用 `ReplacePersistentRegistry` 已经使用的 canonical registry path 来得到 `registry_fingerprint`。

## Record Schema

建议 table：

```sql
CREATE TABLE admin_mutation_idempotency_records (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT 'control_plane',
  actor_id TEXT NOT NULL DEFAULT '',
  operation TEXT NOT NULL,
  idempotency_key_hash TEXT NOT NULL,
  idempotency_key_prefix TEXT NOT NULL DEFAULT '',
  idempotency_key_hash_algorithm TEXT NOT NULL DEFAULT 'sha256',
  request_fingerprint TEXT NOT NULL,
  request_fingerprint_algorithm TEXT NOT NULL DEFAULT 'sha256',
  request_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  first_request_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('processing', 'succeeded')),
  response_status_code INTEGER,
  response_body JSONB,
  response_fingerprint TEXT NOT NULL DEFAULT '',
  registry_fingerprint TEXT NOT NULL DEFAULT '',
  previous_registry_fingerprint TEXT NOT NULL DEFAULT '',
  snapshot_version TEXT NOT NULL DEFAULT '',
  noop BOOLEAN NOT NULL DEFAULT false,
  registry_revision_id BIGINT REFERENCES registry_revisions(id),
  admin_audit_event_id BIGINT REFERENCES admin_audit_events(id),
  replay_count BIGINT NOT NULL DEFAULT 0,
  last_replay_request_id TEXT NOT NULL DEFAULT '',
  last_replayed_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX admin_mutation_idempotency_records_unique_key
  ON admin_mutation_idempotency_records (
    project_id,
    actor_id,
    operation,
    idempotency_key_hash
  );

CREATE INDEX admin_mutation_idempotency_records_expires_at
  ON admin_mutation_idempotency_records (expires_at);

CREATE INDEX admin_mutation_idempotency_records_request_fingerprint
  ON admin_mutation_idempotency_records (request_fingerprint);
```

`processing` 在同一个 transaction 内、mutation work 前插入，并在 commit 前更新为 `succeeded`。因为它是 transaction-local，普通 caller 通常只会观察到没有 row，或已经 committed 的 `succeeded` row。这个状态仍然有助于 lock wait、diagnostics，以及未来可能更直接暴露 in-flight reservations 的实现。

## Transaction Boundary

`ReplacePersistentRegistry` 继续拥有 registry mutation transaction。

implementation 应按这个顺序扩展 transaction：

1. Canonicalize 并 validate incoming registry。
2. 计算 `registry_fingerprint` 和 idempotency `request_fingerprint`。
3. 开始 serializable Postgres transaction。
4. 插入 `status='processing'` 的 idempotency reservation row。
5. 如果 scoped key 已经存在 committed row：
   - same `request_fingerprint`：进入 replay path，不执行 mutation
   - different `request_fingerprint`：返回 conflict
6. 获取 registry mutation advisory lock。
7. 执行现有 import/replace 或 no-op path。
8. registry 发生变化时插入 registry revision。
9. 插入 required admin audit success event。
10. 用 response status、response body、linkage ids、fingerprints 和 `status='succeeded'` 更新 idempotency record。
11. Commit。

idempotency success record、registry rows、registry revision 和 admin audit success event 必须原子 commit。

如果 transaction rollback，idempotency reservation 也随之 rollback。因为没有 committed mutation outcome 可以 replay，同一个 key 可以重新尝试。

## Response Replay

对 same scoped key plus same request fingerprint：

- 不再调用 `ReplacePersistentRegistry` mutation logic
- 返回 cached `response_status_code`
- 返回 cached `response_body`
- 保留原始 success semantics：
  - changed registry replay 返回 `201 Created`
  - no-op replay 返回 `200 OK`
- 增加 `replay_count`
- 把 `last_replay_request_id` 设置为 retry request id
- 设置 `last_replayed_at`

implementation 可以增加 response headers，例如：

```text
Idempotency-Replayed: true
Idempotency-Record-ID: <id>
```

这些 headers 只用于 diagnostics。body 继续沿用现有 `ImportReplaceResponse` shape。

## Conflict Behavior

对 same scoped key plus different request fingerprint：

```http
409 Conflict
```

```json
{
  "error": {
    "error_type": "IDEMPOTENCY_KEY_CONFLICT",
    "error_scope": "caller",
    "message": "idempotency key was already used for a different request",
    "retryable": false
  }
}
```

这个 conflict 不能执行 mutation，也不能创建 registry revision。

conflict response 只能在 logs 或 audit 中包含安全诊断 metadata，例如 operation、actor、project、key hash prefix、existing request fingerprint 和 incoming request fingerprint。不能回显 raw idempotency key。

## In-Progress And Concurrency Semantics

同一个 scoped key 的并发相同请求应该只产生一次 mutation。

推荐的 v0 行为是让第二个 transaction 在 unique key conflict 上等待，直到第一个 transaction commit 或 rollback：

- 如果第一个 commit，第二个 request 观察到 succeeded record 并 replay
- 如果第一个 rollback，第二个 request 可以取得 reservation 并尝试 mutation
- 如果等待超过 caller context deadline，返回 retryable platform failure

如果 implementation 选择显式 in-progress response，而不是等待，使用：

```text
409 IDEMPOTENCY_REQUEST_IN_PROGRESS platform retryable=true
```

同样行为只适用于 scoped key。不同 actor 或未来不同 project 可以独立使用相同 `Idempotency-Key` 值。

## Failure Semantics

idempotency store 缓存 committed mutation outcomes，不缓存每一个 HTTP failure。

这些情况不要求写 idempotency record：

- invalid admin token
- missing `X-Request-ID`
- missing `Idempotency-Key`
- invalid JSON
- over-limit request body
- missing `registry`
- `dry_run=true`
- invalid registry that fails before a canonical request fingerprint is created

transaction 开始后的 failures 应该让 idempotency reservation 和 registry mutation 一起 rollback：

- registry advisory lock conflict
- persistent read/write failure
- required audit write failure
- serializable transaction failure
- commit failure where Postgres reports rollback

如果 client 在 server commit 后 timeout，使用同一个 scoped key 和 same request fingerprint retry 时，返回 cached success response。

如果 `tx.Commit` 返回 ambiguous error 但 Postgres 实际已经 commit，retry path 必须仍然找到 committed idempotency record 并 replay success response。如果 Postgres rollback，retry path 可以重新尝试 mutation。

## Audit And Revision Linkage

对 changed registry imports：

- `registry_revisions.id` 应存入 `registry_revision_id`。
- `registry.import_replace` success 对应的 `admin_audit_events.id` 应存入 `admin_audit_event_id`。

对 same-fingerprint no-op imports：

- `registry_revision_id` 为 null。
- `admin_audit_event_id` 指向 `registry.import_replace` no-op success audit event。

Replay requests 不能创建额外 registry revisions。Replay 可以：

- 只更新 idempotency record replay fields，或
- 额外写一条 lightweight audit event，例如 `registry.import_replace.replay`

v0 implementation 应优先只更新 replay fields。之后如果 operators 需要完整 replay event stream，再增加单独 replay audit action。

## Retention And Cleanup

默认 retention：

```text
30 days after completed_at
```

`expires_at` 表示 record 可以被 cleanup。它不表示 row 仍存在时 request-time semantics 会悄悄消失。

规则：

- record 存在期间，same-key same-request replay 和 same-key different-request conflict 继续生效
- cleanup 可以删除 `expires_at < now()` 的 records
- 删除 idempotency record 不能删除 registry revision 或 admin audit evidence
- hosted deployments 之后可以按 operation 和 project tier 调整 retention

## HTTP Error Mapping

增加这些 registry/service error types：

| Condition | HTTP | `error_type` | scope | retryable |
| --- | ---: | --- | --- | --- |
| Same scoped key, different request | 409 | `IDEMPOTENCY_KEY_CONFLICT` | caller | false |
| Same scoped key still in progress, if not waiting | 409 | `IDEMPOTENCY_REQUEST_IN_PROGRESS` | platform | true |
| Idempotency store read failed | 503 | `IDEMPOTENCY_STORE_READ_FAILED` | platform | true |
| Idempotency store write failed | 503 | `IDEMPOTENCY_STORE_WRITE_FAILED` | platform | true |
| Cached response cannot be replayed | 500 | `IDEMPOTENCY_RESPONSE_REPLAY_FAILED` | platform | true |

现有 mutation errors 保持当前 mapping。

## Implementation Shape

推荐 Go shape：

- hosted identity 引入后，扩展 `registry.ImportReplaceOptions`，增加 project 或 scope fields
- 在 registry package 内增加小型 idempotency helper，不放在 HTTP handler 内
- 让 `insertRegistryRevisionTx` 和 `insertAdminAuditTx` 返回 inserted ids
- 让 `ReplacePersistentRegistry` 返回 normal result 或带 status metadata 的 replayed result
- HTTP request parsing 和 response writing 继续留在 `httpapi`
- 所有 mutable table writes 继续留在 registry package

HTTP 层只应该计算 request identity 和解析 body。registry 层拥有 canonical request fingerprinting、idempotency reservation、transaction linkage 和 replay decision。

## Tests Required For Implementation

Schema 和 registry-layer tests：

- unique key scope 是 `project_id + actor_id + operation + idempotency_key_hash`
- raw idempotency key 不落库
- same key plus same canonical request 返回 cached result
- same key plus different source or registry fingerprint 返回 `IDEMPOTENCY_KEY_CONFLICT`
- changed import 存储 `registry_revision_id` 和 `admin_audit_event_id`
- no-op import 存储 null `registry_revision_id` 和 non-null `admin_audit_event_id`
- audit write failure 会 rollback registry mutation 和 idempotency reservation
- commit success followed by client retry 会 replay committed response
- concurrent identical requests 只产生一次 registry replacement
- cleanup 删除 expired idempotency rows，但不删除 audit 或 revision rows

HTTP tests：

- replayed changed import 返回原始 `201` 和 response body
- replayed no-op import 返回原始 `200` 和 response body
- conflict key reuse 返回 `409 IDEMPOTENCY_KEY_CONFLICT`
- idempotency store read/write failures 映射为 `503`
- invalid auth、missing headers、invalid JSON、over-limit body 和 `dry_run=true` 不要求 idempotency records
- original request 和 replay 的 `X-Request-ID` 可以不同
- replay 不触发 snapshot export、publish、Data Plane reload 或第二次 registry mutation

## Acceptance Criteria

这个 design 被接受的条件：

- persistent idempotency record schema 已文档化
- key scope 已文档化
- request fingerprint semantics 已文档化
- response replay semantics 已文档化
- same-key different-request conflict behavior 已文档化
- 和 `ReplacePersistentRegistry` 的 transaction boundary 已文档化
- registry revision 和 admin audit linkage 已文档化
- retention and cleanup policy 已文档化
- failure semantics 已文档化
- 下一项 slice 的 implementation tests 已命名
- public CRUD、vault、billing、marketplace、workflow、provider onboarding 和 automatic propagation 继续不进入范围
