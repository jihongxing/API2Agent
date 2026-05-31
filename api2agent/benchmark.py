import importlib.util
import os
import sys
from pathlib import Path
from time import perf_counter
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


def run_generated_package_latency_benchmark(
    *,
    package_dir: Path | str,
    tool_name: str,
    params: dict[str, Any] | None = None,
    iterations: int = 3,
    direct: bool = True,
    proxy_url: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be greater than 0")
    if not direct and not proxy_url:
        raise ValueError("At least one of direct or proxy_url must be provided")

    package_path = Path(package_dir)
    capability = _load_capability(package_path)
    tool = _find_generated_tool(capability, tool_name)
    if tool is None:
        raise ValueError(f"Unknown generated package tool: {tool_name}")

    base_env = dict(env or {})
    runs: dict[str, Any] = {}
    if direct:
        runs["direct"] = _benchmark_generated_mode(
            package_path=package_path,
            tool_name=tool_name,
            params=params or {},
            iterations=iterations,
            env={key: value for key, value in base_env.items() if key != "API2AGENT_PROXY_URL"},
        )
    if proxy_url:
        proxy_env = {
            **base_env,
            "API2AGENT_PROXY_URL": proxy_url,
            "API2AGENT_PROVIDER_ID": base_env.get("API2AGENT_PROVIDER_ID") or capability.get("name", "unknown"),
            "API2AGENT_CAPABILITY_ID": base_env.get("API2AGENT_CAPABILITY_ID") or capability.get("name", "unknown"),
            "API2AGENT_PROVIDER_REGION": base_env.get("API2AGENT_PROVIDER_REGION")
            or capability.get("provider_region")
            or "",
        }
        proxy_env = {key: value for key, value in proxy_env.items() if value is not None}
        runs["proxy"] = _benchmark_generated_mode(
            package_path=package_path,
            tool_name=tool_name,
            params=params or {},
            iterations=iterations,
            env=proxy_env,
        )

    return {
        "contract_version": "api2agent.generated_package_latency_benchmark.v0",
        "package_dir": str(package_path),
        "capability": {
            "name": capability.get("name"),
            "version": capability.get("version"),
            "provider_region": capability.get("provider_region"),
            "provider_regions": capability.get("provider_regions") or [],
            "source": capability.get("source"),
        },
        "tool": {
            "name": tool.get("name"),
            "method": tool.get("method"),
            "path": tool.get("path"),
        },
        "iterations": iterations,
        "runs": runs,
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


def _load_capability(package_dir: Path) -> dict[str, Any]:
    capability_path = package_dir / "capability.json"
    if not capability_path.exists():
        raise ValueError(f"Generated package capability.json not found: {capability_path}")
    import json

    payload = json.loads(capability_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Generated package capability.json must contain an object: {capability_path}")
    return payload


def _find_generated_tool(capability: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
    for tool in capability.get("tools") or []:
        if tool.get("name") == tool_name:
            return tool
    return None


def _benchmark_generated_mode(
    *,
    package_path: Path,
    tool_name: str,
    params: dict[str, Any],
    iterations: int,
    env: dict[str, str],
) -> dict[str, Any]:
    results = [
        _execute_generated_tool(package_path=package_path, tool_name=tool_name, params=params, env=env)
        for _ in range(iterations)
    ]
    successful = [item for item in results if item.get("ok")]
    latencies = [float(item["latency_ms"]) for item in results if item.get("ok")]
    return {
        "runs": len(results),
        "successful_runs": len(successful),
        "failed_runs": len(results) - len(successful),
        "success_rate": len(successful) / len(results) if results else 0.0,
        "p50_latency_ms": round(_percentile(latencies, 50), 3) if latencies else None,
        "p95_latency_ms": round(_percentile(latencies, 95), 3) if latencies else None,
        "results": results,
    }


def _execute_generated_tool(
    *,
    package_path: Path,
    tool_name: str,
    params: dict[str, Any],
    env: dict[str, str],
) -> dict[str, Any]:
    module = _load_runner_module(package_path)
    old_env = os.environ.copy()
    started = perf_counter()
    try:
        os.environ.clear()
        os.environ.update(old_env)
        os.environ.update(env)
        result = module.execute_tool(tool_name, params)
        latency_ms = (perf_counter() - started) * 1000
        error = result.get("error") if isinstance(result, dict) else None
        return {
            "ok": bool(isinstance(result, dict) and result.get("ok")),
            "status_code": result.get("status_code") if isinstance(result, dict) else None,
            "latency_ms": round(latency_ms, 3),
            "error_type": error.get("type") if isinstance(error, dict) else None,
            "usage_event_id": result.get("usage_event_id") if isinstance(result, dict) else None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": round((perf_counter() - started) * 1000, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def _load_runner_module(package_dir: Path):
    module_name = f"api2agent_benchmark_runner_{package_dir.name}_{id(package_dir)}_{len(sys.modules)}"
    spec = importlib.util.spec_from_file_location(module_name, package_dir / "runner.py")
    if spec is None or spec.loader is None:
        raise ValueError(f"Generated package runner.py not found: {package_dir / 'runner.py'}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


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
