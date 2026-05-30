# Go Data Plane Durable Events Dogfood Report

日期：2026-05-30

## 目标

验证 Go Data Plane 的 JSONL event ingestion 可以持久写入事件，并且进程重启后 event sequence IDs 可以从已有日志继续。

## 设置

Dogfood flow：

```text
start Go Data Plane
  -> execute network.public_ip.get
  -> stop process
  -> restart Go Data Plane with the same event directory
  -> execute network.public_ip.get again
  -> inspect events.jsonl
```

脚本：

```text
python scripts/go_dataplane_durable_events_dogfood.py --output .dogfood/go-dataplane-durable-events/report.json
```

## 结果

```json
{
  "passed": true,
  "checks": {
    "first_response_success": true,
    "second_response_success": true,
    "event_log_exists": true,
    "eight_events_for_two_calls": true,
    "sequence_continues_after_restart": true,
    "no_duplicate_sequences": true,
    "two_request_contexts": true,
    "two_usage_events": true,
    "two_decision_logs": true
  }
}
```

## 证明了什么

- JSONL event writes 在 writer 返回前会 flush 并 sync。
- 重启后的 writer 会从已有 event log 恢复下一个 sequence ID。
- Event sequence IDs 在进程重启后仍保持单调递增。
- Execution graph 在重启前后保持 append-only。

## 备注

这还是本地 durable ingestion，不是最终 hosted ingestion pipeline。未来 hosted path 仍然需要 queue/log-backed ingestion 和 backpressure 行为。
