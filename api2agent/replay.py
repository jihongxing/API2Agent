import importlib.util
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

import httpx

from api2agent.adapters.open_meteo import OpenMeteoWeatherAdapter
from api2agent.adapters.wttr_in import WttrInWeatherAdapter
from api2agent.control.models import UsageEvent


SDK_ADAPTERS = {
    "sdk:OpenMeteoWeatherAdapter": OpenMeteoWeatherAdapter,
    "sdk:WttrInWeatherAdapter": WttrInWeatherAdapter,
}


def can_execute_replay(event: UsageEvent) -> bool:
    return bool(
        event.request_metadata
        and event.provider_runtime_reference
        and (
            event.provider_runtime_reference in SDK_ADAPTERS
            or event.provider_runtime_reference == "proxy:http"
            or str(event.provider_runtime_reference).startswith("local_package:")
        )
        and event.credential_reference is None
    )


def execute_replay(event: UsageEvent) -> dict[str, Any]:
    if not event.request_metadata:
        return _error("missing_request_metadata", "Usage event has no request metadata.")
    if not event.provider_runtime_reference:
        return _error("missing_provider_runtime_reference", "Usage event has no provider runtime reference.")
    if event.credential_reference:
        return _error("credential_required", "Replay cannot execute because the original call referenced credentials.")

    if event.provider_runtime_reference in SDK_ADAPTERS:
        return _execute_sdk_replay(event)
    if event.provider_runtime_reference == "proxy:http":
        return _execute_http_replay(event)
    if str(event.provider_runtime_reference).startswith("local_package:"):
        return _execute_local_package_replay(event)
    return _error("unsupported_provider_runtime", f"Unsupported replay runtime: {event.provider_runtime_reference}")


def _execute_sdk_replay(event: UsageEvent) -> dict[str, Any]:
    adapter_class = SDK_ADAPTERS[str(event.provider_runtime_reference)]
    input_data = event.request_metadata.get("input") if event.request_metadata else None
    if not isinstance(input_data, dict):
        return _error("missing_sdk_input", "SDK replay requires request_metadata.input.")

    result = adapter_class().call(input_data)
    return {
        "ok": result.ok,
        "runtime": event.provider_runtime_reference,
        "provider_id": result.provider_id,
        "status_code": result.status_code,
        "latency_ms": result.latency_ms,
        "output": result.output,
        "error_type": result.error_type,
        "error_message": result.error_message,
    }


def _execute_http_replay(event: UsageEvent) -> dict[str, Any]:
    metadata = event.request_metadata or {}
    method = str(metadata.get("method") or event.method or "GET").upper()
    url = metadata.get("url")
    if not isinstance(url, str) or not url:
        return _error("missing_http_url", "HTTP replay requires request_metadata.url.")

    start = perf_counter()
    response = httpx.request(
        method,
        url,
        params=metadata.get("params") or {},
        json=metadata.get("json"),
        headers=_replay_headers(metadata.get("headers") or {}),
        timeout=20,
    )
    latency_ms = (perf_counter() - start) * 1000
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text

    return {
        "ok": response.is_success,
        "runtime": event.provider_runtime_reference,
        "provider_id": event.provider_id,
        "status_code": response.status_code,
        "latency_ms": latency_ms,
        "body": body,
        "error_type": None if response.is_success else "http_status",
    }


def _execute_local_package_replay(event: UsageEvent) -> dict[str, Any]:
    package_dir = _local_package_dir(event.provider_runtime_reference)
    if package_dir is None:
        return _error("invalid_local_package_runtime", "Local package replay requires local_package:<package_dir>.")
    runner_path = package_dir / "runner.py"
    if not runner_path.exists():
        return _error("missing_local_package_runner", f"Generated runner not found: {runner_path}")

    metadata = event.request_metadata or {}
    params = metadata.get("params")
    if not isinstance(params, dict):
        return _error("missing_local_package_params", "Local package replay requires request_metadata.params.")

    runner = _load_local_runner(runner_path, event.id)
    start = perf_counter()
    result = runner.execute_tool(event.tool_id, params)
    latency_ms = (perf_counter() - start) * 1000
    if not isinstance(result, dict):
        return _error("invalid_local_package_result", "Generated runner returned a non-object result.")

    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "runtime": event.provider_runtime_reference,
        "provider_id": event.provider_id,
        "status_code": result.get("status_code"),
        "latency_ms": latency_ms,
        "body": result.get("body"),
        "error_type": error.get("type"),
        "error_message": error.get("message"),
    }


def _local_package_dir(runtime: str | None) -> Path | None:
    if not runtime or not runtime.startswith("local_package:"):
        return None
    raw_path = runtime.removeprefix("local_package:")
    if not raw_path:
        return None
    return Path(raw_path)


def _load_local_runner(runner_path: Path, event_id: str):
    module_name = f"api2agent_replay_runner_{event_id.replace('-', '_')}"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, runner_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load runner: {runner_path}")
    spec.loader.exec_module(module)
    return module


def _replay_headers(headers: dict[str, Any]) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in headers.items()
        if value != "[REDACTED]"
    }


def _error(error_type: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "type": error_type,
            "message": message,
        },
    }
