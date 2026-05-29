import importlib
import sys
from pathlib import Path

from api2agent.generators.package import generate_package
from api2agent.parsers.curl import parse_curl
from api2agent.parsers.openapi import parse_openapi_file


FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


def _load_runner(output_dir: Path):
    sys.modules.pop("runner", None)
    sys.path.insert(0, str(output_dir))
    return importlib.import_module("runner")


def test_execute_tool_sends_query_header_body_and_auth(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "body_query_header.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = {}

        class FakeResponse:
            is_success = True
            status_code = 201

            def json(self):
                return {"ok": True}

        def fake_request(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

        monkeypatch.setattr(runner.httpx, "request", fake_request)
        monkeypatch.setattr(
            runner.os,
            "getenv",
            lambda key: "secret-token" if key == runner.CAPABILITY["auth"]["env"] else None,
        )

        result = runner.execute_tool(
            "create_item",
            {
                "item_id": "123",
                "verbose": True,
                "X-Trace-Id": "trace-123",
                "body": {"name": "demo"},
            },
        )

        assert result["ok"] is True
        assert captured["method"] == "POST"
        assert captured["url"] == "https://api.example.com/items/123"
        assert captured["kwargs"]["params"] == {"verbose": True}
        assert captured["kwargs"]["json"] == {"name": "demo"}
        assert captured["kwargs"]["headers"]["Authorization"] == "Bearer secret-token"
        assert captured["kwargs"]["headers"]["X-Trace-Id"] == "trace-123"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_reports_missing_parameters(tmp_path) -> None:
    capability = parse_openapi_file(FIXTURES / "body_query_header.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        result = runner.execute_tool("create_item", {"item_id": "123"})

        assert result["ok"] is False
        assert result["error"]["type"] == "missing_parameters"
        assert result["error"]["parameters"] == ["body"]
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_reports_missing_auth(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "body_query_header.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        monkeypatch.setattr(runner.os, "getenv", lambda key: None)

        result = runner.execute_tool("create_item", {"item_id": "123", "body": {"name": "demo"}})

        assert result["ok"] is False
        assert result["error"]["type"] == "missing_auth"
        assert result["error"]["env"] == "BODY_QUERY_HEADER_API_TOKEN"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_reports_http_status(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "body_query_header.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        class FakeResponse:
            is_success = False
            status_code = 401

            def json(self):
                return {"message": "unauthorized"}

        monkeypatch.setattr(runner.os, "getenv", lambda key: "secret-token")
        monkeypatch.setattr(runner.httpx, "request", lambda *args, **kwargs: FakeResponse())

        result = runner.execute_tool("create_item", {"item_id": "123", "body": {"name": "demo"}})

        assert result["ok"] is False
        assert result["status_code"] == 401
        assert result["error"]["type"] == "http_status"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_uses_tool_level_base_url(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "servers.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = {}

        class FakeResponse:
            is_success = True
            status_code = 200

            def json(self):
                return {"ok": True}

        def fake_request(method, url, **kwargs):
            captured["url"] = url
            return FakeResponse()

        monkeypatch.setattr(runner.httpx, "request", fake_request)

        result = runner.execute_tool("get_admin", {})

        assert result["ok"] is True
        assert captured["url"] == "https://admin.example.com/admin"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_applies_parameter_defaults(tmp_path, monkeypatch) -> None:
    capability = parse_curl("curl 'https://api.example.com/items?format=json' -H 'X-Trace-Id: trace-123'")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = {}

        class FakeResponse:
            is_success = True
            status_code = 200

            def json(self):
                return {"ok": True}

        def fake_request(method, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

        monkeypatch.setattr(runner.httpx, "request", fake_request)

        result = runner.execute_tool("get_items", {})

        assert result["ok"] is True
        assert captured["url"] == "https://api.example.com/items"
        assert captured["kwargs"]["params"] == {"format": "json"}
        assert captured["kwargs"]["headers"]["X-Trace-Id"] == "trace-123"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_can_call_api2agent_proxy(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "body_query_header.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = {}

        class FakeResponse:
            is_success = True
            status_code = 200
            text = ""

            def json(self):
                return {"ok": True, "proxied": True, "usage_event_id": "evt_123"}

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

        env = {
            runner.CAPABILITY["auth"]["env"]: "secret-token",
            "API2AGENT_PROXY_URL": "http://127.0.0.1:8765",
            "API2AGENT_PROXY_KEY": "proxy-secret",
            "API2AGENT_PROJECT_ID": "local",
            "API2AGENT_PROVIDER_ID": "github",
            "API2AGENT_ESTIMATED_COST": "0.02",
            "API2AGENT_ROUTING_DECISION_ID": "decision_123",
            "API2AGENT_CAPABILITY_ID": "semantic_capability",
        }
        monkeypatch.setattr(runner.os, "getenv", lambda key: env.get(key))
        monkeypatch.setattr(runner.httpx, "post", fake_post)

        result = runner.execute_tool(
            "create_item",
            {
                "item_id": "123",
                "verbose": True,
                "X-Trace-Id": "trace-123",
                "body": {"name": "demo"},
            },
        )

        payload = captured["kwargs"]["json"]

        assert result["proxied"] is True
        assert captured["url"] == "http://127.0.0.1:8765/v1/proxy/call"
        assert captured["kwargs"]["headers"] == {"Authorization": "Bearer proxy-secret"}
        assert payload["project_id"] == "local"
        assert payload["routing_decision_id"] == "decision_123"
        assert payload["capability_id"] == "semantic_capability"
        assert payload["provider_id"] == "github"
        assert payload["tool_id"] == "create_item"
        assert payload["estimated_cost"] == 0.02
        assert payload["request"]["method"] == "POST"
        assert payload["request"]["url"] == "https://api.example.com/items/123"
        assert payload["request"]["params"] == {"verbose": True}
        assert payload["request"]["headers"]["Authorization"] == "Bearer secret-token"
        assert payload["request"]["json"] == {"name": "demo"}
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)
