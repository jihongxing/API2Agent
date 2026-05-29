from pathlib import Path
from typing import Any, Literal

from api2agent.adapters.models import AdapterResult, ProviderAdapter
from api2agent.adapters.open_meteo import OpenMeteoWeatherAdapter
from api2agent.adapters.wttr_in import WttrInWeatherAdapter
from api2agent.capabilities.failover import build_failover_policy
from api2agent.capabilities.models import FailoverPolicy, ProviderCandidate, RoutingDecision, RoutingPolicy
from api2agent.capabilities.routing import rank_providers
from api2agent.control.models import UsageEvent
from api2agent.control.storage import UsageStore

SdkRoutingStrategy = Literal[
    "first",
    "random",
    "lowest_cost",
    "lowest_latency",
    "lowest_observed_latency",
    "highest_success_rate",
    "balanced",
]


def call(
    capability: str,
    input: dict[str, Any],
    *,
    project_id: str = "local",
    agent_id: str | None = None,
    provider_id: str | None = None,
    strategy: SdkRoutingStrategy = "lowest_latency",
    failover: bool = False,
    max_attempts: int | None = None,
    retry_on_status_codes: list[int] | None = None,
    retry_on_error_types: list[str] | None = None,
    db: Path | str = Path("api2agent-usage.sqlite"),
) -> dict[str, Any]:
    store = UsageStore(Path(db))
    adapter_classes = _adapters_for_capability(capability)
    ranked_provider_ids, decision_strategy = _rank_provider_ids(capability, adapter_classes, provider_id, store, strategy)
    failover_policy = _build_sdk_failover_policy(
        enabled=failover,
        candidate_count=len(ranked_provider_ids),
        max_attempts=max_attempts,
        retry_on_status_codes=retry_on_status_codes,
        retry_on_error_types=retry_on_error_types,
    )
    decision = RoutingDecision(
        project_id=project_id,
        capability_id=capability,
        strategy=decision_strategy,
        preset="sdk_core_loop_v0",
        selected_provider_id=ranked_provider_ids[0] if ranked_provider_ids else None,
        ranked_provider_ids=ranked_provider_ids,
        metrics=store.metrics_for_capability(capability),
        failover_policy=failover_policy,
    )
    store.record_routing_decision(decision)
    attempts = ranked_provider_ids[: failover_policy.max_attempts] if failover_policy.enabled else ranked_provider_ids[:1]
    attempt_results: list[dict[str, Any]] = []
    last_result: AdapterResult | None = None
    last_event: UsageEvent | None = None
    last_provider_id: str | None = None

    for index, attempted_provider_id in enumerate(attempts):
        adapter = adapter_classes[attempted_provider_id]()
        result = adapter.call(input)
        event = _record_usage(store, decision, adapter, result, input)
        attempt_results.append(
            {
                "provider_id": adapter.provider_id,
                "ok": result.ok,
                "usage_event_id": event.id,
                "status_code": result.status_code,
                "error_type": result.error_type,
                "latency_ms": result.latency_ms,
            }
        )
        last_result = result
        last_event = event
        last_provider_id = adapter.provider_id
        if result.ok:
            break
        if index >= len(attempts) - 1 or not _should_failover_adapter_result(result, failover_policy):
            break

    if last_result is None or last_event is None:
        raise RuntimeError(f"No provider attempts were available for capability: {capability}")

    return {
        "ok": last_result.ok,
        "capability_id": capability,
        "provider_id": last_provider_id,
        "routing_decision": decision.model_dump(mode="json"),
        "usage_event_id": last_event.id,
        "attempts": attempt_results,
        "output": last_result.output,
        "error_type": last_result.error_type,
        "error_message": last_result.error_message,
        "latency_ms": last_result.latency_ms,
        "cost": last_result.cost.model_dump(mode="json"),
        "agent_id": agent_id,
    }


def _rank_provider_ids(
    capability: str,
    adapters: dict[str, type[ProviderAdapter]],
    provider_id: str | None = None,
    store: UsageStore | None = None,
    strategy: SdkRoutingStrategy = "lowest_latency",
) -> tuple[list[str], str]:
    if provider_id:
        if provider_id not in adapters:
            raise ValueError(f"No provider adapter for capability={capability}, provider_id={provider_id}")
        return [provider_id], "provider_id"

    policy_strategy = "lowest_latency" if strategy == "lowest_observed_latency" else strategy
    candidates = [
        ProviderCandidate(
            id=provider_id,
            capability_id=capability,
            provider_id=provider_id,
            tool_id=getattr(adapter_class, "tool_id", "call"),
        )
        for provider_id, adapter_class in adapters.items()
    ]
    ranked = rank_providers(
        candidates,
        store.metrics_for_capability(capability) if store is not None else [],
        RoutingPolicy(strategy=policy_strategy),
    )
    ranked_provider_ids = [candidate.provider_id for candidate in ranked]
    return ranked_provider_ids, policy_strategy


def _adapters_for_capability(capability: str) -> dict[str, type[ProviderAdapter]]:
    if capability == "weather.get":
        return {
            "open_meteo": OpenMeteoWeatherAdapter,
            "wttr_in": WttrInWeatherAdapter,
        }
    raise ValueError(f"No provider adapter for capability: {capability}")


def _record_usage(
    store: UsageStore,
    decision: RoutingDecision,
    adapter: ProviderAdapter,
    result: AdapterResult,
    input: dict[str, Any],
) -> UsageEvent:
    event = UsageEvent(
        routing_decision_id=decision.id,
        execution_mode="direct",
        project_id=decision.project_id,
        capability_id=decision.capability_id,
        provider_id=adapter.provider_id,
        tool_id=getattr(adapter, "tool_id", "call"),
        method="GET",
        path=decision.capability_id,
        status_code=result.status_code,
        success=result.ok,
        latency_ms=result.latency_ms,
        estimated_cost=result.cost.estimated_cost,
        error_type=result.error_type,
        request_metadata={"input": input},
        provider_runtime_reference=f"sdk:{adapter.__class__.__name__}",
    )
    return store.record(event)


def _build_sdk_failover_policy(
    *,
    enabled: bool,
    candidate_count: int,
    max_attempts: int | None,
    retry_on_status_codes: list[int] | None,
    retry_on_error_types: list[str] | None,
) -> FailoverPolicy:
    policy = build_failover_policy(
        enabled=enabled,
        candidate_count=candidate_count,
        max_attempts=max_attempts,
        retry_on_status_codes=retry_on_status_codes,
    )
    policy.retry_on_error_types = retry_on_error_types or [
        "RATE_LIMIT",
        "TIMEOUT",
        "PROVIDER_ERROR",
        "NORMALIZATION_ERROR",
        "UNKNOWN",
    ]
    return policy


def _should_failover_adapter_result(result: AdapterResult, policy: FailoverPolicy) -> bool:
    if not policy.enabled:
        return False
    if result.status_code is not None and int(result.status_code) in policy.retry_on_status_codes:
        return True
    return bool(result.error_type and result.error_type in policy.retry_on_error_types)
