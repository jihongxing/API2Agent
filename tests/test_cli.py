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
    assert kwargs["env"] is None


def test_test_command_allow_write_executes_manual_write_test(tmp_path, monkeypatch) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "manual_write_test.py").write_text("print('write')", encoding="utf-8")

    fake_run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr("api2agent.cli.subprocess.run", fake_run)

    result = runner.invoke(app, ["test", str(package_dir), "--allow-write"])

    assert result.exit_code == 0
    fake_run.assert_called_once()
    args, kwargs = fake_run.call_args
    assert args[0][-1] == "manual_write_test.py"
    assert kwargs["cwd"] == package_dir
    assert kwargs["env"]["API2AGENT_ALLOW_WRITE_TEST"] == "1"


def test_test_command_can_execute_specific_read_tool(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/basic.yaml"))
    package_dir = generate_package(capability, tmp_path / "package")

    fake_run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr("api2agent.cli.subprocess.run", fake_run)

    result = runner.invoke(
        app,
        [
            "test",
            str(package_dir),
            "--tool",
            "get_user",
            "--params",
            '{"user_id": "123"}',
        ],
    )

    assert result.exit_code == 0
    args, kwargs = fake_run.call_args
    assert args[0][1] == "-c"
    assert args[0][-2] == "get_user"
    assert json.loads(args[0][-1]) == {"user_id": "123"}
    assert kwargs["cwd"] == package_dir
    assert kwargs["env"] is None


def test_test_command_blocks_specific_write_tool_without_allow_write(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/unsafe.yaml"))
    package_dir = generate_package(capability, tmp_path / "package")
    fake_run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr("api2agent.cli.subprocess.run", fake_run)

    result = runner.invoke(app, ["test", str(package_dir), "--tool", "create_order"])

    assert result.exit_code != 0
    assert "Write/delete tools require --allow-write" in result.output
    fake_run.assert_not_called()


def test_proxy_command_passes_credential_config(tmp_path, monkeypatch) -> None:
    config = tmp_path / "credentials.yaml"
    config.write_text("credentials: []\n", encoding="utf-8")
    captured = {}

    def fake_run_proxy_server(**kwargs):
        captured.update(kwargs)
        raise KeyboardInterrupt

    monkeypatch.setattr("api2agent.cli.run_proxy_server", fake_run_proxy_server)

    result = runner.invoke(
        app,
        [
            "proxy",
            "--port",
            "8765",
            "--db",
            str(tmp_path / "usage.sqlite"),
            "--credential-config",
            str(config),
        ],
    )

    assert result.exit_code == 0
    assert captured["credential_config"] == config
    assert "Credential config:" in result.output
    assert "Proxy stopped." in result.output


def test_benchmark_package_command_prints_json(tmp_path, monkeypatch) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    captured = {}

    def fake_benchmark(**kwargs):
        captured.update(kwargs)
        return {
            "contract_version": "api2agent.generated_package_latency_benchmark.v0",
            "package_dir": str(package_dir),
            "capability": {
                "name": "example_items",
                "version": "0.1.0",
                "provider_region": "us-east",
                "provider_regions": ["us-east"],
                "source": "curl",
            },
            "tool": {"name": "get_items", "method": "GET", "path": "/items"},
            "iterations": 2,
            "runs": {
                "direct": {
                    "runs": 2,
                    "successful_runs": 2,
                    "failed_runs": 0,
                    "success_rate": 1.0,
                    "p50_latency_ms": 10.0,
                    "p95_latency_ms": 12.0,
                    "results": [],
                }
            },
        }

    monkeypatch.setattr("api2agent.cli.run_generated_package_latency_benchmark", fake_benchmark)

    result = runner.invoke(
        app,
        [
            "benchmark-package",
            str(package_dir),
            "--tool",
            "get_items",
            "--iterations",
            "2",
            "--params",
            '{"limit": 1}',
            "--provider-region",
            "us-east",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["contract_version"] == "api2agent.generated_package_latency_benchmark.v0"
    assert captured["package_dir"] == package_dir
    assert captured["tool_name"] == "get_items"
    assert captured["params"] == {"limit": 1}
    assert captured["iterations"] == 2
    assert captured["env"]["API2AGENT_PROVIDER_REGION"] == "us-east"


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


def test_generate_command_applies_max_tools_during_openapi_parse(tmp_path) -> None:
    paths = {
        f"/items/{index}": {
            "get": {
                "operationId": f"getItem{index}",
                "responses": {"200": {"description": "OK"}},
            }
        }
        for index in range(120)
    }
    spec = tmp_path / "large.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Large API", "version": "1.0.0"},
                "servers": [{"url": "https://api.example.com"}],
                "paths": paths,
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "api2agent-output"

    result = runner.invoke(
        app,
        [
            "generate",
            str(spec),
            "--max-tools",
            "3",
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    capability = json.loads((output_dir / "capability.json").read_text(encoding="utf-8"))
    assert len(capability["tools"]) == 3


def test_generate_command_writes_provider_region_metadata(tmp_path) -> None:
    output_dir = tmp_path / "api2agent-output"

    result = runner.invoke(
        app,
        [
            "generate",
            "--curl",
            "curl https://api.example.com/items",
            "--name",
            "example_items",
            "--provider-region",
            "us-east",
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    capability = json.loads((output_dir / "capability.json").read_text(encoding="utf-8"))
    assert capability["provider_region"] == "us-east"
    assert capability["provider_regions"] == ["us-east"]


def test_generate_command_warns_for_large_unfiltered_openapi_package(tmp_path) -> None:
    paths = {
        f"/items/{index}": {
            "get": {
                "operationId": f"getItem{index}",
                "responses": {"200": {"description": "OK"}},
            }
        }
        for index in range(51)
    }
    spec = tmp_path / "large.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Large API", "version": "1.0.0"},
                "servers": [{"url": "https://api.example.com"}],
                "paths": paths,
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "generate",
            str(spec),
            "--output",
            str(tmp_path / "api2agent-output"),
        ],
    )

    assert result.exit_code == 0
    assert "Warning: generated package contains 51 tools" in result.output
    assert "--include-tag, --include-path, --include-operation, or --max-tools" in result.output


def test_generate_command_does_not_warn_when_large_openapi_is_bounded_by_max_tools(tmp_path) -> None:
    paths = {
        f"/items/{index}": {
            "get": {
                "operationId": f"getItem{index}",
                "responses": {"200": {"description": "OK"}},
            }
        }
        for index in range(51)
    }
    spec = tmp_path / "large.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Large API", "version": "1.0.0"},
                "servers": [{"url": "https://api.example.com"}],
                "paths": paths,
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "generate",
            str(spec),
            "--max-tools",
            "5",
            "--output",
            str(tmp_path / "api2agent-output"),
        ],
    )

    assert result.exit_code == 0
    assert "Warning: generated package contains" not in result.output


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


def test_inspect_command_prints_large_package_summary(tmp_path) -> None:
    paths = {
        f"/repos/{index}": {
            "get": {
                "operationId": f"getRepo{index}",
                "tags": ["repos"],
                "responses": {"200": {"description": "OK"}},
            }
        }
        for index in range(52)
    }
    spec = tmp_path / "large.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Large API", "version": "1.0.0"},
                "servers": [{"url": "https://api.example.com"}],
                "paths": paths,
            }
        ),
        encoding="utf-8",
    )
    package_dir = generate_package(parse_openapi_file(spec), tmp_path / "package")

    result = runner.invoke(app, ["inspect", str(package_dir), "--limit", "2"])

    assert result.exit_code == 0
    assert "Tool count: 52" in result.output
    assert "Safety: read=52" in result.output
    assert "Top tags: repos(52)" in result.output
    assert "Top path prefixes: /repos(52)" in result.output
    assert "Large package hint:" in result.output


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


def test_usage_command_prints_credential_audit_json(tmp_path) -> None:
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record(
        UsageEvent(
            id="event_credential",
            project_id="local",
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            method="GET",
            path="/",
            status_code=401,
            success=False,
            error_type="credential_expired",
            request_metadata={
                "credential": {
                    "credential_id": "cred_demo",
                    "owner_type": "project",
                    "owner_id": "local",
                    "provider_id": "demo",
                    "auth_type": "api_key",
                    "source": "config",
                    "secret_ref": "DEMO_TOKEN",
                    "secret_value": "raw-secret",
                    "status": "active",
                    "expires_at": "2026-01-01T00:00:00+00:00",
                    "rotation_hint": "rotate",
                }
            },
            credential_reference="config:cred_demo",
        )
    )
    store.record(
        UsageEvent(
            id="event_plain",
            project_id="local",
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
        )
    )

    result = runner.invoke(app, ["usage", "--db", str(db), "--credential-audit", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["contract_version"] == "credential_audit.v0.1"
    assert payload["count"] == 1
    assert payload["credential_failure_counts"] == {"credential_expired": 1}
    assert payload["events"][0]["id"] == "event_credential"
    assert payload["events"][0]["credential_reference"] == "config:cred_demo"
    assert payload["events"][0]["credential_metadata"]["credential_id"] == "cred_demo"
    assert "secret_value" not in payload["events"][0]["credential_metadata"]
    assert "raw-secret" not in result.output


def test_usage_command_prints_credential_audit_text(tmp_path) -> None:
    db = tmp_path / "usage.sqlite"
    UsageStore(db).record(
        UsageEvent(
            id="event_credential",
            project_id="local",
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            method="GET",
            path="/",
            status_code=401,
            success=False,
            error_type="credential_disabled",
            request_metadata={
                "credential": {
                    "credential_id": "cred_demo",
                    "owner_type": "project",
                    "owner_id": "local",
                    "status": "disabled",
                    "secret_value": "raw-secret",
                }
            },
            credential_reference="config:cred_demo",
        )
    )

    result = runner.invoke(app, ["usage", "--db", str(db), "--credential-audit"])

    assert result.exit_code == 0
    assert "Credential audit events: 1" in result.output
    assert "credential_disabled: 1" in result.output
    assert "Reference: config:cred_demo" in result.output
    assert "Metadata: id=cred_demo, owner=project:local, status=disabled" in result.output
    assert "raw-secret" not in result.output


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


def test_replay_command_executes_local_generated_package_replay(tmp_path) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "runner.py").write_text(
        """
CAPABILITY = {"tools": [{"name": "get", "method": "GET", "path": "/"}]}

def execute_tool(name, params):
    return {"ok": True, "status_code": 200, "body": {"echo": params["q"]}}
""",
        encoding="utf-8",
    )
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record(
        UsageEvent(
            id="event_local_package",
            execution_mode="direct",
            project_id="local",
            capability_id="echo.get",
            provider_id="echo_provider",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            request_metadata={"params": {"q": "hello"}},
            provider_runtime_reference=f"local_package:{package_dir}",
        )
    )

    result = runner.invoke(app, ["replay", "event_local_package", "--db", str(db), "--execute", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["replayable"] is True
    assert payload["executed"] is True
    assert payload["replay_result"]["ok"] is True
    assert payload["replay_result"]["body"] == {"echo": "hello"}


def test_replay_command_reports_missing_local_package_credential(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TEST_API_TOKEN", raising=False)
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "runner.py").write_text(
        """
CAPABILITY = {"tools": [{"name": "get", "method": "GET", "path": "/"}]}

def execute_tool(name, params):
    return {"ok": True, "status_code": 200, "body": {"ok": True}}
""",
        encoding="utf-8",
    )
    db = tmp_path / "usage.sqlite"
    UsageStore(db).record(
        UsageEvent(
            id="event_credential_replay",
            execution_mode="direct",
            project_id="local",
            capability_id="secure.data.get",
            provider_id="secure",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            request_metadata={
                "params": {},
                "credential": {
                    "credential_id": "cred_secure",
                    "owner_type": "project",
                    "owner_id": "local",
                    "provider_id": "secure",
                    "auth_type": "bearer",
                    "injection_mode": "header",
                    "injection_name": "Authorization",
                    "source": "env",
                    "secret_ref": "TEST_API_TOKEN",
                },
            },
            credential_reference="env:TEST_API_TOKEN",
            provider_runtime_reference=f"local_package:{package_dir}",
        )
    )

    result = runner.invoke(app, ["replay", "event_credential_replay", "--db", str(db), "--execute", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["replayable"] is False
    assert payload["replay_result"]["error"]["type"] == "missing_credential_secret"
    assert "credential" in payload["missing_for_exact_replay"]
    assert "TEST_API_TOKEN" in payload["replay_result"]["error"]["message"]


def test_replay_command_executes_local_package_with_resolved_credential(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_TOKEN", "secret-token")
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "runner.py").write_text(
        """
import json
import os

CAPABILITY = {"tools": [{"name": "get", "method": "GET", "path": "/"}]}

def execute_tool(name, params):
    headers = json.loads(os.getenv("API2AGENT_CREDENTIAL_HEADERS") or "{}")
    return {
        "ok": headers.get("Authorization") == "Bearer secret-token",
        "status_code": 200,
        "body": {"authorized": headers.get("Authorization") == "Bearer secret-token"},
    }
""",
        encoding="utf-8",
    )
    db = tmp_path / "usage.sqlite"
    UsageStore(db).record(
        UsageEvent(
            id="event_credential_replay",
            execution_mode="direct",
            project_id="local",
            capability_id="secure.data.get",
            provider_id="secure",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            request_metadata={
                "params": {},
                "credential": {
                    "credential_id": "cred_secure",
                    "owner_type": "project",
                    "owner_id": "local",
                    "provider_id": "secure",
                    "auth_type": "bearer",
                    "injection_mode": "header",
                    "injection_name": "Authorization",
                    "source": "env",
                    "secret_ref": "TEST_API_TOKEN",
                },
            },
            credential_reference="env:TEST_API_TOKEN",
            provider_runtime_reference=f"local_package:{package_dir}",
        )
    )

    result = runner.invoke(app, ["replay", "event_credential_replay", "--db", str(db), "--execute", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["replayable"] is True
    assert payload["replay_result"]["ok"] is True
    assert payload["replay_result"]["body"] == {"authorized": True}
    assert "secret-token" not in result.output


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


def test_golden_command_lists_filtered_golden_traces(tmp_path) -> None:
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record(
        UsageEvent(
            id="golden_shadow",
            execution_mode="shadow",
            project_id="local",
            capability_id="weather.get",
            provider_id="wttr_in",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
            is_golden=True,
        )
    )
    store.record(
        UsageEvent(
            id="golden_other",
            execution_mode="direct",
            project_id="local",
            capability_id="weather.get",
            provider_id="open_meteo",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
            is_golden=True,
        )
    )

    result = runner.invoke(
        app,
        [
            "golden",
            "--list",
            "--db",
            str(db),
            "--capability-id",
            "weather.get",
            "--provider-id",
            "wttr_in",
            "--execution-mode",
            "shadow",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["contract_version"] == "golden_trace.v0.1"
    assert payload["count"] == 1
    assert payload["golden_traces"][0]["id"] == "golden_shadow"


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


def test_ledger_command_can_filter_golden_rows(tmp_path) -> None:
    db = tmp_path / "usage.sqlite"
    store = UsageStore(db)
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="weather.get",
            provider_id="open_meteo",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
            estimated_cost=0.01,
            is_golden=True,
        )
    )
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="weather.get",
            provider_id="wttr_in",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
            estimated_cost=0.02,
        )
    )

    result = runner.invoke(app, ["ledger", "--db", str(db), "--golden-only", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert len(payload) == 1
    assert payload[0]["provider_id"] == "open_meteo"
