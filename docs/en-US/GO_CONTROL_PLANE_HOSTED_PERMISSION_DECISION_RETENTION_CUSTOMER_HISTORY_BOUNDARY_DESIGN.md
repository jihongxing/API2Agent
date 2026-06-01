# Go Control Plane Hosted Permission Decision Retention + Customer History Boundary Design v0

Date: 2026-06-02

Status: complete

## Decision

Design a retention and customer-history boundary for hosted permission decision evidence before exposing decision history or treating persisted decision rows as long-lived product data.

For v0, hosted permission decision rows remain security and operations evidence. The next implementation should add the local boundary pieces that make retention and tenant-scoped history safe to build later: explicit retention policy metadata, tenant/project scoped query semantics, redaction rules, access-control checks, operator audit evidence, and dogfood proof. It should not expose a public customer history API yet.

Recommended next task:

```text
Go Control Plane Hosted Permission Decision Retention Boundary Implementation v0
```

That implementation should stay local/private and prove retention/history boundary mechanics without adding public CRUD, OAuth/OIDC, invitation/session lifecycle, marketplace/provider onboarding, vault writes, billing, workflow runtime, automatic propagation, policy write APIs, Data Plane reads from mutable Control Plane tables, or real production gateway deployment.

## Why This Design Now

The full hosted permission decision persistence lane is accepted for local v0:

- request-time decision evidence is persisted.
- allowed decisions fail closed when required evidence cannot be written.
- duplicate-equivalent evidence is stable.
- duplicate-conflicting evidence fails explicitly.
- production-shaped timeout/retry behavior is proven.
- persisted rows carry `evidence_fingerprint` and production-boundary metadata.
- live Postgres dogfood proves 16 secret-safe decision rows.

The remaining risk is no longer whether decision evidence can be written. The risk is how long evidence should live, who can view it, what can be exported or deleted, how support operators are audited, and what privacy guarantees exist before decision history becomes customer-visible.

## Goals

- define default retention stance for hosted permission decision rows
- define tenant/project scoped decision-history query semantics
- define safe customer-visible fields and redaction rules
- define access-control expectations for tenant admins, project admins, support operators, and internal systems
- define export, deletion, legal hold, and cleanup boundaries
- define operator audit requirements for viewing decision evidence
- define local implementation and dogfood evidence for the next slice

## Non-Goals

- no public customer-facing history endpoint in this design slice
- no OAuth/OIDC provider integration
- no public user/project/role CRUD
- no invitation, login, or session lifecycle
- no marketplace/provider onboarding
- no credential vault writes
- no billing or settlement state
- no workflow runtime
- no automatic snapshot publish or Data Plane reload
- no hosted policy write APIs
- no Data Plane reads from mutable Control Plane tables
- no real production gateway deployment

## Data Classification

Hosted permission decision rows are security evidence.

They are not:

- raw request logs
- raw identity-provider records
- billing metering records
- provider marketplace analytics
- workflow execution logs
- credential vault records

They may contain tenant-sensitive identifiers, such as project id, subject id, actor id, token id, required permission, policy fingerprint, deny reason family, gateway key id, and request id. Those fields are useful for accountability, support, and incident response, but they must stay bounded and secret-free.

## Retention Policy

Default v0 stance:

```text
90 days
```

Rules:

- append-only rows remain immutable during the active retention window.
- cleanup is out of band and never runs inline with public admin request handling.
- expired rows are eligible for deletion only when no legal hold applies.
- aggregate, tenant-safe metrics may outlive raw row retention.
- integrity conflict evidence should be retained at least as long as normal decision evidence.
- local dogfood rows live only as long as test artifacts.

Recommended local metadata for the next implementation:

| Field | Purpose |
| --- | --- |
| `retention_policy_version` | records the policy used when the row was written |
| `retention_class` | classifies normal, security, integrity-conflict, or legal-hold candidate evidence |
| `retain_until` | explicit cleanup eligibility timestamp |
| `history_visibility` | records whether the row is hidden, tenant_visible_candidate, or support_only |
| `legal_hold` | blocks cleanup when true |

If adding columns is too large for the next slice, the implementation may start with a bounded JSON metadata shape plus query/index proof. A later schema-hardening slice can promote fields into first-class columns.

## History Visibility Model

Decision history should be built as a tenant/project scoped view, not a global table dump.

Initial visibility classes:

| Class | Meaning |
| --- | --- |
| `hidden` | internal-only evidence; not eligible for customer history |
| `tenant_visible_candidate` | eligible for future customer history after access checks/redaction |
| `support_only` | visible only to audited support/operator workflows |

Default:

```text
tenant_visible_candidate
```

Exception candidates:

- platform integrity conflicts may be `support_only` until a customer-safe explanation is designed.
- source-unavailable rows may be visible as availability events, but not with internal database failure details.
- unknown route/method and missing/invalid public auth remain outside decision persistence in v0.

## Customer-Visible Field Boundary

Future customer history can show:

| Field | Stance |
| --- | --- |
| decision timestamp | visible |
| project id/name | visible within tenant/project scope |
| action or endpoint permission | visible |
| allow/deny/source-unavailable result | visible |
| deny reason family | visible |
| request id correlation | visible if tenant supplied or safe |
| policy version/fingerprint | visible |
| actor/subject display reference | visible only after identity lifecycle approval |
| decision id | visible as support/debug reference |
| evidence fingerprint | visible as integrity/audit reference |

Future customer history must not show:

- raw bearer tokens
- raw `Authorization` headers
- cookies
- gateway secrets
- OAuth access or refresh tokens
- plaintext API keys
- vault material
- raw request bodies
- raw provider credentials
- private Control Plane internal stack/error details
- unapproved external identity-provider subject references

## Access Control

Decision history access must be scoped by tenant and project.

Expected principals:

| Principal | Access stance |
| --- | --- |
| tenant owner/admin | may query tenant/project-scoped history after future public identity lifecycle exists |
| project admin | may query project-scoped history after future public identity lifecycle exists |
| readonly project member | no default history access in v0 |
| support operator | support-only access with reason, ticket id, and audit row |
| internal system | read access only for retention cleanup, export generation, metrics, and incident workflows |
| Data Plane | no direct reads from mutable Control Plane tables |

Until public identity lifecycle exists, local implementation should prove access checks with trusted gateway/test principals only.

## Operator Audit

Any support/operator view of decision evidence must create an audit record.

Audit evidence should include:

- actor/operator id
- organization id and project id scope
- access reason
- optional ticket/case reference
- query time range
- result count bucket
- redaction policy version
- request id
- outcome

Audit evidence must not include raw decision row contents, raw tokens, gateway secrets, or request bodies.

## Export Boundary

Export is designed but not implemented as a public API in this slice.

Future export requirements:

- tenant/project scope is required.
- explicit time range is required.
- export must use the customer-visible field boundary.
- export creation must write an audit event.
- export artifact must include a manifest with schema version, redaction policy version, row count, time range, and fingerprint.
- export artifacts must have a short lifetime unless legal hold requires longer retention.
- export must not include hidden/support-only fields without a separate audited support workflow.

## Deletion Boundary

Deletion is split into cleanup and customer-requested deletion.

Cleanup:

- deletes rows where `retain_until < now()` and `legal_hold=false`.
- runs out of band.
- emits cleanup metrics and a summary audit/operation event.
- never deletes admin audit rows, registry revisions, or aggregate metrics.

Customer-requested deletion:

- remains deferred until public identity lifecycle and policy/tenant admin authority exist.
- must be tenant/project scoped.
- must preserve aggregate security metrics when allowed.
- must produce deletion audit evidence.

## Legal Hold Boundary

Legal hold blocks cleanup and customer-requested deletion for matching rows.

V0 design stance:

- support/operator-only function, not customer-facing.
- scoped by tenant/project/time range.
- requires reason and operator audit evidence.
- does not mutate decision evidence except the hold metadata.

Implementation can defer legal hold mechanics, but the retention schema/metadata should not make legal hold impossible.

## Query Semantics

Initial local query helper should support:

- project id scope
- optional subject id scope
- start/end time range
- result family filter: allowed, denied, source-unavailable, persistence-failure, integrity-conflict
- endpoint/required permission filter
- limit plus stable descending time order

Rules:

- no unscoped cross-tenant query helper.
- default time range should be bounded.
- hard maximum page size is required.
- query output must be redacted through the customer-visible field boundary even if used only locally.
- support/operator query paths must emit audit evidence.

## Schema And Index Guidance

Existing production-boundary schema already has tenant/time, subject/time, retention, and policy-fingerprint indexes. The next implementation should either add explicit retention/history metadata or prove an equivalent bounded metadata shape.

Recommended indexes if promoted to columns:

```sql
CREATE INDEX hosted_permission_decisions_project_retain_until
  ON hosted_permission_decisions (project_id, retain_until);

CREATE INDEX hosted_permission_decisions_project_visibility_time
  ON hosted_permission_decisions (project_id, history_visibility, resolved_at DESC);
```

The implementation must not add raw request body storage, raw token storage, OAuth token tables, public CRUD tables, policy write APIs, or Data Plane mutable-read paths.

## Implementation Requirements

The next implementation should:

- add or standardize retention metadata for hosted permission decision rows.
- add a local/private decision-history query helper with tenant/project scoping.
- apply redaction to query output.
- add support/operator audit evidence for support-style queries.
- add cleanup candidate selection logic without deleting rows yet, unless deletion can be proven safely in an isolated local helper.
- keep customer-facing history endpoints disabled/deferred.
- prove query, redaction, retention metadata, and audit behavior in tests and dogfood.

## Test Requirements

Tests should cover:

- new decision rows receive retention policy metadata.
- `retain_until` or equivalent metadata is deterministic from `resolved_at` and policy.
- tenant/project scoped query returns only matching rows.
- cross-project query attempts are rejected or impossible through the helper.
- subject-scoped query stays within project scope.
- time range and page size limits are enforced.
- redacted output omits tokens, authorization headers, cookies, gateway secrets, OAuth tokens, plaintext credentials, vault material, and raw request bodies.
- support/operator query writes audit evidence.
- cleanup candidate selector ignores legal-hold rows.
- customer-facing history endpoint remains absent/disabled.
- Data Plane still does not read mutable Control Plane tables.

## Dogfood Requirements

Local dogfood should:

1. run the existing hosted admin gateway contract harness with decision persistence enabled.
2. write production-boundary decision rows with retention/history metadata.
3. query decision history for one project and prove row count and filters.
4. query a different project or scope and prove isolation.
5. run a support/operator query and prove audit evidence is written.
6. run cleanup-candidate selection and prove retained/legal-hold rows are handled correctly.
7. emit a secret-safe artifact containing only redacted history rows and summary counts.

## Acceptance Criteria

This design is accepted when:

- default retention stance is explicit.
- history visibility classes are explicit.
- customer-visible fields and redaction rules are explicit.
- access control expectations are explicit.
- operator audit expectations are explicit.
- export, deletion, cleanup, and legal hold boundaries are explicit.
- local implementation requirements are defined.
- test and dogfood evidence requirements are defined.
- public CRUD, OAuth/OIDC, production gateway deployment, vault, billing, marketplace, workflow, provider onboarding, policy write APIs, Data Plane mutable reads, and automatic propagation remain deferred.

## Next Recommended Task

```text
Go Control Plane Hosted Permission Decision Retention Boundary Implementation v0
```
