import importlib
import json
import sys
from pathlib import Path

from api2agent.generators.package import generate_package
from api2agent.parsers.curl import parse_curl
from api2agent.parsers.graphql import parse_graphql_file
from api2agent.parsers.har import parse_har_file
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


def test_execute_tool_wraps_graphql_variables(tmp_path, monkeypatch) -> None:
    capability = parse_graphql_file(Path("tests/fixtures/graphql/basic_manifest.json"))
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = {}

        class FakeResponse:
            is_success = True
            status_code = 200

            def json(self):
                return {"data": {"user": {"login": "octocat"}}}

        def fake_request(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

        monkeypatch.setattr(runner.httpx, "request", fake_request)
        monkeypatch.setattr(
            runner.os,
            "getenv",
            lambda key: "graphql-secret" if key == "GITHUB_GRAPHQL_TOKEN" else None,
        )

        result = runner.execute_tool("get_viewer", {"body": {"login": "octocat"}})

        assert result["ok"] is True
        assert captured["method"] == "POST"
        assert captured["url"] == "https://api.github.com/graphql"
        assert captured["kwargs"]["headers"]["Authorization"] == "Bearer graphql-secret"
        assert captured["kwargs"]["json"] == {
            "query": "query GetViewer($login: String!) { user(login: $login) { login name } }",
            "operationName": "GetViewer",
            "variables": {"login": "octocat"},
        }
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_runs_har_captured_request(tmp_path, monkeypatch) -> None:
    capability = parse_har_file(Path("tests/fixtures/har/basic_capture.har"))
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = {}

        class FakeResponse:
            is_success = True
            status_code = 200

            def json(self):
                return {"id": "123", "name": "Ada"}

        def fake_request(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

        monkeypatch.setattr(runner.httpx, "request", fake_request)
        monkeypatch.setattr(
            runner.os,
            "getenv",
            lambda key: "har-secret" if key == "EXAMPLE_API_TOKEN" else None,
        )

        result = runner.execute_tool("get_users_123", {"verbose": "true", "X-Trace-Id": "trace-456"})

        assert result["ok"] is True
        assert captured["method"] == "GET"
        assert captured["url"] == "https://api.example.com/users/123"
        assert captured["kwargs"]["params"] == {"verbose": "true"}
        assert captured["kwargs"]["headers"] == {
            "Authorization": "Bearer har-secret",
            "X-Trace-Id": "trace-456",
        }
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


def test_execute_tool_respects_endpoint_level_auth(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "mixed_auth.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = []

        class FakeResponse:
            is_success = True
            status_code = 200

            def json(self):
                return {"ok": True}

        def fake_request(method, url, **kwargs):
            captured.append({"method": method, "url": url, "kwargs": kwargs})
            return FakeResponse()

        monkeypatch.setattr(runner.httpx, "request", fake_request)
        monkeypatch.setattr(
            runner.os,
            "getenv",
            lambda key: "admin-secret" if key == "MIXED_AUTH_API_API_KEY" else None,
        )

        public_result = runner.execute_tool("get_public", {})
        secure_result = runner.execute_tool("get_secure", {})
        admin_result = runner.execute_tool("get_admin", {})

        assert public_result["ok"] is True
        assert captured[0]["url"] == "https://api.example.com/public"
        assert captured[0]["kwargs"]["headers"] == {}

        assert secure_result["ok"] is False
        assert secure_result["error"]["type"] == "missing_auth"
        assert secure_result["error"]["env"] == "MIXED_AUTH_API_TOKEN"

        assert admin_result["ok"] is True
        assert captured[1]["url"] == "https://api.example.com/admin"
        assert captured[1]["kwargs"]["headers"] == {"X-Admin-Key": "admin-secret"}
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

        monkeypatch.setenv(runner.CAPABILITY["auth"]["env"], "secret-token")
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
        assert captured["url"] == "https://admin.example.com/v2/admin"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_uses_global_base_url_override(tmp_path, monkeypatch) -> None:
    capability = parse_curl("curl https://api.example.com/items")
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

        monkeypatch.setenv("API2AGENT_BASE_URL", "http://127.0.0.1:9001")
        monkeypatch.setattr(runner.httpx, "request", fake_request)

        result = runner.execute_tool("get_items", {})

        assert result["ok"] is True
        assert captured["url"] == "http://127.0.0.1:9001/items"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_uses_tool_base_url_override_before_global(tmp_path, monkeypatch) -> None:
    capability = parse_curl("curl https://api.example.com/items")
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

        monkeypatch.setenv("API2AGENT_BASE_URL", "http://127.0.0.1:9001")
        monkeypatch.setenv("API2AGENT_TOOL_BASE_URL_GET_ITEMS", "http://127.0.0.1:9002")
        monkeypatch.setattr(runner.httpx, "request", fake_request)

        result = runner.execute_tool("get_items", {})

        assert result["ok"] is True
        assert captured["url"] == "http://127.0.0.1:9002/items"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_rejects_invalid_base_url_override(tmp_path, monkeypatch) -> None:
    capability = parse_curl("curl https://api.example.com/items")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        monkeypatch.setenv("API2AGENT_BASE_URL", "localhost:9001")

        result = runner.execute_tool("get_items", {})

        assert result["ok"] is False
        assert result["error"]["type"] == "invalid_base_url_override"
        assert result["error"]["env"] == "API2AGENT_BASE_URL"
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


def test_execute_tool_applies_credential_injection_patch(tmp_path, monkeypatch) -> None:
    capability = parse_curl("curl 'https://api.example.com/items?format=json'")
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
            captured["kwargs"] = kwargs
            return FakeResponse()

        monkeypatch.setenv("API2AGENT_CREDENTIAL_HEADERS", '{"Authorization":"Bearer secret-token"}')
        monkeypatch.setenv("API2AGENT_CREDENTIAL_QUERY", '{"api_key":"query-secret"}')
        monkeypatch.setattr(runner.httpx, "request", fake_request)

        result = runner.execute_tool("get_items", {})

        assert result["ok"] is True
        assert captured["kwargs"]["headers"]["Authorization"] == "Bearer secret-token"
        assert captured["kwargs"]["params"] == {"format": "json", "api_key": "query-secret"}
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_can_call_api2agent_proxy(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "body_query_header.yaml").model_copy(
        update={"provider_region": "us-east", "provider_regions": ["us-east"]}
    )
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
        assert payload["provider_region"] == "us-east"
        assert payload["tool_id"] == "create_item"
        assert payload["estimated_cost"] == 0.02
        assert payload["request"]["method"] == "POST"
        assert payload["request"]["url"] == "https://api.example.com/items/123"
        assert payload["request"]["params"] == {"verbose": True}
        assert payload["request"]["headers"] == {"X-Trace-Id": "trace-123"}
        assert payload["request"]["json"] == {"name": "demo"}
        assert payload["credential"] == {
            "credential_id": "github_BODY_QUERY_HEADER_API_TOKEN",
            "owner_type": "project",
            "owner_id": "local",
            "provider_id": "github",
            "auth_type": "bearer",
            "injection_mode": "header",
            "injection_name": "Authorization",
            "source": "env",
            "secret_ref": "BODY_QUERY_HEADER_API_TOKEN",
        }
        assert "secret-token" not in json.dumps(payload)
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_proxy_credential_intent_respects_endpoint_level_auth(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "mixed_auth.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = []

        class FakeResponse:
            is_success = True
            status_code = 200
            text = ""

            def json(self):
                return {"ok": True, "proxied": True}

        def fake_post(url, **kwargs):
            captured.append(kwargs["json"])
            return FakeResponse()

        env = {
            "API2AGENT_PROXY_URL": "http://127.0.0.1:8765",
            "API2AGENT_PROJECT_ID": "local",
            "API2AGENT_PROVIDER_ID": "mixed-provider",
        }
        monkeypatch.setattr(runner.os, "getenv", lambda key: env.get(key))
        monkeypatch.setattr(runner.httpx, "post", fake_post)

        public_result = runner.execute_tool("get_public", {})
        secure_result = runner.execute_tool("get_secure", {})
        admin_result = runner.execute_tool("get_admin", {})

        assert public_result["proxied"] is True
        assert "credential" not in captured[0]

        assert secure_result["proxied"] is True
        assert captured[1]["credential"]["auth_type"] == "bearer"
        assert captured[1]["credential"]["secret_ref"] == "MIXED_AUTH_API_TOKEN"

        assert admin_result["proxied"] is True
        assert captured[2]["credential"]["auth_type"] == "api_key"
        assert captured[2]["credential"]["injection_name"] == "X-Admin-Key"
        assert captured[2]["credential"]["secret_ref"] == "MIXED_AUTH_API_API_KEY"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_supports_query_cookie_and_combined_openapi_auth(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "security_combinations.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = []

        class FakeResponse:
            is_success = True
            status_code = 200

            def json(self):
                return {"ok": True}

        def fake_request(method, url, **kwargs):
            captured.append({"method": method, "url": url, "kwargs": kwargs})
            return FakeResponse()

        monkeypatch.setattr(runner.httpx, "request", fake_request)
        monkeypatch.setattr(
            runner.os,
            "getenv",
            lambda key: "secret-token" if key == "SECURITY_COMBINATIONS_API_API_KEY" else None,
        )

        query_result = runner.execute_tool("get_query_auth", {})
        cookie_result = runner.execute_tool("get_cookie_auth", {})
        combined_result = runner.execute_tool("get_combined_auth", {})

        assert query_result["ok"] is True
        assert captured[0]["kwargs"]["params"] == {"api_key": "secret-token"}
        assert captured[0]["kwargs"]["headers"] == {}

        assert cookie_result["ok"] is True
        assert captured[1]["kwargs"]["params"] == {}
        assert captured[1]["kwargs"]["headers"] == {"Cookie": "session=secret-token"}

        assert combined_result["ok"] is True
        assert captured[2]["kwargs"]["params"] == {"api_key": "secret-token"}
        assert captured[2]["kwargs"]["headers"] == {"X-API-Key": "secret-token"}
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_execute_tool_reports_all_missing_combined_auth_envs(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "security_combinations.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        monkeypatch.setattr(runner.os, "getenv", lambda key: None)

        result = runner.execute_tool("get_combined_auth", {})

        assert result["ok"] is False
        assert result["error"]["type"] == "missing_auth"
        assert result["error"]["envs"] == [
            "SECURITY_COMBINATIONS_API_API_KEY",
            "SECURITY_COMBINATIONS_API_API_KEY",
        ]
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_proxy_payload_includes_combined_credential_intents(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "security_combinations.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    runner = _load_runner(output_dir)
    try:
        captured = {}

        class FakeResponse:
            is_success = True
            status_code = 200
            text = ""

            def json(self):
                return {"ok": True, "proxied": True}

        def fake_post(url, **kwargs):
            captured["payload"] = kwargs["json"]
            return FakeResponse()

        env = {
            "API2AGENT_PROXY_URL": "http://127.0.0.1:8765",
            "API2AGENT_PROJECT_ID": "local",
            "API2AGENT_PROVIDER_ID": "security-provider",
        }
        monkeypatch.setattr(runner.os, "getenv", lambda key: env.get(key))
        monkeypatch.setattr(runner.httpx, "post", fake_post)

        result = runner.execute_tool("get_combined_auth", {})

        assert result["proxied"] is True
        credentials = captured["payload"]["credentials"]
        assert [credential["injection_mode"] for credential in credentials] == ["header", "query"]
        assert [credential["injection_name"] for credential in credentials] == ["X-API-Key", "api_key"]
        assert captured["payload"]["credential"] == credentials[0]
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_proxy_payload_provider_region_env_overrides_capability_metadata(tmp_path, monkeypatch) -> None:
    capability = parse_curl("curl https://api.example.com/items", name="example_items").model_copy(
        update={"provider_region": "us-east", "provider_regions": ["us-east"]}
    )
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
            captured["kwargs"] = kwargs
            return FakeResponse()

        env = {
            "API2AGENT_PROXY_URL": "http://127.0.0.1:8765",
            "API2AGENT_PROVIDER_REGION": "cn",
        }
        monkeypatch.setattr(runner.os, "getenv", lambda key: env.get(key))
        monkeypatch.setattr(runner.httpx, "post", fake_post)

        result = runner.execute_tool("get_items", {})

        assert result["proxied"] is True
        assert captured["kwargs"]["json"]["provider_region"] == "cn"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)


def test_proxy_payload_uses_base_url_override(tmp_path, monkeypatch) -> None:
    capability = parse_curl("curl https://api.example.com/items", name="example_items").model_copy(
        update={"provider_region": "us-east", "provider_regions": ["us-east"]}
    )
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
            captured["kwargs"] = kwargs
            return FakeResponse()

        env = {
            "API2AGENT_PROXY_URL": "http://127.0.0.1:8765",
            "API2AGENT_BASE_URL": "http://127.0.0.1:9001/api",
        }
        monkeypatch.setattr(runner.os, "getenv", lambda key: env.get(key))
        monkeypatch.setattr(runner.httpx, "post", fake_post)

        result = runner.execute_tool("get_items", {})

        assert result["proxied"] is True
        assert captured["kwargs"]["json"]["request"]["url"] == "http://127.0.0.1:9001/api/items"
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("runner", None)
