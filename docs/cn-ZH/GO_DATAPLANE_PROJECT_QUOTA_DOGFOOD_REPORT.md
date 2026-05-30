# Go Data Plane Project Quota Dogfood 报告

日期：2026-05-30

## 目标

验证 Go Data Plane 是否可以在 provider forwarding 之前执行本地、process-level project-level quota。

这对应 RFC 里 Edge Proxy 要求的 project identity 和 quota enforcement。

## 语义

Quota 具有以下特征：

- 只在当前进程内生效
- 按 project 计数
- 在 routing/provider execution 之前生效
- quota 耗尽时 fail closed

如果 quota 超额：

- 不写入 `RoutingDecision`
- 不调用 provider adapter
- 不写入 `UsageEvent`
- 写入 failed `DecisionLog`
- response 返回 `429`
- error type 是 `QUOTA_EXCEEDED`

## 环境

```bash
API2AGENT_PROJECT_QUOTA=1
```

## Dogfood 命令

```bash
python scripts/go_dataplane_project_quota_dogfood.py \
  --output .dogfood/go-dataplane-project-quota/report.json
```

脚本会构建：

- `api2agent-dataplane`
- `api2agent-conformance`

然后对同一个 project 发送两次请求。

## 观察结果

请求 1：

- 成功
- provider 被调用一次
- 写入 `request_context`、`routing_decision`、`usage_event`、`decision_log`

请求 2：

- 以 `QUOTA_EXCEEDED` 失败
- provider 没有被再次调用
- 只写入 `request_context` 和 `decision_log`

第二次失败的 decision log 记录了：

- `error_type: QUOTA_EXCEEDED`
- `error_scope: caller`

Protocol v0.2 conformance 通过。

## 结果

Project Quota Gate v0 通过。

Go Data Plane 现在拥有一个最小的本地 quota control point，可以在 provider forwarding 之前阻止滥用。

## 非目标

本切片不包含：

- billing
- payment
- hosted quota storage
- per-user quota accounting
- quota plans
- quota dashboards
