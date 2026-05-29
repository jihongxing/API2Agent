# Replay Dogfood 报告

日期：2026-05-30

## 目标

验证 `api2agent replay --execute` 是否可以基于 usage event 中捕获的 metadata 重新执行 provider call。

Source database：

- `.dogfood/shadow-weather.sqlite`

Capability：

- `weather.get`

## 方法

Replay 一个成功的 shadow event：

```bash
python -m api2agent.cli replay 31c5a817-0d2a-4174-94e9-6186acba64ef \
  --db .dogfood/shadow-weather.sqlite \
  --execute \
  --json
```

## 结果

Replay preflight：

```json
{
  "replayable": true,
  "exact_replay_metadata_ready": true,
  "executed": true,
  "missing_for_exact_replay": []
}
```

Replay execution：

```json
{
  "ok": true,
  "runtime": "sdk:WttrInWeatherAdapter",
  "provider_id": "wttr_in",
  "status_code": 200
}
```

Replay 也用 `--record` 执行过，并产生了额外 ledger row：

| Provider | Execution Mode | Calls | Success Rate |
| --- | --- | ---: | ---: |
| `wttr_in` | `replay` | 1 | 100% |

Routing metrics 仍然排除了 replay row：

```text
open_meteo 1 1.0 3342.38
wttr_in 1 1.0 1786.19
```

另一次针对原始 `open_meteo` main event 的 replay 可以执行，但返回了 live timeout。这是可接受且有价值的：replay 不假装 provider state 被冻结，而是重新执行已捕获调用，并暴露当前 provider behavior。

## 证明了什么

当以下条件满足时，API2Agent 现在已经有最小 deterministic replay path：

- request metadata 已捕获
- provider runtime reference 被支持
- 不需要 credential reference

Replay 已经从 audit-only preflight 进入 supported events 的 executable debugging。

## 当前限制

- 先支持 SDK adapters
- HTTP/proxy replay 只在不需要 credentials 时可用
- replay execution 只有在使用 `--record` 时才写入新的 usage event
- replay events 默认不进入 routing metrics
- local generated package replay 仍是后续工作
