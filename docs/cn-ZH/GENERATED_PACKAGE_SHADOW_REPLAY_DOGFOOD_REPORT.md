# Generated Package Shadow + Replay Dogfood 报告

日期：2026-05-30

## 目标

验证 local generated provider packages 是否可以进入 Reliability + Observability loop：

- main provider execution
- shadow provider execution
- usage ledger recording
- 基于 captured metadata 的 exact replay
- golden trace listing 和 ledger filtering

## 方法：No-Network Regression Dogfood

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

## 真实 No-Auth API 验证

同一条 loop 随后用两个从 curl input 生成的真实 no-auth APIs 完成验证：

- `ipify`：`https://api.ipify.org?format=json`
- `httpbin`：`https://httpbin.org/ip`

生成 packages：

```bash
python -m api2agent.cli generate --curl="curl 'https://api.ipify.org?format=json'" \
  --name ipify_public_ip \
  --output .dogfood/generated-real-api-shadow-replay/ipify \
  --force

python -m api2agent.cli generate --curl="curl 'https://httpbin.org/ip'" \
  --name httpbin_public_ip \
  --output .dogfood/generated-real-api-shadow-replay/httpbin \
  --force
```

Provider registry：

- capability：`public_ip_lookup`
- selected provider：`ipify`
- shadow provider：`httpbin`
- output mapping：
  - `ipify`：`$.ip`
  - `httpbin`：`$.origin`

执行：

```bash
python -m api2agent.cli call .dogfood/generated-real-api-shadow-replay/registry.json \
  --capability-id public_ip_lookup \
  --db .dogfood/generated-real-api-shadow-replay/usage.sqlite \
  --strategy first \
  --shadow \
  --json
```

结果：

- routing decision id：`d7afb386-934b-4c21-b3a4-d1e9121840b5`
- main usage event：`c256e26b-639d-4be4-bfbd-9cae34d52a5c`
- shadow usage event：`7ac911e8-fe2c-4230-aa06-a928a344463b`
- main provider：`ipify`
- shadow provider：`httpbin`
- normalized output：`{ "ip": "108.174.61.76" }`
- ledger rows：
  - `ipify / direct / success`
  - `httpbin / shadow / success`

Replay：

```bash
python -m api2agent.cli replay 7ac911e8-fe2c-4230-aa06-a928a344463b \
  --db .dogfood/generated-real-api-shadow-replay/usage.sqlite \
  --execute \
  --json
```

Replay result：

- `replayable`：`true`
- `exact_replay_metadata_ready`：`true`
- `executed`：`true`
- runtime：`local_package:.dogfood/generated-real-api-shadow-replay/httpbin`
- provider：`httpbin`
- status：`200`

Golden trace filtering：

```bash
python -m api2agent.cli golden --list \
  --db .dogfood/generated-real-api-shadow-replay/usage.sqlite \
  --capability-id public_ip_lookup \
  --provider-id httpbin \
  --execution-mode shadow \
  --json

python -m api2agent.cli ledger \
  --db .dogfood/generated-real-api-shadow-replay/usage.sqlite \
  --golden-only \
  --group-by-mode \
  --json
```

Golden result：

- `contract_version`：`golden_trace.v0.1`
- `count`：`1`
- provider：`httpbin`
- execution mode：`shadow`

这证明 generated package path 不只是能跑本地 fake，也能跑真实 API。
