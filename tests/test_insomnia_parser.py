from pathlib import Path

import pytest

from api2agent.ir.models import SafetyLevel
from api2agent.parsers.insomnia import count_insomnia_requests_file, parse_insomnia_export, parse_insomnia_file


FIXTURES = Path(__file__).parent / "fixtures" / "insomnia"


def test_parse_insomnia_export_to_capability() -> None:
    capability = parse_insomnia_file(FIXTURES / "basic_export.json")

    assert capability.name == "insomnia_demo_api"
    assert capability.base_url == "https://api.example.com"
    assert capability.source.endswith("basic_export.json")
    assert capability.auth.type == "bearer"
    assert capability.auth.env == "INSOMNIA_DEMO_API_TOKEN"
    assert [tool.name for tool in capability.tools] == ["get_user", "create_user"]

    get_user = capability.tools[0]
    params = {parameter.name: parameter for parameter in get_user.parameters}
    assert get_user.method == "GET"
    assert get_user.path == "/users/{user_id}"
    assert get_user.tags == ["Users"]
    assert get_user.safety == SafetyLevel.READ
    assert params["user_id"].location == "path"
    assert params["user_id"].required is True
    assert params["verbose"].location == "query"
    assert params["verbose"].schema_["default"] == "true"
    assert params["X-Trace-Id"].location == "header"

    create_user = capability.tools[1]
    assert create_user.safety == SafetyLevel.WRITE
    assert create_user.request_body is not None
    assert create_user.request_body.content_type == "application/json"
    assert create_user.request_body.schema_["properties"]["active"]["type"] == "boolean"


def test_count_insomnia_requests_file() -> None:
    assert count_insomnia_requests_file(FIXTURES / "basic_export.json") == 2


def test_insomnia_export_requires_resources() -> None:
    with pytest.raises(ValueError, match="resources"):
        parse_insomnia_export({})
