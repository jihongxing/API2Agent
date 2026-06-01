# Go Control Plane Hosted Permission Store Design v0

日期：2026-06-01

状态：complete

## 决策

定义 durable hosted permission store boundary，用于 gateway permission lookup。

建议下一项 implementation task：

```text
Go Control Plane Hosted Permission Store Contract Harness v0
```

这份设计在概念上替换 static dogfood permission source，但不实现 storage、public role CRUD、OAuth/OIDC、invitation flow、production gateway deployment、marketplace/provider onboarding、billing、workflow runtime、credential vault writes 或 automatic snapshot propagation。

permission store 属于 hosted gateway/auth boundary。private Control Plane 继续作为第二道 authorization gate，必须继续使用 trusted gateway claims，而不是直接读取 public permission tables。

## 为什么现在做这片

hosted admin path 已经证明：

- hosted trusted-gateway identity 和 header issuance
- public caller header stripping
- gateway-local static permission decisions
- Control Plane endpoint permission checks 作为第二道 gate
- 通过 `POST /v1/admin/registry/project-partition/replace` 完成 project-scoped mutation
- hosted project mutation 的 audit 与 idempotency evidence
- success、replay、partition violation 和 gateway-local denial 的 live dogfood

剩下的 hosted product gap 是 gateway permission source 仍然是 static dogfood policy。下一步需要设计 durable lookup boundary，后续才能实现，而不会过早打开 public role management，也不会把 authorization 移进 mutable Control Plane API surface。

## 目标

- 定义 durable permission-store entities 与 relationships
- 定义替换 static policy lookup 的 gateway lookup contract
- 保持 endpoint permission mapping 显式且窄
- 保留 hosted project mutation 的 project-scoped authorization
- 保持 Control Plane trusted-permission checks 作为第二道 gate
- 定义 unavailable、ambiguous、stale 或 denied policy 的 fail-closed semantics
- 定义 permission source id、version、decision id 的安全 audit/report evidence
- 在 implementation 前定义 consistency 与 cache 预期
- 让下一项 contract harness 可测试，同时不加入 public CRUD

## 非目标

不要实现或设计这些 public product surfaces：

- OAuth/OIDC provider integration
- public user、project、role 或 permission CRUD
- invitation、login 或 session lifecycle
- production gateway deployment
- marketplace/provider onboarding
- credential vault writes
- billing or settlement state
- workflow runtime
- automatic snapshot publish or reload
- Data Plane reads from mutable Control Plane tables
- global registry/provider objects 的 public mutation

## Boundary

hosted gateway 拥有 permission lookup：

```text
public authenticated principal
  -> hosted permission store lookup
  -> gateway-issued trusted claims
  -> private Control Plane request
  -> Control Plane endpoint permission check
```

Control Plane 在 v0 中不得直接读取 hosted permission tables。它只接收 gateway-issued trusted claims：

```text
X-API2Agent-Subject-ID
X-API2Agent-Actor-ID
X-API2Agent-Project-ID
X-API2Agent-Organization-ID
X-API2Agent-Token-ID
X-API2Agent-Roles
X-API2Agent-Permissions
```

可选的安全 evidence 只能作为 metadata 转发：

```text
X-API2Agent-Permission-Source
X-API2Agent-Policy-Version
X-API2Agent-Policy-Fingerprint
X-API2Agent-Permission-Decision-ID
```

这些 evidence headers 不得成为 Control Plane 的 authorization inputs。authorization 仍然基于 trusted permissions 和 endpoint-specific checks。

## Store Model

durable store 应该建模 gateway claims 所需的 authorization facts。建议 logical entities：

| Entity | Purpose |
| --- | --- |
| `hosted_subjects` | 从 authenticated external/public principal 映射而来的稳定 hosted subject。 |
| `hosted_project_memberships` | subject 在 project 和 organization 内的 membership，包括 active/suspended state。 |
| `hosted_roles` | 内部 role definitions，例如 `project_admin`、`project_editor`、`project_readonly` 或 `platform_operator`。 |
| `hosted_role_bindings` | role 到 subject/project/organization scope 的 assignment。 |
| `hosted_permission_grants` | role 与 scope 授予的 permission constants；也可以实现为 role-permission binding table。 |
| `hosted_policy_versions` | monotonic policy version、fingerprint、activation time 和 audit metadata。 |
| `hosted_permission_decisions` | 可选 append-only decision/audit record，用于 gateway permission lookups。 |

External token/session storage 不属于这份 v0 设计。未来如果加入 OAuth/OIDC/session tables，它们应该把 authenticated public principal 输入这个 lookup boundary，而不是改变 permission decision contract。

## Lookup Contract

概念上的 gateway contract：

```text
ResolveHostedPermissionDecision(request_context, endpoint_context)
  -> HostedPermissionDecision
```

Inputs：

| Field | Description |
| --- | --- |
| `public_principal_id` | gateway authenticator 认证后的 public subject。 |
| `external_subject_ref` | public auth 后可选的 provider/user reference。 |
| `method` | HTTP method。 |
| `path` | routing normalization 之后的 public admin path。 |
| `project_context` | 来自 trusted route/context 的 project，不来自任意 caller headers。 |
| `request_id` | safe evidence correlation id。 |
| `resolved_at` | gateway decision time。 |

Outputs：

| Field | Description |
| --- | --- |
| `allowed` | gateway 是否可以 forward request。 |
| `deny_reason` | `allowed=false` 时的 stable local denial reason。 |
| `subject_id` | trusted headers 使用的 hosted subject id。 |
| `actor_id` | audit/idempotency scope 使用的 actor id。 |
| `project_id` | trusted headers 使用的 project scope。 |
| `organization_id` | trusted headers 使用的 organization scope。 |
| `token_id` | 如果可用，使用 non-secret token/session id。 |
| `roles` | gateway-issued trusted role names。 |
| `permissions` | gateway-issued trusted permission constants。 |
| `required_permission` | 从 method/path 派生的 endpoint permission。 |
| `policy_source` | durable store/source identifier。 |
| `policy_version` | decision 使用的 monotonic policy version。 |
| `policy_fingerprint` | policy view 的 non-secret fingerprint。 |
| `decision_id` | 用于 report/audit correlation 的 non-secret decision id。 |
| `resolved_at` | decision timestamp。 |

gateway 必须在 forward 前检查 `required_permission` 是否存在于 `permissions`。Control Plane 必须用 trusted claims 再做一次 endpoint permission check。

## Endpoint Permission Mapping

hosted gateway 必须显式映射当前 private admin endpoints：

| Method / Path | Required Permission |
| --- | --- |
| `POST /v1/admin/registry/validate` | `control_plane.registry.validate` |
| `POST /v1/admin/registry/import-replace` | `control_plane.registry.import_replace` |
| `POST /v1/admin/registry/project-partition/replace` | `control_plane.registry.project_partition_replace` |
| `POST /v1/admin/snapshots/export-artifact` | `control_plane.snapshot.export_artifact` |
| `GET /v1/admin/distribution/current` | `control_plane.distribution.read_current` |
| `POST /v1/admin/distribution/publish` | `control_plane.distribution.publish` |

Hosted project mutation 应该授予：

```text
control_plane.registry.project_partition_replace
```

不应授予 broad full-registry replacement：

```text
control_plane.registry.import_replace
```

除非是明确的 operator/internal roles，且这些 roles 不作为普通 hosted project memberships 暴露。

未知 public admin paths 必须在 gateway 本地以 `404` 或 `405` 失败，不得到达 Control Plane。

## Failure Semantics

Gateway-local failures：

| Condition | HTTP | Error Type | Forward? |
| --- | --- | --- | --- |
| missing public auth | `401` | `PUBLIC_AUTH_REQUIRED` | no |
| invalid public principal | `401` | `PUBLIC_AUTH_INVALID` | no |
| permission store unavailable | `503` | `PERMISSION_SOURCE_UNAVAILABLE` | no |
| missing project membership | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| inactive/suspended membership | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| ambiguous project scope | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| stale or ambiguous policy view | `503` 或 `403` | `PERMISSION_SOURCE_UNAVAILABLE` 或 `PUBLIC_AUTHZ_DENIED` | no |
| endpoint permission absent | `403` | `PUBLIC_AUTHZ_DENIED` | no |
| unknown admin route | `404` | `PUBLIC_ROUTE_NOT_FOUND` | no |
| unsupported method | `405` | `PUBLIC_METHOD_NOT_ALLOWED` | no |

Unavailable store failures 是 gateway-local `503 PERMISSION_SOURCE_UNAVAILABLE`，不得创建 Control Plane audit rows 或 idempotency records。

Policy ambiguity、missing membership、stale policy 和 permission absence 必须 fail closed。系统绝不能从 durable lookup fallback 到 broad static allow。

Control Plane failures 仍然独立：

- invalid trusted gateway auth 返回 `401 AUTH_ERROR`
- missing trusted permissions 返回 `403 AUTHZ_DENIED`
- platform auth configuration failure 返回 `503 AUTH_SERVICE_UNAVAILABLE`

## Consistency

单次 permission decision 必须从 coherent policy view 解析。

v0 最低预期：

- role bindings、membership state 和 permission grants 从同一个 consistent transaction/snapshot 读取
- decision output 包含 `policy_version` 或 `policy_fingerprint`
- revocation 不允许在显式有界 cache window 之外继续 allow
- stale 或 mixed-version policy reads 必须 fail closed
- policy writes 不在范围内，但 read model 必须为 monotonic versioning 和 revocation evidence 留出空间

## Caching

最安全的 v0 contract harness 可以不使用 cache。

如果后续 implementation 加入 gateway-local cache，它必须：

- short-lived
- 以 subject、project、endpoint permission 和 policy version/fingerprint 为 key
- 在 policy version mismatch 时 invalidated 或 bypassed
- backing store unavailable 且 cache stale 或 ambiguous 时 fail-closed
- 不在 evidence 中包含 raw public tokens 或 gateway secrets

任何 cache 都不能把 revoked permission 变成无界 allow。

## Audit And Evidence

安全 evidence：

- `subject_id`
- `actor_id`
- `project_id`
- `organization_id`
- `roles`
- `permissions`
- `required_permission`
- `policy_source`
- `policy_version`
- `policy_fingerprint`
- `decision_id`
- `resolved_at`

禁止 evidence：

- raw public bearer tokens
- raw gateway secrets
- raw session tokens
- OAuth access/refresh tokens
- credential vault material
- plaintext API keys

Gateway-local denials 应该出现在 gateway dogfood/report evidence 中，但不得创建 Control Plane audit 或 idempotency rows，因为它们不会被 forward。

Forwarded successful 或 Control Plane-denied requests 应继续使用 trusted actor/project scope 写 Control Plane audit 与 idempotency evidence。

## Contract Harness Plan

下一项 implementation slice 应证明 lookup contract，而不是构建 production permission store。

建议 harness behavior：

1. 用 durable-store-shaped fixture 或 local read model 替换 static in-memory policy。
2. 通过新 contract 解析 subject、membership、role bindings 和 permission grants。
3. 在 safe report evidence 中返回 policy source/version/fingerprint/decision id。
4. 保持 gateway trusted-header stripping 与 injection。
5. 保持 gateway-local denial before forwarding。
6. 保持 Control Plane second-gate denial test。
7. 增加 revocation 与 unavailable-store cases。
8. public CRUD 与 auth-provider lifecycle 全部保持出范围。

## Test Plan

未来 implementation 应覆盖：

- project admin/editor 在允许 endpoint 上 lookup allow
- readonly principal 在 mutation endpoint 上 lookup deny
- missing membership/project scope
- inactive/suspended membership
- permission store unavailable
- stale or ambiguous policy version
- permission revocation removes access
- 当前六个 endpoint 的 endpoint permission mapping
- hosted project mutation 必须使用 `control_plane.registry.project_partition_replace`
- hosted project mutation 不要求 broad `control_plane.registry.import_replace`
- Control Plane second gate 仍然拒绝 insufficient trusted permissions
- gateway-local denials 不创建 Control Plane audit/idempotency rows
- audit/report evidence 包含 policy version/fingerprint/decision id
- raw public tokens、gateway secrets、session tokens 和 vault material 被 redacted
- 不加入 public role CRUD、user CRUD、invitation flow、OAuth/OIDC provider integration 或 production gateway deployment
- 不改变 registry mutation 或 snapshot propagation behavior

## Acceptance Criteria

- durable permission store model 明确
- gateway lookup input/output contract 明确
- endpoint permission mapping 包含 project partition endpoint
- hosted project mutation 使用 project-partition permission，而不是 broad import/replace
- failure semantics fail-closed，且必要时保持 gateway-local
- consistency 与 cache rules 防止 revocation 后无界 allow
- audit/report evidence 可用且 secret-safe
- implementation 仍 deferred 到 contract harness
- 不启动 public CRUD、OAuth/OIDC、production gateway、marketplace、vault、billing、workflow 或 automatic propagation scope

## Next Recommended Task

```text
Go Control Plane Hosted Permission Store Contract Harness v0
```
