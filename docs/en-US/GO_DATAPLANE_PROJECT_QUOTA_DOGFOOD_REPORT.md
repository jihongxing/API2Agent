# Go Data Plane Project Quota Dogfood Report

Date: 2026-05-30

## Goal

Verify that Go Data Plane can enforce a local, process-level project-level quota before provider forwarding.

This slice is the local production analog of the RFC's requirement that the Edge Proxy enforce project identity and quotas.

## Semantics

Quota is:

- local to the process
- per project
- enforced before routing/provider execution
- fail-closed on quota exhaustion

If the quota is exceeded:

- no `RoutingDecision` is emitted
- no provider adapter is called
- no `UsageEvent` is emitted
- a failed `DecisionLog` is emitted
- response returns `429`
- error type is `QUOTA_EXCEEDED`

## Environment

```bash
API2AGENT_PROJECT_QUOTA=1
```

## Dogfood Command

```bash
python scripts/go_dataplane_project_quota_dogfood.py \
  --output .dogfood/go-dataplane-project-quota/report.json
```

The script builds:

- `api2agent-dataplane`
- `api2agent-conformance`

It then runs two requests against the same project.

## Observed Result

Request 1:

- succeeded
- provider was called once
- emitted `request_context`, `routing_decision`, `usage_event`, and `decision_log`

Request 2:

- failed with `QUOTA_EXCEEDED`
- provider was not called again
- emitted only `request_context` and `decision_log`

The second failed decision log recorded:

- `error_type: QUOTA_EXCEEDED`
- `error_scope: caller`

Protocol v0.2 conformance passed.

## Result

Project Quota Gate v0 passed.

The Go Data Plane now has a minimal local quota control point that can block abuse before provider forwarding.

## Non-Goals

This slice does not add:

- billing
- payment
- hosted quota storage
- per-user quota accounting
- quota plans
- quota dashboards
