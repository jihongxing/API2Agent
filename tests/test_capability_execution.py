import json
from pathlib import Path

from typer.testing import CliRunner

from api2agent.capabilities.execution import execute_capability
from api2agent.capabilities.models import FailoverPolicy, ProviderCandidate, RoutingPolicy
from api2agent.cli import app
from api2agent.control.storage import UsageStore


runner = CliRunner()


def _write_runner(package_dir: Path, body: dict, ok: bool = True) -> None:
    package_dir.mkdir()
    (package_dir / "runner.py").write_text(
        f"""
CAPABILITY = {{"tools": [{{"name": "get", "method": "GET", "path": "/"}}]}}

def execute_tool(name, params):
    return {{"ok": {ok!r}, "body": {body!r}, "tool": name, "params": params}}
""",
        encoding="utf-8",
    )


def _write_status_runner(package_dir: Path, status_code: int) -> None:
    package_dir.mkdir()
    (package_dir / "runner.py").write_text(
        f"""
CAPABILITY = {{"tools": [{{"name": "get", "method": "GET", "path": "/status/{status_code}"}}]}}

def execute_tool(name, params):
    return {{
        "ok": False,
        "status_code": {status_code},
        "error": {{"type": "http_status", "message": "HTTP {status_code}"}},
    }}
""",
        encoding="utf-8",
    )


def test_execute_capability_selects_provider_and_normalizes_output(tmp_path) -> None:
    package_dir = tmp_path / "ipify"
    _write_runner(package_dir, {"ip": "108.174.61.76"})
    provider = ProviderCandidate(
        id="ipify_public_ip",
        capability_id="public_ip_lookup",
        provider_id="ipify",
        tool_id="get",
        output_mapping={"ip": "$.ip"},
        metadata={"package_dir": str(package_dir)},
    )

    store = UsageStore(tmp_path / "usage.sqlite")
    result = execute_capability(
        providers=[provider],
        capability_id="public_ip_lookup",
        params={},
        store=store,
        policy=RoutingPolicy(strategy="first"),
        preset="test_preset",
    )

    assert result["ok"] is True
    assert result["provider_id"] == "ipify"
    assert result["normalized_body"] == {"ip": "108.174.61.76"}
    assert result["attempts"][0]["provider_id"] == "ipify"
    assert result["attempts"][0]["ok"] is True
    assert result["routing_decision"]["failover_policy"]["enabled"] is False
    assert result["routing_decision"]["selected_provider_id"] == "ipify"
    assert result["routing_decision"]["preset"] == "test_preset"
    stored_decision = store.get_routing_decision(result["routing_decision"]["id"])
    usage_events = store.usage_for_routing_decision(result["routing_decision"]["id"])
    assert stored_decision is not None
    assert stored_decision.selected_provider_id == "ipify"
    assert len(usage_events) == 1
    assert usage_events[0].provider_id == "ipify"
    assert usage_events[0].success is True


def test_execute_capability_reports_normalization_failure(tmp_path) -> None:
    package_dir = tmp_path / "httpbin"
    _write_runner(package_dir, {"origin": "108.174.61.76"})
    provider = ProviderCandidate(
        id="httpbin_public_ip",
        capability_id="public_ip_lookup",
        provider_id="httpbin",
        tool_id="get_ip",
        output_mapping={"ip": "$.ip"},
        metadata={"package_dir": str(package_dir)},
    )

    result = execute_capability(
        providers=[provider],
        capability_id="public_ip_lookup",
        params={},
        store=UsageStore(tmp_path / "usage.sqlite"),
        policy=RoutingPolicy(strategy="first"),
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "all_providers_failed"
    assert result["attempts"][0]["ok"] is False
    assert result["attempts"][0]["result"]["error"]["type"] == "output_normalization"


def test_execute_capability_returns_failed_attempts_before_failover_success(tmp_path) -> None:
    failing_dir = tmp_path / "failing"
    _write_status_runner(failing_dir, 500)
    success_dir = tmp_path / "success"
    _write_runner(success_dir, {"ip": "108.174.61.76"})
    providers = [
        ProviderCandidate(
            id="failing_public_ip",
            capability_id="public_ip_lookup",
            provider_id="failing",
            tool_id="get",
            output_mapping={"ip": "$.ip"},
            metadata={"package_dir": str(failing_dir)},
        ),
        ProviderCandidate(
            id="ipify_public_ip",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            output_mapping={"ip": "$.ip"},
            metadata={"package_dir": str(success_dir)},
        ),
    ]

    result = execute_capability(
        providers=providers,
        capability_id="public_ip_lookup",
        params={},
        store=UsageStore(tmp_path / "usage.sqlite"),
        policy=RoutingPolicy(strategy="first"),
        failover=True,
    )

    assert result["ok"] is True
    assert result["provider_id"] == "ipify"
    assert [attempt["provider_id"] for attempt in result["attempts"]] == ["failing", "ipify"]
    assert [attempt["ok"] for attempt in result["attempts"]] == [False, True]
    assert result["routing_decision"]["failover_policy"]["enabled"] is True
    assert result["routing_decision"]["failover_policy"]["max_attempts"] == 2


def test_execute_capability_stops_on_non_retriable_failover_status(tmp_path) -> None:
    failing_dir = tmp_path / "failing"
    _write_status_runner(failing_dir, 400)
    success_dir = tmp_path / "success"
    _write_runner(success_dir, {"ip": "108.174.61.76"})
    providers = [
        ProviderCandidate(
            id="failing_public_ip",
            capability_id="public_ip_lookup",
            provider_id="failing",
            tool_id="get",
            output_mapping={"ip": "$.ip"},
            metadata={"package_dir": str(failing_dir)},
        ),
        ProviderCandidate(
            id="ipify_public_ip",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            output_mapping={"ip": "$.ip"},
            metadata={"package_dir": str(success_dir)},
        ),
    ]

    store = UsageStore(tmp_path / "usage.sqlite")
    result = execute_capability(
        providers=providers,
        capability_id="public_ip_lookup",
        params={},
        store=store,
        policy=RoutingPolicy(strategy="first"),
        failover_policy=FailoverPolicy(enabled=True, max_attempts=2, retry_on_status_codes=[500]),
    )
    stored_decision = store.get_routing_decision(result["routing_decision"]["id"])

    assert result["ok"] is False
    assert [attempt["provider_id"] for attempt in result["attempts"]] == ["failing"]
    assert result["attempts"][0]["result"]["status_code"] == 400
    assert stored_decision is not None
    assert stored_decision.failover_policy is not None
    assert stored_decision.failover_policy.retry_on_status_codes == [500]


def test_call_command_executes_and_prints_normalized_json(tmp_path) -> None:
    package_dir = tmp_path / "ipify"
    _write_runner(package_dir, {"ip": "108.174.61.76"})
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "ipify_public_ip",
                        "capability_id": "public_ip_lookup",
                        "provider_id": "ipify",
                        "tool_id": "get",
                        "output_mapping": {"ip": "$.ip"},
                        "metadata": {"package_dir": str(package_dir)},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "call",
            str(registry),
            "--capability-id",
            "public_ip_lookup",
            "--db",
            str(tmp_path / "usage.sqlite"),
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["registry_contract_version"] == "provider_registry.v0.1"
    assert payload["ok"] is True
    assert payload["normalized_body"] == {"ip": "108.174.61.76"}


def test_call_command_rejects_missing_provider_package(tmp_path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "missing_public_ip",
                        "capability_id": "public_ip_lookup",
                        "provider_id": "missing",
                        "tool_id": "get",
                        "metadata": {"package_dir": str(tmp_path / "missing-package")},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "call",
            str(registry),
            "--capability-id",
            "public_ip_lookup",
            "--db",
            str(tmp_path / "usage.sqlite"),
            "--json",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid provider package metadata" in result.output
