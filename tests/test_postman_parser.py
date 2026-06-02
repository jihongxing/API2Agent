from pathlib import Path

from api2agent.ir.models import SafetyLevel
from api2agent.parsers.postman import count_postman_requests_file, parse_postman_file


FIXTURES = Path(__file__).parent / "fixtures" / "postman"


def test_parse_postman_collection_to_capability() -> None:
    capability = parse_postman_file(FIXTURES / "basic_collection.json")

    assert capability.name == "postman_demo_api"
    assert capability.version == "1.2.3"
    assert capability.base_url == "https://api.example.com"
    assert capability.source.endswith("basic_collection.json")
    assert capability.auth.type == "bearer"
    assert capability.auth.env == "POSTMAN_DEMO_API_TOKEN"
    assert [tool.name for tool in capability.tools] == ["get_user", "create_user"]

    get_user = capability.tools[0]
    params = {parameter.name: parameter for parameter in get_user.parameters}
    assert get_user.method == "GET"
    assert get_user.path == "/users/{user_id}"
    assert get_user.base_url == "https://api.example.com"
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


def test_count_postman_requests_file() -> None:
    assert count_postman_requests_file(FIXTURES / "basic_collection.json") == 2
