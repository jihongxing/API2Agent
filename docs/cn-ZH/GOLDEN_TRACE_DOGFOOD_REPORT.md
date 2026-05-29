# Golden Trace Dogfood 报告

日期：2026-05-30

## 目标

验证真实 usage event 是否可以被标记为 golden trace、被列出，并在 ledger output 中过滤。

Source database：

- `.dogfood/shadow-weather.sqlite`

Usage event：

- `31c5a817-0d2a-4174-94e9-6186acba64ef`

Provider：

- `wttr_in`

Execution mode：

- `shadow`

## 方法

```bash
python -m api2agent.cli golden 31c5a817-0d2a-4174-94e9-6186acba64ef \
  --db .dogfood/shadow-weather.sqlite \
  --json

python -m api2agent.cli golden --list \
  --db .dogfood/shadow-weather.sqlite \
  --capability-id weather.get \
  --provider-id wttr_in \
  --execution-mode shadow \
  --json

python -m api2agent.cli ledger \
  --db .dogfood/shadow-weather.sqlite \
  --golden-only \
  --json
```

## 结果

```json
{
  "contract_version": "golden_trace.v0.1",
  "is_golden": true,
  "usage_event": {
    "provider_id": "wttr_in",
    "execution_mode": "shadow",
    "is_golden": true
  }
}
```

List output 会返回稳定 golden trace contract：

```json
{
  "contract_version": "golden_trace.v0.1",
  "count": 1,
  "golden_traces": [
    {
      "provider_id": "wttr_in",
      "execution_mode": "shadow",
      "is_golden": true
    }
  ]
}
```

## 证明了什么

API2Agent 可以把真实 known-good executions 标记为后续用途的基准：

- replay baselines
- benchmark baselines
- provider scoring
- regression tests
- filtered ledger inspection

## 当前限制

- golden traces 当前是 marker 和 filter
- scoring logic 还没有使用 golden traces
