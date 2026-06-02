from pathlib import Path

import pytest

from api2agent.ir.models import SafetyLevel
from api2agent.parsers.bruno import count_bruno_requests_file, parse_bruno_collection, parse_bruno_file


FIXTURES = Path(__file__).parent / "fixtures" / "bruno"


def test_parse_bruno_collection_to_capability() -> None:
    capability = parse_bruno_file(FIXTURES / "basic_collection.json")

    assert capability.name == "bruno_demo_api"
    assert capability.version == "1.0.0"
    assert capability.base_url == "https://api.example.com"
    assert capability.source.endswith("basic_collection.json")
    assert capability.auth.type == "api_key"
    assert capability.auth.env == "BRUNO_DEMO_API_API_KEY"
    assert capability.auth.header == "X-API-Key"
    assert [tool.name for tool in capability.tools] == ["get_user", "create_user"]

    get_user = capability.tools[0]
    params = {parameter.name: parameter for parameter in get_user.parameters}
    assert get_user.method == "GET"
    assert get_user.path == "/users/123"
    assert get_user.tags == ["Users"]
    assert get_user.safety == SafetyLevel.READ
    assert params["verbose"].location == "query"
    assert params["verbose"].schema_["default"] == "true"
    assert params["X-Trace-Id"].location == "header"

    create_user = capability.tools[1]
    assert create_user.safety == SafetyLevel.WRITE
    assert create_user.request_body is not None
    assert create_user.request_body.content_type == "application/json"
    assert create_user.request_body.schema_["properties"]["active"]["type"] == "boolean"


def test_count_bruno_requests_file() -> None:
    assert count_bruno_requests_file(FIXTURES / "basic_collection.json") == 2


def test_bruno_collection_requires_items() -> None:
    with pytest.raises(ValueError, match="items or requests"):
        parse_bruno_collection({"name": "bad"})
