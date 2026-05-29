from pathlib import Path
from unittest.mock import Mock
import json

from typer.testing import CliRunner

from api2agent.adapters.models import AdapterResult
from api2agent.control.models import UsageEvent
from api2agent.control.storage import UsageStore
from api2agent.capabilities.models import RoutingDecision
from api2agent.generators.package import generate_package
from api2agent.cli import app
from api2agent import replay as replay_module
from api2agent.parsers.curl import parse_curl
from api2agent.parsers.openapi import parse_openapi_file


runner = CliRunner()


def test_test_command_executes_smoke_test(tmp_path, monkeypatch) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "smoke_test.py").write_text("print('ok')", encoding="utf-8")

    fake_run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr("api2agent.cli.subprocess.run", fake_run)

    result = runner.invoke(app, ["test", str(package_dir)])

    assert result.exit_code == 0
    fake_run.assert_called_once()
    args, kwargs = fake_run.call_args
    assert args[0][-1] == "smoke_test.py"
    assert kwargs["cwd"] == package_dir


def test_generate_command_refuses_non_empty_output_without_force(tmp_path) -> None:
    output_dir = tmp_path / "api2agent-output"
    output_dir.mkdir()
    (output_dir / "custom.txt").write_text("keep me", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "generate",
            "tests/fixtures/openapi/basic.yaml",
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code != 0
    assert "Use --force" in result.output


def test_generate_command_allows_force(tmp_path) -> None:
    output_dir = tmp_path / "api2agent-output"
    output_dir.mkdir()
    (output_dir / "custom.txt").write_text("keep me", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "generate",
            "tests/fixtures/openapi/basic.yaml",
            "--output",
            str(output_dir),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "capability.json").exists()
    assert (output_dir / "custom.txt").read_text(encoding="utf-8") == "keep me"


def test_generate_command_filters_tools_by_tag_and_max_tools(tmp_path) -> None:
    output_dir = tmp_path / "api2agent-output"

    result = runner.invoke(
        app,
        [
            "generate",
            "tests/fixtures/openapi/multi_tools.yaml",
            "--include-tag",
            "repos",
            "--max-tools",
            "1",
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    capability = json.loads((output_dir / "capability.json").read_text(encoding="utf-8"))
    assert [tool["name"] for tool in capability["tools"]] == ["list_repos"]


def test_generate_command_fails_when_filters_match_no_tools(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            "tests/fixtures/openapi/multi_tools.yaml",
            "--include-tag",
            "missing",
            "--output",
            str(tmp_path / "api2agent-output"),
        ],
    )

    assert result.exit_code != 0
    assert "No tools matched" in result.output


def test_test_command_propagates_smoke_test_failure(tmp_path, monkeypatch) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "smoke_test.py").write_text("raise SystemExit(1)", encoding="utf-8")

    fake_run = Mock(return_value=Mock(returncode=2))
    monkeypatch.setattr("api2agent.cli.subprocess.run", fake_run)

    result = runner.invoke(app, ["test", str(package_dir)])

    assert result.exit_code == 2


def test_run_command_executes_mcp_server(tmp_path, monkeypatch) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "mcp_server.py").write_text("print('server')", encoding="utf-8")

    fake_run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr("api2agent.cli.subprocess.run", fake_run)

    result = runner.invoke(app, ["run", str(package_dir)])

    assert result.exit_code == 0
    fake_run.assert_called_once()
    args, kwargs = fake_run.call_args
    assert args[0][-1] == "mcp_server.py"
    assert kwargs["cwd"] == package_dir


def test_inspect_command_prints_capability_summary(tmp_path) -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/body_query_header.yaml"))
    package_dir = generate_package(capability, tmp_path / "package")

    result = runner.invoke(app, ["inspect", str(package_dir)])

    assert result.exit_code == 0
    assert "Capability: body_query_header_api" in result.output
    assert "Auth: bearer via Authorization, env=BODY_QUERY_HEADER_API_TOKEN" in result.output
    assert "create_item: POST /items/{item_id} [write]" in result.output
    assert "required=item_id, body" in result.output


def test_inspect_command_can_print_json(tmp_path) -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/basic.yaml"))
    package_dir = generate_package(capability, tmp_path / "package")

    result = runner.invoke(app, ["inspect", str(package_dir), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["name"] == "basic_api"


def test_inspect_command_handles_tools_without_request_body(tmp_path) -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/basic.yaml"))
    package_dir = generate_package(capability, tmp_path / "package")

    result = runner.invoke(app, ["inspect", str(package_dir)])

    assert result.exit_code == 0
    assert "get_user: GET /users/{user_id} [read] required=user_id" in result.output
    assert "path: user_id string required" in result.output


def test_inspect_command_prints_parameter_and_body_details(tmp_path) -> None:
    capability = parse_curl(
        """curl 'https://api.example.com/items?verbose=true' \
        -H 'X-Trace-Id: trace-123' \
        --json '{"name":"demo","active":true}'"""
    )
    package_dir = generate_package(capability, tmp_path / "package")

    result = runner.invoke(app, ["inspect", str(package_dir)])

    assert result.exit_code == 0
    assert "query: verbose string default=true" in result.output
    assert "header: X-Trace-Id string default=trace-123" in result.output
    assert "body: object {name:string, active:boolean} required" in result.output


def test_inspect_command_truncates_large_tool_lists(tmp_path) -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/multi_tools.yaml"))
    package_dir = generate_package(capability, tmp_path / "package")

    result = runner.invoke(app, ["inspect", str(package_dir), "--limit", "2"])

    assert result.exit_code == 0
    assert "showing 2 of 4 tools" in result.output
    assert "list_users" in result.output
    assert "create_user" in result.output
    assert "list_repos" not in result.output


def test_ledger_command_prints_json_rows(tmp_path) -> None:
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            latency_ms=120,
            estimated_cost=0.01,
        )
    )

    result = runner.invoke(app, ["ledger", "--db", str(db), "--project-id", "local", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload[0]["project_id"] == "local"
    assert payload[0]["capability_id"] == "public_ip_lookup"
    assert payload[0]["provider_id"] == "ipify"
    assert payload[0]["estimated_cost"] == 0.01


def test_decision_command_prints_decision_and_usage_events(tmp_path) -> None:
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record_routing_decision(
        RoutingDecision(
            id="decision_123",
            project_id="local",
            capability_id="public_ip_lookup",
            strategy="first",
            selected_provider_id="ipify",
            ranked_provider_ids=["ipify"],
        )
    )
    store.record(
        UsageEvent(
            routing_decision_id="decision_123",
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            latency_ms=100,
            estimated_cost=0.01,
        )
    )

    result = runner.invoke(app, ["decision", "decision_123", "--db", str(db), "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["contract_version"] == "decision_usage.v0.1"
    assert payload["decision"]["id"] == "decision_123"
    assert payload["decision"]["selected_provider_id"] == "ipify"
    assert payload["usage_event_count"] == 1
    assert payload["usage_events"][0]["provider_id"] == "ipify"


def test_replay_command_returns_preflight_audit(tmp_path) -> None:
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record_routing_decision(
        RoutingDecision(
            id="decision_123",
            project_id="local",
            capability_id="public_ip_lookup",
            strategy="first",
            selected_provider_id="ipify",
            ranked_provider_ids=["ipify"],
        )
    )
    store.record(
        UsageEvent(
            id="event_123",
            routing_decision_id="decision_123",
            execution_mode="direct",
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            latency_ms=100,
            estimated_cost=0.01,
        )
    )

    result = runner.invoke(app, ["replay", "event_123", "--db", str(db), "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["contract_version"] == "replay.v0.1"
    assert payload["replayable"] is False
    assert payload["exact_replay_metadata_ready"] is False
    assert payload["usage_event"]["id"] == "event_123"
    assert payload["routing_decision"]["id"] == "decision_123"
    assert "request_metadata" in payload["missing_for_exact_replay"]


def test_replay_command_executes_supported_sdk_replay(tmp_path, monkeypatch) -> None:
    class FakeReplayAdapter:
        provider_id = "fake_weather"
        capability_id = "weather.get"

        def call(self, input):
            return AdapterResult(
                ok=True,
                capability_id=self.capability_id,
                provider_id=self.provider_id,
                output={"city": input["city"], "temperature_2m": 17.0},
                status_code=200,
                latency_ms=5,
            )

    monkeypatch.setitem(replay_module.SDK_ADAPTERS, "sdk:FakeReplayAdapter", FakeReplayAdapter)
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record(
        UsageEvent(
            id="event_replay",
            execution_mode="direct",
            project_id="local",
            capability_id="weather.get",
            provider_id="fake_weather",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=500,
            success=False,
            request_metadata={"input": {"city": "San Francisco"}},
            provider_runtime_reference="sdk:FakeReplayAdapter",
        )
    )

    result = runner.invoke(app, ["replay", "event_replay", "--db", str(db), "--execute", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["replayable"] is True
    assert payload["executed"] is True
    assert payload["replay_result"]["ok"] is True
    assert payload["replay_result"]["output"]["temperature_2m"] == 17.0


def test_replay_command_can_record_replay_usage_event(tmp_path, monkeypatch) -> None:
    class FakeReplayAdapter:
        provider_id = "fake_weather"
        capability_id = "weather.get"

        def call(self, input):
            return AdapterResult(
                ok=True,
                capability_id=self.capability_id,
                provider_id=self.provider_id,
                output={"city": input["city"]},
                status_code=200,
                latency_ms=5,
            )

    monkeypatch.setitem(replay_module.SDK_ADAPTERS, "sdk:FakeReplayAdapter", FakeReplayAdapter)
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record(
        UsageEvent(
            id="event_replay",
            execution_mode="direct",
            project_id="local",
            capability_id="weather.get",
            provider_id="fake_weather",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=500,
            success=False,
            request_metadata={"input": {"city": "San Francisco"}},
            provider_runtime_reference="sdk:FakeReplayAdapter",
        )
    )

    result = runner.invoke(app, ["replay", "event_replay", "--db", str(db), "--execute", "--record", "--json"])
    payload = json.loads(result.output)
    replay_event = UsageStore(db).get_usage_event(payload["recorded_usage_event_id"])

    assert result.exit_code == 0
    assert payload["recorded_usage_event_id"]
    assert replay_event is not None
    assert replay_event.execution_mode == "replay"
    assert replay_event.request_metadata["replay_source_event_id"] == "event_replay"


def test_golden_command_marks_usage_event(tmp_path) -> None:
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record(
        UsageEvent(
            id="event_golden",
            execution_mode="direct",
            project_id="local",
            capability_id="weather.get",
            provider_id="open_meteo",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
        )
    )

    result = runner.invoke(app, ["golden", "event_golden", "--db", str(db), "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["is_golden"] is True
    assert payload["usage_event"]["is_golden"] is True


def test_decision_command_preserves_stable_contract_fields(tmp_path) -> None:
    fixture = json.loads(Path("tests/fixtures/decision_audit/failover_audit.json").read_text(encoding="utf-8"))
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record_routing_decision(RoutingDecision.model_validate(fixture["decision"]))
    for item in fixture["usage_events"]:
        store.record(UsageEvent.model_validate(item))

    result = runner.invoke(app, ["decision", "decision_fixture_001", "--db", str(db), "--json"])
    payload = json.loads(result.output)

    stable_top_level = {"contract_version", "decision", "usage_events", "usage_event_count"}
    stable_decision = {
        "id",
        "project_id",
        "capability_id",
        "strategy",
        "preset",
        "selected_provider_id",
        "ranked_provider_ids",
        "metrics",
        "failover_policy",
        "created_at",
    }
    stable_failover_policy = {
        "enabled",
        "max_attempts",
        "retry_on_error_types",
        "retry_on_status_codes",
    }
    stable_usage_event = {
        "id",
        "routing_decision_id",
        "execution_mode",
        "project_id",
        "capability_id",
        "provider_id",
        "tool_id",
        "method",
        "path",
        "status_code",
        "success",
        "latency_ms",
        "estimated_cost",
        "error_type",
        "request_metadata",
        "credential_reference",
        "provider_runtime_reference",
        "is_golden",
        "created_at",
    }

    assert result.exit_code == 0
    assert payload["contract_version"] == "decision_usage.v0.1"
    assert stable_top_level <= set(payload)
    assert stable_decision <= set(payload["decision"])
    assert stable_failover_policy <= set(payload["decision"]["failover_policy"])
    assert payload["usage_event_count"] == 2
    assert stable_usage_event <= set(payload["usage_events"][0])
    assert stable_usage_event <= set(payload["usage_events"][1])


def test_decision_command_preserves_direct_execution_mode_fixture(tmp_path) -> None:
    fixture = json.loads(Path("tests/fixtures/decision_audit/direct_audit.json").read_text(encoding="utf-8"))
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record_routing_decision(RoutingDecision.model_validate(fixture["decision"]))
    for item in fixture["usage_events"]:
        store.record(UsageEvent.model_validate(item))

    result = runner.invoke(app, ["decision", "decision_fixture_direct_001", "--db", str(db), "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["usage_event_count"] == 1
    assert payload["usage_events"][0]["execution_mode"] == "direct"


def test_ledger_command_preserves_stable_contract_fields(tmp_path) -> None:
    fixture = json.loads(Path("tests/fixtures/usage_ledger/direct_proxy_events.json").read_text(encoding="utf-8"))
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    for item in fixture["usage_events"]:
        store.record(UsageEvent.model_validate(item))

    result = runner.invoke(app, ["ledger", "--db", str(db), "--project-id", "local", "--group-by-mode", "--json"])
    payload = json.loads(result.output)
    stable_ledger_row = {
        "project_id",
        "capability_id",
        "provider_id",
        "execution_mode",
        "total_calls",
        "successful_calls",
        "failed_calls",
        "success_rate",
        "average_latency_ms",
        "estimated_cost",
    }

    assert result.exit_code == 0
    assert payload == fixture["expected_group_by_mode_rows"]
    assert stable_ledger_row <= set(payload[0])
    assert stable_ledger_row <= set(payload[1])


def test_ledger_command_filters_by_provider(tmp_path) -> None:
    fixture = json.loads(Path("tests/fixtures/usage_ledger/direct_proxy_events.json").read_text(encoding="utf-8"))
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    for item in fixture["usage_events"]:
        store.record(UsageEvent.model_validate(item))

    result = runner.invoke(
        app,
        [
            "ledger",
            "--db",
            str(db),
            "--project-id",
            "local",
            "--capability-id",
            "public_ip_lookup",
            "--provider-id",
            "ipify",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert len(payload) == 1
    assert payload[0]["provider_id"] == "ipify"
    assert payload[0]["total_calls"] == 2
