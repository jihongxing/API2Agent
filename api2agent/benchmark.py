from pathlib import Path
from typing import Any, Iterable

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
