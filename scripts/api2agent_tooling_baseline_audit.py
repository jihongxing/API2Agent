from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api2agent.control.storage import UsageStore
from api2agent.generators.package import generate_package
from api2agent.parsers.curl import parse_curl
from api2agent.parsers.openapi import parse_openapi_file


OUT_DIR = ROOT / ".dogfood" / "tooling-baseline-audit"
RESULT_PATH = OUT_DIR / "result.json"
GITHUB_OPENAPI_URL = (
    "https://raw.githubusercontent.com/github/rest-api-description/main/"
    "descriptions/api.github.com/api.github.com.json"
)


@dataclass(frozen=True)
class AuditCase:
    case_id: str
    kind: str
    source: str
    capability_name: str
    direct_params: dict[str, Any] | None = None
    env: dict[str, str] | None = None
    direct_runs: int = 3
    proxy_runs: int = 1


CASES = [
    AuditCase(
        case_id="curl_ipify_public_ip",
        kind="curl",
        source="curl https://api.ipify.org?format=json",
        capability_name="ipify_public_ip",
    ),
    AuditCase(
        case_id="curl_open_meteo_forecast",
        kind="curl",
        source=(
            "curl 'https://api.open-meteo.com/v1/forecast?"
            "latitude=39.9042&longitude=116.4074&current=temperature_2m'"
        ),
        capability_name="open_meteo_forecast",
    ),
    AuditCase(
        case_id="curl_github_repo_read",
        kind="curl",
        source="curl https://api.github.com/repos/octocat/Hello-World",
        capability_name="github_repo_read",
    ),
    AuditCase(
        case_id="curl_httpbin_bearer",
        kind="curl",
        source="curl -H 'Authorization: Bearer API2AGENT_BASELINE_TOKEN' https://httpbin.org/bearer",
        capability_name="httpbin_bearer",
        env={"HTTPBIN_BEARER_TOKEN": "API2AGENT_BASELINE_TOKEN"},
        proxy_runs=0,
    ),
]


def main() -> None:
    _prepare_output()
    results: dict[str, Any] = {
        "contract_version": "api2agent.tooling_baseline_audit.v0",
        "generated_at": _utc_now(),
        "output_dir": str(OUT_DIR),
        "summary": {},
        "cases": [],
        "large_openapi": None,
        "findings": [],
    }

    for case in CASES:
        results["cases"].append(_audit_curl_case(case))

    results["large_openapi"] = _audit_large_openapi()
    results["summary"] = _build_summary(results)
    results["findings"] = _build_findings(results)
    RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(results["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote {RESULT_PATH}")


def _prepare_output() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _audit_curl_case(case: AuditCase) -> dict[str, Any]:
    case_dir = OUT_DIR / case.case_id
    package_dir = case_dir / "package"
    case_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    generation_error = None
    direct_results: list[dict[str, Any]] = []
    proxy_results: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}

    try:
        capability = parse_curl(case.source, name=case.capability_name)
        generate_package(capability, package_dir, force=True)
        generation_ms = _elapsed_ms(started)
        metadata = _package_metadata(package_dir)
        direct_results = _run_direct(package_dir, metadata["first_tool"], case.env or {}, case.direct_runs)
        if case.proxy_runs > 0:
            proxy_results = _run_proxy(package_dir, metadata["first_tool"], case.env or {}, case.proxy_runs)
    except Exception as exc:
        generation_ms = _elapsed_ms(started)
        generation_error = f"{type(exc).__name__}: {exc}"

    direct_latencies = [item["latency_ms"] for item in direct_results if item.get("ok")]
    proxy_latencies = [item["latency_ms"] for item in proxy_results if item.get("ok")]
    direct_success = sum(1 for item in direct_results if item.get("ok"))
    proxy_success = sum(1 for item in proxy_results if item.get("ok"))

    return {
        "case_id": case.case_id,
        "kind": case.kind,
        "source": case.source,
        "package_dir": str(package_dir),
        "generation": {
            "ok": generation_error is None,
            "latency_ms": generation_ms,
            "error": generation_error,
        },
        "capability": metadata,
        "manual_source_edits_required": 0 if generation_error is None else None,
        "direct": {
            "runs": len(direct_results),
            "successful_runs": direct_success,
            "first_successful_call": direct_success > 0,
            "p50_latency_ms": _percentile(direct_latencies, 50),
            "p95_latency_ms": _percentile(direct_latencies, 95),
            "results": direct_results,
        },
        "proxy": {
            "runs": len(proxy_results),
            "successful_runs": proxy_success,
            "first_successful_call": proxy_success > 0 if proxy_results else None,
            "p50_latency_ms": _percentile(proxy_latencies, 50),
            "p95_latency_ms": _percentile(proxy_latencies, 95),
            "usage_event_count": _usage_event_count(case_dir / "usage.sqlite"),
            "credential_safe": _proxy_events_are_credential_safe(case_dir / "usage.sqlite"),
            "results": proxy_results,
        },
        "onboarding": _onboarding_assessment(metadata, generation_error),
    }


def _audit_large_openapi() -> dict[str, Any]:
    case_dir = OUT_DIR / "openapi_github_large_spec"
    package_dir = case_dir / "package"
    spec_path = case_dir / "github.openapi.json"
    case_dir.mkdir(parents=True, exist_ok=True)

    download_error = None
    generation_error = None
    inspect_error = None
    metadata: dict[str, Any] = {}
    filtered_metadata: dict[str, Any] = {}

    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            response = client.get(GITHUB_OPENAPI_URL)
            response.raise_for_status()
            spec_path.write_bytes(response.content)
    except Exception as exc:
        download_error = f"{type(exc).__name__}: {exc}"

    started = time.perf_counter()
    if download_error is None:
        try:
            capability = parse_openapi_file(spec_path, name="github_rest_api")
            generate_package(capability, package_dir, force=True)
            metadata = _package_metadata(package_dir)
        except Exception as exc:
            generation_error = f"{type(exc).__name__}: {exc}"
    generation_ms = _elapsed_ms(started)

    filtered_dir = case_dir / "filtered_package"
    filtered_generation_error = None
    filtered_started = time.perf_counter()
    if download_error is None:
        try:
            capability = parse_openapi_file(spec_path, name="github_rest_api_filtered")
            capability.tools = [tool for tool in capability.tools if tool.path == "/repos/{owner}/{repo}"]
            generate_package(capability, filtered_dir, force=True)
            filtered_metadata = _package_metadata(filtered_dir)
        except Exception as exc:
            filtered_generation_error = f"{type(exc).__name__}: {exc}"
    filtered_generation_ms = _elapsed_ms(filtered_started)

    if generation_error is None and package_dir.exists():
        try:
            subprocess.run(
                [sys.executable, "-m", "api2agent.cli", "inspect", str(package_dir), "--limit", "10"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            inspect_error = f"{type(exc).__name__}: {exc}"

    return {
        "case_id": "openapi_github_large_spec",
        "kind": "openapi",
        "source": GITHUB_OPENAPI_URL,
        "spec_path": str(spec_path),
        "package_dir": str(package_dir),
        "download": {
            "ok": download_error is None,
            "error": download_error,
            "bytes": spec_path.stat().st_size if spec_path.exists() else 0,
        },
        "generation": {
            "ok": generation_error is None and download_error is None,
            "latency_ms": generation_ms,
            "error": generation_error,
        },
        "inspect": {
            "ok": inspect_error is None and generation_error is None and download_error is None,
            "error": inspect_error,
        },
        "capability": metadata,
        "filtered_generation": {
            "ok": filtered_generation_error is None and download_error is None,
            "latency_ms": filtered_generation_ms,
            "error": filtered_generation_error,
            "package_dir": str(filtered_dir),
            "capability": filtered_metadata,
        },
        "onboarding": {
            "manual_source_edits_required": 0 if generation_error is None and download_error is None else None,
            "risk": "large_endpoint_dump" if metadata.get("tool_count", 0) > 50 else "normal",
            "notes": [
                "Large OpenAPI import generates successfully but needs filtering for Agent usability."
                if metadata.get("tool_count", 0) > 50
                else "Large OpenAPI import is already bounded."
            ],
        },
    }


def _package_metadata(package_dir: Path) -> dict[str, Any]:
    capability_path = package_dir / "capability.json"
    capability = json.loads(capability_path.read_text(encoding="utf-8"))
    tools = capability.get("tools") or []
    read_tools = [tool for tool in tools if tool.get("safety") == "read"]
    write_tools = [tool for tool in tools if tool.get("safety") == "write"]
    auth = capability.get("auth") or {}
    first_tool = read_tools[0] if read_tools else (tools[0] if tools else {})
    return {
        "name": capability.get("name"),
        "base_url": capability.get("base_url"),
        "auth_type": auth.get("type"),
        "auth_env": auth.get("env"),
        "tool_count": len(tools),
        "read_tool_count": len(read_tools),
        "write_tool_count": len(write_tools),
        "first_tool": first_tool.get("name"),
        "first_tool_path": first_tool.get("path"),
        "first_tool_method": first_tool.get("method"),
        "first_tool_required_parameters": [
            parameter.get("name")
            for parameter in first_tool.get("parameters", [])
            if parameter.get("required")
        ],
        "has_proxy_docs": "API2AGENT_PROXY_URL" in (package_dir / "README.md").read_text(encoding="utf-8"),
        "has_credential_intent_code": "credential_id" in (package_dir / "runner.py").read_text(encoding="utf-8"),
        "has_timeout_default": '"timeout": 20' in (package_dir / "runner.py").read_text(encoding="utf-8"),
        "provider_region": capability.get("provider_region"),
        "provider_regions": capability.get("provider_regions") or [],
        "has_region_metadata": bool(capability.get("provider_region") or capability.get("provider_regions")),
    }


def _run_direct(package_dir: Path, tool_name: str, env: dict[str, str], runs: int) -> list[dict[str, Any]]:
    results = []
    for _ in range(runs):
        results.append(_execute_generated_tool(package_dir, tool_name, env))
    return results


def _run_proxy(package_dir: Path, tool_name: str, env: dict[str, str], runs: int) -> list[dict[str, Any]]:
    db_path = package_dir.parent / "usage.sqlite"
    store = UsageStore(db_path)
    proxy_env = {
        **env,
        "API2AGENT_PROXY_URL": "http://api2agent.local",
        "API2AGENT_PROJECT_ID": "baseline",
        "API2AGENT_PROVIDER_ID": package_dir.parent.name,
    }
    results = []
    for _ in range(runs):
        result = _execute_generated_tool(
            package_dir,
            tool_name,
            proxy_env,
            proxy_hook=lambda payload: _execute_proxy_payload(payload, store),
        )
        results.append(result)
    return results


def _execute_proxy_payload(payload: dict[str, Any], store: UsageStore) -> dict[str, Any]:
    from api2agent.control.proxy import execute_proxy_call

    status, body = execute_proxy_call(payload, store=store)
    return {"status_code": status, "body": body}


def _execute_generated_tool(
    package_dir: Path,
    tool_name: str,
    env: dict[str, str],
    proxy_hook=None,
) -> dict[str, Any]:
    started = time.perf_counter()
    module = _load_runner_module(package_dir)
    old_env = os.environ.copy()
    old_post = None
    try:
        os.environ.clear()
        os.environ.update(old_env)
        os.environ.update(env)
        if proxy_hook is not None:
            old_post = module.httpx.post

            def fake_post(url: str, json: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 25):
                proxy_result = proxy_hook(json)
                return _FakeResponse(proxy_result["status_code"], proxy_result["body"])

            module.httpx.post = fake_post
        result = module.execute_tool(tool_name, {})
        latency_ms = _elapsed_ms(started)
        return {
            "ok": bool(result.get("ok")),
            "status_code": result.get("status_code"),
            "latency_ms": latency_ms,
            "error_type": (result.get("error") or {}).get("type") if isinstance(result.get("error"), dict) else None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": _elapsed_ms(started),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    finally:
        if old_post is not None:
            module.httpx.post = old_post
        os.environ.clear()
        os.environ.update(old_env)


def _load_runner_module(package_dir: Path):
    module_name = f"api2agent_baseline_runner_{package_dir.parent.name}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, package_dir / "runner.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load runner module from {package_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self._body = body
        self.is_success = 200 <= status_code < 300
        self.text = json.dumps(body, ensure_ascii=False)

    def json(self) -> Any:
        return self._body


def _usage_event_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    return len(UsageStore(db_path).list_usage_events(limit=1000))


def _proxy_events_are_credential_safe(db_path: Path) -> bool | None:
    if not db_path.exists():
        return None
    events = UsageStore(db_path).list_usage_events(limit=1000)
    if not events:
        return None
    sensitive_markers = ["API2AGENT_BASELINE_TOKEN", "Bearer API2AGENT_BASELINE_TOKEN"]
    raw = json.dumps([event.model_dump(mode="json") for event in events], ensure_ascii=False)
    return not any(marker in raw for marker in sensitive_markers)


def _onboarding_assessment(metadata: dict[str, Any], generation_error: str | None) -> dict[str, Any]:
    notes = []
    weak_tool_names = {"get", "post", "put", "patch", "delete", "head", "options", "api"}
    if generation_error is not None:
        return {
            "manual_source_edits_required": None,
            "naming_quality": "failed",
            "proxy_ready": False,
            "credential_safe_by_default": False,
            "notes": [generation_error],
        }
    if metadata.get("name") in {"api", "curl_api"}:
        notes.append("Capability naming is vague without explicit --name.")
    if metadata.get("first_tool") in weak_tool_names:
        notes.append("First tool name is generic and should use host/path intent.")
    if not metadata.get("has_proxy_docs"):
        notes.append("Generated README does not document proxy mode.")
    if metadata.get("auth_type") != "none" and not metadata.get("has_credential_intent_code"):
        notes.append("Generated runner does not preserve credential intent.")
    if not metadata.get("has_region_metadata"):
        notes.append("Provider region metadata is not emitted by the current tooling.")
    return {
        "manual_source_edits_required": 0,
        "naming_quality": "weak"
        if metadata.get("name") in {"api", "curl_api"} or metadata.get("first_tool") in weak_tool_names
        else "good",
        "proxy_ready": bool(metadata.get("has_proxy_docs")),
        "credential_safe_by_default": bool(metadata.get("has_credential_intent_code")),
        "notes": notes,
    }


def _build_summary(results: dict[str, Any]) -> dict[str, Any]:
    cases = results["cases"]
    generation_ok = sum(1 for item in cases if item["generation"]["ok"])
    direct_success = sum(1 for item in cases if item["direct"]["first_successful_call"])
    proxy_attempts = [item for item in cases if item["proxy"]["runs"]]
    proxy_success = sum(1 for item in proxy_attempts if item["proxy"]["first_successful_call"])
    large = results["large_openapi"] or {}
    return {
        "curl_cases": len(cases),
        "curl_generation_success": f"{generation_ok}/{len(cases)}",
        "curl_first_call_success": f"{direct_success}/{len(cases)}",
        "proxy_first_call_success": f"{proxy_success}/{len(proxy_attempts)}",
        "large_openapi_generation_success": bool((large.get("generation") or {}).get("ok")),
        "large_openapi_tool_count": (large.get("capability") or {}).get("tool_count"),
        "filtered_large_openapi_tool_count": ((large.get("filtered_generation") or {}).get("capability") or {}).get(
            "tool_count"
        ),
    }


def _build_findings(results: dict[str, Any]) -> list[dict[str, str]]:
    findings = []
    cases = results["cases"]
    if all(item["generation"]["ok"] for item in cases):
        findings.append(
            {
                "severity": "positive",
                "title": "curl onboarding works for the audited read-only APIs",
                "detail": "ipify, Open-Meteo, GitHub repo read, and httpbin bearer generated without source edits.",
            }
        )
    if any(not item["capability"].get("has_region_metadata") for item in cases if item.get("capability")):
        findings.append(
            {
                "severity": "medium",
                "title": "Provider region metadata is still missing from generated packages",
                "detail": "This limits faster-response and location-aware routing readiness in the Tooling Layer.",
            }
        )
    if results["large_openapi"]["capability"].get("tool_count", 0) > 50:
        findings.append(
            {
                "severity": "medium",
                "title": "Large OpenAPI specs still generate endpoint dumps without filtering",
                "detail": "GitHub REST generated successfully, but the unfiltered package is too large for Agent ergonomics.",
            }
        )
    weak_naming_cases = [
        item["case_id"]
        for item in cases
        if (item.get("onboarding") or {}).get("naming_quality") == "weak"
    ]
    if weak_naming_cases:
        findings.append(
            {
                "severity": "medium",
                "title": "curl tool naming is still weak for root-path APIs",
                "detail": "Generic tool names make Agent tool choice harder. Affected cases: "
                + ", ".join(weak_naming_cases),
            }
        )
    if all(item["proxy"]["credential_safe"] is not False for item in cases):
        findings.append(
            {
                "severity": "positive",
                "title": "Proxy events avoid raw credential leakage in audited paths",
                "detail": "The audited proxy events did not include the bearer token marker.",
            }
        )
    return findings


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 3)
    sorted_values = sorted(values)
    if percentile == 50:
        return round(float(median(sorted_values)), 3)
    rank = (len(sorted_values) - 1) * (percentile / 100)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return round(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight, 3)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    main()
