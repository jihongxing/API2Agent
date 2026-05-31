from pathlib import Path

from api2agent.filters import ToolFilter
from api2agent.ir.models import SafetyLevel
from api2agent.parsers.openapi import count_openapi_operations_file, parse_openapi_file


FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


def test_parse_basic_openapi() -> None:
    capability = parse_openapi_file(FIXTURES / "basic.yaml")

    assert capability.name == "basic_api"
    assert capability.base_url == "https://api.example.com"
    assert len(capability.tools) == 1
    assert capability.tools[0].name == "get_user"
    assert capability.tools[0].operation_id == "getUser"
    assert capability.tools[0].safety == SafetyLevel.READ
    assert capability.tools[0].parameters[0].name == "user_id"


def test_parse_openapi_tags() -> None:
    capability = parse_openapi_file(FIXTURES / "multi_tools.yaml")
    tags_by_name = {tool.name: tool.tags for tool in capability.tools}

    assert tags_by_name["list_users"] == ["users"]
    assert tags_by_name["list_repos"] == ["repos"]


def test_parse_openapi_applies_filters_during_parse() -> None:
    capability = parse_openapi_file(
        FIXTURES / "multi_tools.yaml",
        filters=ToolFilter(include_tags=["repos"], max_tools=1),
    )

    assert [tool.name for tool in capability.tools] == ["list_repos"]


def test_count_openapi_operations_file() -> None:
    assert count_openapi_operations_file(FIXTURES / "multi_tools.yaml") == 4


def test_parse_bearer_auth() -> None:
    capability = parse_openapi_file(FIXTURES / "bearer_auth.yaml")

    assert capability.auth.type == "bearer"
    assert capability.auth.env == "BEARER_API_TOKEN"
    assert capability.auth.header == "Authorization"


def test_parse_endpoint_level_auth_overrides() -> None:
    capability = parse_openapi_file(FIXTURES / "mixed_auth.yaml")
    tools = {tool.name: tool for tool in capability.tools}

    assert capability.auth.type == "bearer"
    assert capability.auth.env == "MIXED_AUTH_API_TOKEN"

    assert tools["get_public"].auth is not None
    assert tools["get_public"].auth.type == "none"
    assert tools["get_secure"].auth is None
    assert tools["get_admin"].auth is not None
    assert tools["get_admin"].auth.type == "api_key"
    assert tools["get_admin"].auth.env == "MIXED_AUTH_API_API_KEY"
    assert tools["get_admin"].auth.header == "X-Admin-Key"


def test_classifies_unsafe_methods() -> None:
    capability = parse_openapi_file(FIXTURES / "unsafe.yaml")
    safety_by_name = {tool.name: tool.safety for tool in capability.tools}

    assert safety_by_name["create_order"] == SafetyLevel.WRITE
    assert safety_by_name["delete_order"] == SafetyLevel.DELETE


def test_resolves_local_refs() -> None:
    capability = parse_openapi_file(FIXTURES / "refs.yaml")
    tools = {tool.name: tool for tool in capability.tools}

    get_user = tools["get_user_by_ref"]
    assert get_user.parameters[0].name == "user_id"
    assert get_user.parameters[0].schema_["type"] == "string"
    assert get_user.responses[0].schema_["properties"]["email"]["type"] == "string"

    create_user = tools["create_user_by_ref"]
    assert create_user.request_body is not None
    assert create_user.request_body.required is True
    assert create_user.request_body.schema_["properties"]["email"]["type"] == "string"


def test_resolves_server_variables_and_overrides() -> None:
    capability = parse_openapi_file(FIXTURES / "servers.yaml")
    tools = {tool.name: tool for tool in capability.tools}

    assert capability.base_url == "https://api.example.com/v1"
    assert tools["get_public"].base_url is None
    assert tools["get_admin"].base_url == "https://admin.example.com/v2"
    assert tools["get_regional"].base_url == "https://us.example.com"


def test_normalizes_schema_composition() -> None:
    capability = parse_openapi_file(FIXTURES / "composition.yaml")
    tool = capability.tools[0]

    assert tool.request_body is not None
    assert tool.request_body.schema_["type"] == "object"
    assert tool.request_body.schema_["properties"]["email"]["type"] == "string"
    assert tool.request_body.schema_["properties"]["name"]["type"] == "string"
    assert tool.request_body.schema_["required"] == ["email"]

    response_schema = tool.responses[0].schema_
    assert response_schema["properties"]["id"]["type"] == "string"
    assert response_schema["properties"]["email"]["type"] == "string"
    assert response_schema["required"] == ["id", "email"]

    lookup_schema = tool.parameters[0].schema_
    assert lookup_schema["oneOf"][0]["type"] == "string"
    assert lookup_schema["oneOf"][1]["type"] == "integer"
