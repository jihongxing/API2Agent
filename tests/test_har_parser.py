from pathlib import Path

import pytest

from api2agent.ir.models import SafetyLevel
from api2agent.parsers.har import count_har_entries_file, parse_har, parse_har_file


FIXTURES = Path(__file__).parent / "fixtures" / "har"


def test_parse_har_capture_to_capability() -> None:
    capability = parse_har_file(FIXTURES / "basic_capture.har")

    assert capability.name == "example_api"
    assert capability.base_url == "https://api.example.com"
    assert capability.source.endswith("basic_capture.har")
    assert capability.auth.type == "bearer"
    assert capability.auth.env == "EXAMPLE_API_TOKEN"
    assert [tool.name for tool in capability.tools] == ["get_users_123", "post_users"]

    get_user = capability.tools[0]
    params = {parameter.name: parameter for parameter in get_user.parameters}
    assert get_user.method == "GET"
    assert get_user.path == "/users/123"
    assert get_user.tags == ["har", "example_api"]
    assert get_user.safety == SafetyLevel.READ
    assert params["verbose"].location == "query"
    assert params["verbose"].schema_["default"] == "true"
    assert params["X-Trace-Id"].location == "header"
    assert "User-Agent" not in params
    assert get_user.responses[0].status_code == "200"
    assert get_user.responses[0].schema_["properties"]["name"]["type"] == "string"

    create_user = capability.tools[1]
    assert create_user.safety == SafetyLevel.WRITE
    assert create_user.request_body is not None
    assert create_user.request_body.content_type == "application/json"
    assert create_user.request_body.example == {"name": "Grace", "active": True}
    assert create_user.request_body.schema_["properties"]["active"]["type"] == "boolean"
    assert create_user.responses[0].status_code == "201"


def test_count_har_entries_file() -> None:
    assert count_har_entries_file(FIXTURES / "basic_capture.har") == 2


def test_har_requires_entries() -> None:
    with pytest.raises(ValueError, match="log.entries"):
        parse_har({"log": {"entries": []}})
