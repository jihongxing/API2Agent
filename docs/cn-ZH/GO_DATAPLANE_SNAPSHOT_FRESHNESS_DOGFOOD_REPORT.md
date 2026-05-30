# Go Data Plane Snapshot Freshness Dogfood 报告

日期：2026-05-30

## 目标

验证 Go Data Plane 在 routing snapshot 过期时是否 fail closed。

这对应 Production Architecture RFC 里的 Snapshot Drift mitigation：

```text
record snapshot_version
record fetch time and TTL
fail closed when snapshots expire beyond policy
```

## 语义

`/v1/execute` 现在会在写入 `RequestContext` 后、进入 routing 前检查 snapshot freshness。

如果 snapshot 已过期或非法：

- 不写入 `RoutingDecision`
- 不调用 provider adapter
- 不写入 `UsageEvent`
- 写入 failed `DecisionLog`
- response 返回 `503`
- error type 是 `SNAPSHOT_EXPIRED` 或 `SNAPSHOT_INVALID`

`/healthz` 会把 expired snapshot 报告为 `degraded`。

## Dogfood 命令

```bash
python scripts/go_dataplane_snapshot_freshness_dogfood.py \
  --output .dogfood/go-dataplane-snapshot-freshness/report.json
```

脚本会构建：

- `api2agent-dataplane`
- `api2agent-conformance`

并基于 Protocol v0.2 校验 emitted JSONL events。

## 场景 1：Active Snapshot 可以执行

设置：

- snapshot TTL 仍然有效
- local provider 返回固定 public-IP response

观察结果：

- `/healthz` 返回 `status: ok`
- `/v1/execute` 成功
- provider 被调用一次
- event graph 是：

```text
request_context -> routing_decision -> usage_event -> decision_log
```

- Protocol v0.2 conformance 通过

## 场景 2：Expired Snapshot Fail Closed

设置：

- snapshot `snapshot_fetched_at` 是 `2026-01-01T00:00:00Z`
- snapshot TTL 是 `1h`

观察结果：

- `/healthz` 返回 `status: degraded`
- `/healthz` 返回 `snapshot_expired: true`
- `/v1/execute` 返回 `SNAPSHOT_EXPIRED`
- provider 没有被调用
- event graph 是：

```text
request_context -> decision_log
```

- failed `DecisionLog.routing_context` 包含 `error_type: SNAPSHOT_EXPIRED`
- Protocol v0.2 conformance 通过

## 结果

Snapshot Freshness Gate v0 通过。

Go Data Plane 现在会拒绝使用过期 routing snapshot 执行 provider call，从而保证 routing auditability，并避免执行过期策略。

## 非目标

本切片不包含：

- hosted snapshot distribution
- push/pull snapshot refresh
- multi-snapshot fallback
- queue-backed ingestion
- Control Plane registry APIs
