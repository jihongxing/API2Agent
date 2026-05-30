from pathlib import Path
from typing import Any, Iterable

from api2agent.capabilities.models import (
    DecisionDatasetRecord,
    MetricsSnapshot,
    ProviderCandidate,
    RoutingDecision,
    RoutingPolicy,
)
from api2agent.capabilities.routing import rank_providers, select_provider_region
from api2agent.sdk import call


def run_weather_benchmark(
    *,
    city: str,
    iterations: int = 3,
    providers: Iterable[str] = ("open_meteo", "wttr_in"),
    db: Path | str = Path("api2agent-usage.sqlite"),
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be greater than 0")

    results_by_provider: dict[str, list[dict[str, Any]]] = {provider: [] for provider in providers}
    for _ in range(iterations):
        for provider in providers:
            result = call("weather.get", {"city": city}, provider_id=provider, agent_id="benchmark_agent", db=db)
            results_by_provider[provider].append(result)

    provider_stats = []
    for provider, results in results_by_provider.items():
        latencies = [float(item["latency_ms"]) for item in results]
        successes = [item for item in results if item["ok"]]
        estimated_cost = sum(float(item["cost"]["estimated_cost"]) for item in results)
        observed_cost = sum(float(item["cost"]["observed_cost"] or 0.0) for item in results)
        provider_stats.append(
            {
                "provider_id": provider,
                "total_calls": len(results),
                "successful_calls": len(successes),
                "success_rate": len(successes) / len(results) if results else 0.0,
                "p50_latency_ms": _percentile(latencies, 50),
                "p95_latency_ms": _percentile(latencies, 95),
                "estimated_cost": estimated_cost,
                "observed_cost": observed_cost,
                "cost_delta": observed_cost - estimated_cost,
            }
        )

    return {
        "capability_id": "weather.get",
        "city": city,
        "iterations": iterations,
        "providers": provider_stats,
    }


def run_region_aware_routing_benchmark(
    *,
    capability_id: str,
    client_region: str,
    providers: Iterable[ProviderCandidate],
    metrics: Iterable[MetricsSnapshot],
    project_id: str = "local",
) -> dict[str, Any]:
    provider_list = list(providers)
    metric_list = list(metrics)
    policy = RoutingPolicy(strategy="region_aware_latency", client_region=client_region)
    ranked = rank_providers(provider_list, metric_list, policy)
    selected = ranked[0] if ranked else None
    decision = RoutingDecision(
        project_id=project_id,
        capability_id=capability_id,
        strategy=policy.strategy,
        client_region=client_region,
        selected_provider_id=selected.provider_id if selected else None,
        selected_provider_region=select_provider_region(selected, client_region) if selected else None,
        ranked_provider_ids=[provider.provider_id for provider in ranked],
        metrics=metric_list,
    )
    selected_latency = _selected_latency(selected.provider_id if selected else None, metric_list, client_region)
    dataset_record = DecisionDatasetRecord(
        request_id=decision.id,
        routing_decision_id=decision.id,
        project_id=project_id,
        capability_id=capability_id,
        client_region=client_region,
        candidate_provider_ids=[provider.provider_id for provider in provider_list],
        selected_provider_id=selected.provider_id if selected else None,
        selected_provider_region=select_provider_region(selected, client_region) if selected else None,
        routing_strategy=policy.strategy,
        success=selected is not None,
        latency_total_ms=selected_latency,
        estimated_cost=selected.estimated_cost if selected else 0.0,
        error_type=None if selected else "no_provider",
    )

    return {
        "capability_id": capability_id,
        "client_region": client_region,
        "selected_provider_id": selected.provider_id if selected else None,
        "ranked_provider_ids": [provider.provider_id for provider in ranked],
        "routing_decision": decision.model_dump(mode="json"),
        "decision_dataset_record": dataset_record.model_dump(mode="json"),
    }


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * (percentile / 100)
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _selected_latency(
    provider_id: str | None,
    metrics: list[MetricsSnapshot],
    client_region: str,
) -> float | None:
    if provider_id is None:
        return None
    matching_metrics = [
        item
        for item in metrics
        if item.provider_id == provider_id and item.client_region == client_region and item.total_calls
    ]
    if matching_metrics:
        return min(item.average_latency_ms for item in matching_metrics)
    provider_metrics = [item for item in metrics if item.provider_id == provider_id and item.total_calls]
    if provider_metrics:
        return min(item.average_latency_ms for item in provider_metrics)
    return None
