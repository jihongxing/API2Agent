# Failover Policy Dogfood Report

Date: May 30, 2026

## Goal

Verify Failover Policy v0 with real HTTP provider failures.

This dogfood validates API2Agent reliability policy. It does not validate marketplace behavior.

## Policy

```json
{
  "enabled": true,
  "max_attempts": 2,
  "retry_on_status_codes": [500]
}
```

Expected behavior:

- HTTP 500 should fall back to the next provider.
- HTTP 400 should stop and not fall back.

## Scenario A: Retriable HTTP 500

Providers:

- `httpbin_500`: `https://httpbin.org/status/500`
- `ipify`: `https://api.ipify.org?format=json`

Result:

```json
{
  "ok": true,
  "final_provider_id": "ipify",
  "attempts": [
    {
      "provider_id": "httpbin_500",
      "ok": false,
      "status_code": 500
    },
    {
      "provider_id": "ipify",
      "ok": true,
      "status_code": 200
    }
  ]
}
```

## Scenario B: Non-Retriable HTTP 400

Providers:

- `httpbin_400`: `https://httpbin.org/status/400`
- `ipify`: `https://api.ipify.org?format=json`

Result:

```json
{
  "ok": false,
  "final_provider_id": null,
  "attempts": [
    {
      "provider_id": "httpbin_400",
      "ok": false,
      "status_code": 400
    }
  ]
}
```

## Ledger

```json
[
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "httpbin_400",
    "total_calls": 1,
    "successful_calls": 0,
    "failed_calls": 1,
    "success_rate": 0.0,
    "average_latency_ms": 2516.4781999774277,
    "estimated_cost": 0.003
  },
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "httpbin_500",
    "total_calls": 1,
    "successful_calls": 0,
    "failed_calls": 1,
    "success_rate": 0.0,
    "average_latency_ms": 2881.919600069523,
    "estimated_cost": 0.003
  },
  {
    "project_id": "local",
    "capability_id": "public_ip_lookup",
    "provider_id": "ipify",
    "total_calls": 1,
    "successful_calls": 1,
    "failed_calls": 0,
    "success_rate": 1.0,
    "average_latency_ms": 2071.823799982667,
    "estimated_cost": 0.001
  }
]
```

## Product Learning

Failover must be policy-driven, not just enabled or disabled.

The minimum useful policy needs:

- enabled
- max_attempts
- retry_on_status_codes
- retry_on_error_types

The current implementation is enough for local API2Agent reliability dogfood. The next hardening step is making policy visible in CLI output and persisted routing decision metadata.

## Follow-Up Verification

Failover policy metadata is now included in the routing decision response and persisted in the local routing decision ledger.

Verified output:

```json
{
  "routing_decision_failover_policy": {
    "enabled": true,
    "max_attempts": 2,
    "retry_on_error_types": [
      "http_error",
      "http_status",
      "proxy_error",
      "output_normalization"
    ],
    "retry_on_status_codes": [500]
  },
  "stored_failover_policy": {
    "enabled": true,
    "max_attempts": 2,
    "retry_on_error_types": [
      "http_error",
      "http_status",
      "proxy_error",
      "output_normalization"
    ],
    "retry_on_status_codes": [500]
  }
}
```

The next hardening step is exposing a dedicated routing-decision inspection command.
