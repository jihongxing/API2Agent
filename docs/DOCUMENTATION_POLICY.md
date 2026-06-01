# API2Agent Documentation Policy

Date: 2026-06-02

Status: active

## Purpose

API2Agent documentation must preserve decisions without slowing code delivery.

The repository previously used one document per small slice for design, implementation reports, dogfood reports, closeouts, and bilingual mirrors. That created good traceability, but the documentation surface is now larger than the product code surface and is too costly to maintain.

This policy changes the default from "create a new document for every task" to "update the smallest durable record that keeps the project understandable."

## Default Rule

For normal implementation work, do not create a new standalone document.

Default updates are:

- code
- tests
- `CHANGELOG.md`
- a compact phase-log entry when the work changes project state

README, roadmap, and implementation-plan updates should happen only when the current focus, durable architecture, or public entry points change.

## When A New Document Is Allowed

Create a new standalone document only when the task changes at least one durable boundary:

- public API contract
- storage schema or migration strategy
- security or trust boundary
- cross-service protocol
- production deployment boundary
- legal/privacy/customer-visible data boundary
- major product direction or irreversible architecture decision

If none of those apply, use the phase log.

## Reports And Closeouts

Do not create per-slice closeout documents by default.

Dogfood and validation evidence should live as machine-readable artifacts or test output. The phase log should record only:

- task name
- commit
- changed behavior
- validation commands
- key evidence metrics
- decision
- next task
- phase completion estimate, when relevant

Detailed JSON output belongs under `.dogfood/` or an equivalent generated-artifact path, not as another long report.

## Bilingual Policy

Long-lived external or product-facing documents may stay bilingual.

Internal process documents, phase logs, dogfood summaries, and closeouts should not be mirrored by default. Use one canonical document unless the user explicitly asks for a translation.

## README Policy

README should list only core navigation:

- Quickstart
- Core concepts
- PRD / MVP
- protocol and architecture
- implementation plan
- roadmap
- documentation policy
- active phase log

Historical reports should remain discoverable through search, git history, and phase-log references, not through the README main navigation.

## Current Exception

Existing historical documents are not deleted by this policy. They remain useful for audit and handoff context.

Future cleanup should archive or index old reports separately instead of removing evidence abruptly.

## Active Phase Log

Hosted Control Plane work now uses:

```text
docs/HOSTED_CONTROL_PLANE_PHASE_LOG.md
```

Future Hosted Control Plane tasks should append compact entries there instead of adding new per-slice reports or closeout documents, unless a new durable boundary requires a standalone design.
