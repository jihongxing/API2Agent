# API2Agent Protocol v0.2 Plan

Status: superseded by the frozen contract draft.

Frozen contract: `docs/en-US/API2AGENT_PROTOCOL_V0_2.md`

Schema snapshot: `schemas/api2agent/v0.2/protocol.schema.json`

## Purpose

Protocol v0.2 should turn the current working MVP contracts into industrial-grade infrastructure contracts.

The goal is not to add more runtime features. The goal is to prevent the Python reference implementation from locking the protocol into local MVP assumptions.

## Freeze Principle

v0.2 must stabilize contracts before production reimplementation.

Stable contracts should be language-neutral, runtime-neutral, model-neutral, and source-neutral.

## Required Additions

### 1. Latency Profile

Current MVP records aggregate latency. v0.2 needs structured latency:

- `latency_ms`
- `latency_p50_ms`
- `latency_p95_ms`
- `latency_p99_ms`
- `latency_cold_start_ms`
- `latency_network_ms`
- `latency_provider_ms`
- `latency_overhead_ms`
- `latency_region`

### 2. Network Topology

Routing needs topology awareness:

- `client_region`
- `edge_region`
- `api2agent_region`
- `provider_region`
- `selected_provider_region`
- `route_path`

### 3. Execution Class

v0.1 is API-first. v0.2 must reserve source-neutral execution classes:

- `api`
- `workflow`
- `tool`
- `model`
- `human`
- `async_job`

These are protocol fields only. They do not mean v0.2 implements all execution sources.

### 4. Reliability Profile

Routing needs reliability metrics beyond success rate:

- `reliability_score`
- `timeout_rate`
- `error_rate`
- `retry_rate`
- `failover_rate`
- `sla_confidence`

### 5. Decision Log

Decision records must preserve:

- candidate providers
- candidate regions
- selected provider
- selected provider region
- routing policy
- routing context
- cost estimate
- latency estimate
- reliability estimate
- outcome

### 6. Capability Source Contract

Capability source must be explicit:

- `source_type`
- `execution_class`
- `executor_ref`
- `input_schema`
- `output_schema`
- `auth`
- `region_metadata`

## Non-Goals

Protocol v0.2 does not implement:

- marketplace UI
- payment settlement
- all capability source adapters
- workflow engine
- hosted SaaS product

## Exit Criteria

Protocol v0.2 is ready when:

- schema fields are documented
- backward compatibility from v0.1 is defined
- Python MVP maps cleanly into v0.2
- production architecture can implement v0.2 without inheriting Python runtime assumptions
