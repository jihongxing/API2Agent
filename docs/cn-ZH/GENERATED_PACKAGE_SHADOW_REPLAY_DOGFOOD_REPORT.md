# Generated Package Shadow + Replay Dogfood 报告

日期：2026-05-30

## 目标

验证 local generated provider packages 是否可以进入 Reliability + Observability loop：

- main provider execution
- shadow provider execution
- usage ledger recording
- 基于 captured metadata 的 exact replay
- golden trace listing 和 ledger filtering

## 方法

在 `.dogfood/generated-shadow-replay` 下创建了一个不依赖网络的 dogfood registry，包含两个 local package runners：

- `primary`
- `shadow`

调用命令：

```bash
python -m api2agent.cli call .dogfood/generated-shadow-replay/registry.json \
  --capability-id public_ip_lookup \
  --params '{"ip":"203.0.113.10"}' \
  --db .dogfood/generated-shadow-replay/usage.sqlite \
  --strategy first \
  --shadow \
  --json
```

Replay 命令：

```bash
python -m api2agent.cli replay 70e439d8-e6b8-4831-adb3-a880e3a5366b \
  --db .dogfood/generated-shadow-replay/usage.sqlite \
  --execute \
  --json
```

Golden filtering：

```bash
python -m api2agent.cli golden --list \
  --db .dogfood/generated-shadow-replay/usage.sqlite \
  --capability-id public_ip_lookup \
  --provider-id shadow \
  --execution-mode shadow \
  --json

python -m api2agent.cli ledger \
  --db .dogfood/generated-shadow-replay/usage.sqlite \
  --golden-only \
  --group-by-mode \
  --json
```

## 结果

Routing decision：

- selected provider：`primary`
- ranked providers：`primary`、`shadow`
- shadow attempts：`shadow`

Usage events：

- `primary` 记录为 `direct`
- `shadow` 记录为 `shadow`
- 两条 events 共享同一个 routing decision

Replay result：

```json
{
  "replayable": true,
  "exact_replay_metadata_ready": true,
  "executed": true,
  "replay_result": {
    "ok": true,
    "runtime": "local_package:.dogfood/generated-shadow-replay/shadow",
    "provider_id": "shadow",
    "status_code": 200,
    "body": {
      "ip": "203.0.113.10"
    }
  }
}
```

Golden list result：

- `contract_version`：`golden_trace.v0.1`
- `count`：`1`
- provider：`shadow`
- execution mode：`shadow`

## 证明了什么

Generated packages 不再只是 callable tools。它们现在可以像 SDK adapters 一样进入同一套 local execution and observability loop：

```text
api2agent call
  -> provider package
  -> shadow provider package
  -> usage events
  -> replay
  -> golden trace filter
```

这补齐了 compiler path 和 SDK reliability path 之间的 alpha gap。
