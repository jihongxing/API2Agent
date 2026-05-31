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


def test_preserves_openapi_examples_and_defaults() -> None:
    capability = parse_openapi_file(FIXTURES / "examples_defaults.yaml")
    tools = {tool.name: tool for tool in capability.tools}

    get_user = tools["get_user_by_example"]
    assert get_user.parameters[0].name == "user_id"
    assert get_user.parameters[0].example == "user_123"
    assert get_user.parameters[1].name == "include"
    assert get_user.parameters[1].examples == ["profile"]
    assert get_user.parameters[2].name == "X-Trace-Id"
    assert get_user.parameters[2].schema_["default"] == "trace-123"

    create_order = tools["create_order_with_example"]
    assert create_order.request_body is not None
    assert create_order.request_body.example == {"sku": "sku_123", "quantity": 2}
    assert create_order.request_body.schema_["properties"]["sku"]["example"] == "fallback_sku"

    update_order = tools["update_order_with_property_examples"]
    assert update_order.parameters[0].schema_["enum"][0] == "order_123"
    assert update_order.request_body is not None
    assert update_order.request_body.schema_["properties"]["status"]["enum"][0] == "shipped"
