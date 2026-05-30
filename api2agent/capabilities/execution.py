import importlib.util
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

from api2agent.capabilities.failover import build_failover_policy, should_failover
from api2agent.capabilities.models import FailoverPolicy, ProviderCandidate, RoutingDecision, RoutingPolicy
from api2agent.capabilities.normalization import OutputNormalizationError, normalize_output
from api2agent.capabilities.routing import rank_providers, select_provider, select_provider_region
from api2agent.control.models import UsageEvent
from api2agent.control.storage import UsageStore
from api2agent.credentials.models import CredentialDefinition, CredentialInjectionPatch, CredentialResolutionRequest
from api2agent.credentials.resolver import LocalCredentialResolver


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
    include_shadow_metrics: bool = True,
    shadow: bool = False,
    shadow_provider_ids: list[str] | None = None,
) -> dict[str, Any]:
    candidates = [provider for provider in providers if provider.capability_id == capability_id]
    metrics = store.metrics_for_capability(
        capability_id,
        include_shadow=include_shadow_metrics,
        client_region=policy.client_region if policy else None,
    )
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
        client_region=policy.client_region if policy else None,
        selected_provider_id=selected.provider_id if selected else None,
        selected_provider_region=select_provider_region(selected, policy.client_region if policy else None)
        if selected
        else None,
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
    attempted_provider_ids: list[str] = []
    final_result: dict[str, Any] | None = None
    for index, provider in enumerate(attempts):
        attempted_provider_ids.append(provider.provider_id)
        start = perf_counter()
        result = _execute_provider(provider, capability_id, params, proxy_url, decision.id)
        latency_ms = (perf_counter() - start) * 1000
        if proxy_url is None:
            _record_usage_event(
                store=store,
                decision=decision,
                provider=provider,
                result=result,
                params=params,
                latency_ms=latency_ms,
                execution_mode="direct",
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
        final_result = {
            "ok": True,
            "routing_decision": decision.model_dump(mode="json"),
            "attempts": attempt_results,
            "provider_id": provider.provider_id,
            "provider_result": result,
            "normalized_body": normalized,
        }
        break

    shadow_attempts = _run_shadow_attempts(
        store=store,
        decision=decision,
        providers=providers,
        capability_id=capability_id,
        params=params,
        proxy_url=proxy_url,
        routing_decision_id=decision.id,
        attempted_provider_ids=attempted_provider_ids,
        ranked_provider_ids=[provider.provider_id for provider in ranked],
        shadow=shadow,
        shadow_provider_ids=shadow_provider_ids,
    )

    if final_result is not None:
        final_result["shadow_attempts"] = shadow_attempts
        return final_result

    return {
        "ok": False,
        "routing_decision": decision.model_dump(mode="json"),
        "attempts": attempt_results,
        "shadow_attempts": shadow_attempts,
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
    resolved_credential = _resolve_provider_credential(provider, runner, capability_id)
    if not resolved_credential.resolved:
        return {
            "ok": False,
            "error": {
                "type": resolved_credential.error_type or "missing_credential",
                "message": resolved_credential.error_message or "Credential could not be resolved.",
            },
            "credential_reference": resolved_credential.credential_reference,
            "credential_metadata": resolved_credential.redacted_metadata,
            **_runner_tool_info(runner, provider.tool_id),
        }

    previous_env = {
        "API2AGENT_PROVIDER_ID": os.environ.get("API2AGENT_PROVIDER_ID"),
        "API2AGENT_ESTIMATED_COST": os.environ.get("API2AGENT_ESTIMATED_COST"),
        "API2AGENT_PROXY_URL": os.environ.get("API2AGENT_PROXY_URL"),
        "API2AGENT_ROUTING_DECISION_ID": os.environ.get("API2AGENT_ROUTING_DECISION_ID"),
        "API2AGENT_CAPABILITY_ID": os.environ.get("API2AGENT_CAPABILITY_ID"),
        "API2AGENT_CREDENTIAL_HEADERS": os.environ.get("API2AGENT_CREDENTIAL_HEADERS"),
        "API2AGENT_CREDENTIAL_QUERY": os.environ.get("API2AGENT_CREDENTIAL_QUERY"),
        "API2AGENT_CREDENTIAL_BODY": os.environ.get("API2AGENT_CREDENTIAL_BODY"),
    }
    try:
        os.environ["API2AGENT_CAPABILITY_ID"] = capability_id
        os.environ["API2AGENT_PROVIDER_ID"] = provider.provider_id
        os.environ["API2AGENT_ESTIMATED_COST"] = str(provider.estimated_cost)
        os.environ["API2AGENT_ROUTING_DECISION_ID"] = routing_decision_id
        _apply_credential_env(resolved_credential.injection_patch)
        if proxy_url:
            os.environ["API2AGENT_PROXY_URL"] = proxy_url
        result = runner.execute_tool(provider.tool_id, params)
        if isinstance(result, dict):
            result.update({key: value for key, value in _runner_tool_info(runner, provider.tool_id).items() if key not in result})
            result["credential_reference"] = resolved_credential.credential_reference
            result["credential_metadata"] = resolved_credential.redacted_metadata
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


def _resolve_provider_credential(provider: ProviderCandidate, runner: Any, capability_id: str):
    credential = _credential_definition(provider, runner)
    request = CredentialResolutionRequest(
        capability_id=capability_id,
        provider_id=provider.provider_id,
        tool_id=provider.tool_id,
        auth_type=credential.auth_type if credential else "none",
        injection_mode=credential.injection_mode if credential else "none",
        injection_name=credential.injection_name if credential else None,
        credential=credential,
    )
    return LocalCredentialResolver().resolve(request)


def _credential_definition(provider: ProviderCandidate, runner: Any) -> CredentialDefinition | None:
    raw_credential = provider.metadata.get("credential")
    if isinstance(raw_credential, dict):
        return CredentialDefinition.model_validate(
            {
                "owner_id": "local",
                "provider_id": provider.provider_id,
                **raw_credential,
            }
        )

    auth = getattr(runner, "CAPABILITY", {}).get("auth") or {}
    auth_type = auth.get("type") or "none"
    if auth_type == "none":
        return None

    env_name = auth.get("env")
    if not env_name:
        return None

    injection_name = auth.get("header") or ("Authorization" if auth_type == "bearer" else "X-API-Key")
    return CredentialDefinition(
        credential_id=f"{provider.provider_id}_{env_name}",
        provider_id=provider.provider_id,
        auth_type="bearer" if auth_type == "bearer" else "api_key",
        injection_mode="header",
        injection_name=injection_name,
        source="env",
        secret_ref=env_name,
    )


def _apply_credential_env(patch: CredentialInjectionPatch) -> None:
    os.environ["API2AGENT_CREDENTIAL_HEADERS"] = json.dumps(patch.headers, ensure_ascii=False)
    os.environ["API2AGENT_CREDENTIAL_QUERY"] = json.dumps(patch.query, ensure_ascii=False)
    os.environ["API2AGENT_CREDENTIAL_BODY"] = json.dumps(patch.body, ensure_ascii=False)


def _record_usage_event(
    *,
    store: UsageStore,
    decision: RoutingDecision,
    provider: ProviderCandidate,
    result: dict[str, Any],
    params: dict[str, Any],
    latency_ms: float,
    execution_mode: str,
) -> None:
    method = result.get("method")
    path = result.get("path")
    if not method or not path:
        return

    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    store.record(
        UsageEvent(
            routing_decision_id=decision.id,
            execution_mode=execution_mode,
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
            request_metadata={
                "params": params,
                "credential": result.get("credential_metadata"),
            },
            credential_reference=result.get("credential_reference"),
            provider_region=select_provider_region(provider, decision.client_region),
            provider_runtime_reference=f"local_package:{provider.metadata.get('package_dir')}",
        )
    )


def _run_shadow_attempts(
    *,
    store: UsageStore,
    decision: RoutingDecision,
    providers: list[ProviderCandidate],
    capability_id: str,
    params: dict[str, Any],
    proxy_url: str | None,
    routing_decision_id: str,
    attempted_provider_ids: list[str],
    ranked_provider_ids: list[str],
    shadow: bool,
    shadow_provider_ids: list[str] | None,
) -> list[dict[str, Any]]:
    if proxy_url is not None:
        return []

    selected_shadow_ids = shadow_provider_ids or (ranked_provider_ids if shadow else [])
    if not selected_shadow_ids:
        return []

    provider_by_id = {provider.provider_id: provider for provider in providers if provider.capability_id == capability_id}
    attempted = set(attempted_provider_ids)
    shadow_attempts: list[dict[str, Any]] = []
    for provider_id in selected_shadow_ids:
        if provider_id in attempted:
            continue
        provider = provider_by_id.get(provider_id)
        if provider is None:
            shadow_attempts.append(
                {
                    "provider_id": provider_id,
                    "ok": False,
                    "error": {"type": "unknown_shadow_provider", "message": f"No provider: {provider_id}"},
                }
            )
            continue

        start = perf_counter()
        result = _execute_provider(provider, capability_id, params, proxy_url, routing_decision_id)
        latency_ms = (perf_counter() - start) * 1000
        _record_usage_event(
            store=store,
            decision=decision,
            provider=provider,
            result=result,
            params=params,
            latency_ms=latency_ms,
            execution_mode="shadow",
        )
        shadow_attempts.append(
            {
                "provider_id": provider.provider_id,
                "ok": bool(result.get("ok")),
                "status_code": result.get("status_code"),
                "error_type": (result.get("error") or {}).get("type") if isinstance(result.get("error"), dict) else None,
                "latency_ms": latency_ms,
            }
        )
    return shadow_attempts
