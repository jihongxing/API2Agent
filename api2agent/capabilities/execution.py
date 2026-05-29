import importlib.util
import os
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

from api2agent.capabilities.failover import build_failover_policy, should_failover
from api2agent.capabilities.models import FailoverPolicy, ProviderCandidate, RoutingDecision, RoutingPolicy
from api2agent.capabilities.normalization import OutputNormalizationError, normalize_output
from api2agent.capabilities.routing import rank_providers, select_provider
from api2agent.control.models import UsageEvent
from api2agent.control.storage import UsageStore


def execute_capability(
    providers: list[ProviderCandidate],
    capability_id: str,
    params: dict[str, Any],
    store: UsageStore,
    policy: RoutingPolicy | None = None,
    preset: str | None = None,
    proxy_url: str | None = None,
    failover: bool = False,
    failover_policy: FailoverPolicy | None = None,
) -> dict[str, Any]:
    candidates = [provider for provider in providers if provider.capability_id == capability_id]
    metrics = store.metrics_for_capability(capability_id)
    selected = select_provider(candidates, metrics, policy)
    ranked = rank_providers(candidates, metrics, policy)
    effective_failover_policy = failover_policy or build_failover_policy(
        enabled=failover,
        candidate_count=len(ranked),
    )
    decision = RoutingDecision(
        capability_id=capability_id,
        strategy=(policy.strategy if policy else "balanced"),
        preset=preset,
        selected_provider_id=selected.provider_id if selected else None,
        ranked_provider_ids=[provider.provider_id for provider in ranked],
        metrics=metrics,
        failover_policy=effective_failover_policy,
    )
    store.record_routing_decision(decision)

    if selected is None:
        return {
            "ok": False,
            "routing_decision": decision.model_dump(mode="json"),
            "attempts": [],
            "error": {"type": "no_provider", "message": f"No provider for capability: {capability_id}"},
        }

    attempts = ranked[: effective_failover_policy.max_attempts] if effective_failover_policy.enabled else [selected]
    attempt_results: list[dict[str, Any]] = []
    for index, provider in enumerate(attempts):
        start = perf_counter()
        result = _execute_provider(provider, capability_id, params, proxy_url, decision.id)
        latency_ms = (perf_counter() - start) * 1000
        if proxy_url is None:
            _record_direct_usage_event(
                store=store,
                decision=decision,
                provider=provider,
                result=result,
                latency_ms=latency_ms,
            )
        if not result.get("ok"):
            attempt_results.append({"provider_id": provider.provider_id, "ok": False, "result": result})
            if index < len(attempts) - 1 and should_failover(result, effective_failover_policy):
                continue
            break

        try:
            normalized = normalize_output(result.get("body"), provider.output_mapping)
        except OutputNormalizationError as exc:
            normalization_result = {
                "ok": False,
                "error": {"type": "output_normalization", "message": str(exc)},
            }
            attempt_results.append({"provider_id": provider.provider_id, "ok": False, "result": normalization_result})
            if index < len(attempts) - 1 and should_failover(normalization_result, effective_failover_policy):
                continue
            break

        attempt_results.append({"provider_id": provider.provider_id, "ok": True, "result": result})
        return {
            "ok": True,
            "routing_decision": decision.model_dump(mode="json"),
            "attempts": attempt_results,
            "provider_id": provider.provider_id,
            "provider_result": result,
            "normalized_body": normalized,
        }

    return {
        "ok": False,
        "routing_decision": decision.model_dump(mode="json"),
        "attempts": attempt_results,
        "error": {"type": "all_providers_failed", "message": "No provider returned a normalized result."},
    }


def _execute_provider(
    provider: ProviderCandidate,
    capability_id: str,
    params: dict[str, Any],
    proxy_url: str | None,
    routing_decision_id: str,
) -> dict[str, Any]:
    package_dir = provider.metadata.get("package_dir")
    if not package_dir:
        return {
            "ok": False,
            "error": {
                "type": "missing_package_dir",
                "message": f"Provider {provider.provider_id} is missing metadata.package_dir.",
            },
        }

    runner_path = Path(str(package_dir)) / "runner.py"
    if not runner_path.exists():
        return {"ok": False, "error": {"type": "missing_runner", "message": str(runner_path)}}

    runner = _load_runner(runner_path, provider.provider_id)
    previous_env = {
        "API2AGENT_PROVIDER_ID": os.environ.get("API2AGENT_PROVIDER_ID"),
        "API2AGENT_ESTIMATED_COST": os.environ.get("API2AGENT_ESTIMATED_COST"),
        "API2AGENT_PROXY_URL": os.environ.get("API2AGENT_PROXY_URL"),
        "API2AGENT_ROUTING_DECISION_ID": os.environ.get("API2AGENT_ROUTING_DECISION_ID"),
        "API2AGENT_CAPABILITY_ID": os.environ.get("API2AGENT_CAPABILITY_ID"),
    }
    try:
        os.environ["API2AGENT_CAPABILITY_ID"] = capability_id
        os.environ["API2AGENT_PROVIDER_ID"] = provider.provider_id
        os.environ["API2AGENT_ESTIMATED_COST"] = str(provider.estimated_cost)
        os.environ["API2AGENT_ROUTING_DECISION_ID"] = routing_decision_id
        if proxy_url:
            os.environ["API2AGENT_PROXY_URL"] = proxy_url
        result = runner.execute_tool(provider.tool_id, params)
        if isinstance(result, dict):
            result.update({key: value for key, value in _runner_tool_info(runner, provider.tool_id).items() if key not in result})
        return result
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _load_runner(runner_path: Path, provider_id: str):
    module_name = f"api2agent_provider_runner_{provider_id}"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, runner_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load runner: {runner_path}")
    spec.loader.exec_module(module)
    return module


def _runner_tool_info(runner: Any, tool_id: str) -> dict[str, str]:
    for tool in getattr(runner, "CAPABILITY", {}).get("tools", []):
        if tool.get("name") == tool_id:
            return {
                "method": str(tool.get("method") or "UNKNOWN"),
                "path": str(tool.get("path") or tool_id),
            }
    return {}


def _record_direct_usage_event(
    *,
    store: UsageStore,
    decision: RoutingDecision,
    provider: ProviderCandidate,
    result: dict[str, Any],
    latency_ms: float,
) -> None:
    method = result.get("method")
    path = result.get("path")
    if not method or not path:
        return

    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    store.record(
        UsageEvent(
            routing_decision_id=decision.id,
            execution_mode="direct",
            project_id=decision.project_id,
            capability_id=decision.capability_id,
            provider_id=provider.provider_id,
            tool_id=provider.tool_id,
            method=str(method),
            path=str(path),
            status_code=result.get("status_code"),
            success=bool(result.get("ok")),
            latency_ms=latency_ms,
            estimated_cost=provider.estimated_cost,
            error_type=error.get("type"),
        )
    )
