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
    assert capability.servers[0].url == "https://api.example.com/{version}"
    assert capability.servers[0].resolved_url == "https://api.example.com/v1"
    assert capability.servers[0].variables["version"].default == "v1"
    assert tools["get_public"].base_url is None
    assert tools["get_public"].server_source == "document"
    assert tools["get_admin"].base_url == "https://admin.example.com/v2"
    assert tools["get_admin"].server_source == "path"
    assert tools["get_regional"].base_url == "https://us.example.com"
    assert tools["get_regional"].server_source == "operation"


def test_preserves_openapi_server_choices_and_profile_hints() -> None:
    capability = parse_openapi_file(FIXTURES / "server_choices.yaml")
    tools = {tool.name: tool for tool in capability.tools}

    assert capability.base_url == "https://api.example.com/v1"
    assert len(capability.servers) == 3
    assert capability.servers[1].profile_hints == ["staging"]
    assert capability.servers[2].is_relative is True
    assert "relative" in capability.servers[2].profile_hints

    public = tools["get_public"]
    assert public.base_url is None
    assert public.servers[0].source == "document"

    admin = tools["get_admin"]
    assert admin.base_url == "https://admin.example.com"
    assert admin.servers[0].profile_hints == ["admin"]

    regional = tools["get_regional"]
    assert regional.base_url == "https://us.example.com"
    assert regional.servers[0].variables["region"].enum == ["us", "eu"]
    assert "regional" in regional.servers[0].profile_hints


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


def test_preserves_schema_shaping_source_metadata() -> None:
    capability = parse_openapi_file(FIXTURES / "schema_shaping.yaml")
    tool = capability.tools[0]

    assert tool.request_body is not None
    schema = tool.request_body.schema_
    assert schema["properties"]["id"]["readOnly"] is True
    assert schema["properties"]["password"]["writeOnly"] is True
    assert schema["properties"]["nickname"]["nullable"] is True
    assert schema["properties"]["labels"]["additionalProperties"]["type"] == "string"
    assert schema["properties"]["loose"]["type"] == "array"
    assert schema["required"] == ["id", "name", "password"]

    mode_schema = tool.parameters[0].schema_
    assert mode_schema["type"] == ["string", "null"]

    response_schema = tool.responses[0].schema_
    assert response_schema["properties"]["password"]["writeOnly"] is True
    assert response_schema["properties"]["status"]["type"] == ["string", "null"]


def test_preserves_openapi_discriminator_metadata() -> None:
    capability = parse_openapi_file(FIXTURES / "discriminator.yaml")
    tools = {tool.name: tool for tool in capability.tools}

    create_payment = tools["create_payment"]
    assert create_payment.request_body is not None
    schema = create_payment.request_body.schema_

    assert schema["discriminator"]["propertyName"] == "method"
    assert schema["discriminator"]["mapping"]["card"] == "#/components/schemas/CardPayment"
    assert schema["oneOf"][0]["title"] == "CardPayment"
    assert schema["oneOf"][1]["properties"]["method"]["enum"] == ["bank_transfer"]

    broken = tools["create_broken_payment"]
    assert broken.request_body is not None
    assert "propertyName" not in broken.request_body.schema_["discriminator"]


def test_preserves_openapi_response_shape_metadata() -> None:
    capability = parse_openapi_file(FIXTURES / "response_shapes.yaml")
    tools = {tool.name: tool for tool in capability.tools}

    get_item = tools["get_item_response_shape"]
    ok_response = get_item.responses[0]
    assert ok_response.status_code == "200"
    assert ok_response.content_type == "application/json"
    assert ok_response.content_types == ["application/json"]
    assert ok_response.example == {"id": "item_123", "name": "Demo"}
    assert ok_response.schema_["properties"]["password"]["writeOnly"] is True

    bad_request = get_item.responses[2]
    assert bad_request.status_code == "400"
    assert bad_request.examples == [{"error": "invalid_request", "code": "invalid"}]

    start_job = tools["start_job_response_shape"]
    accepted = start_job.responses[0]
    assert accepted.status_code == "202"
    assert accepted.content_type == "application/json"
    assert accepted.schema_ == {}

    missing = start_job.responses[1]
    assert missing.content_type == "application/json"
    assert missing.content_types == ["application/json", "text/plain"]

    legacy = type(ok_response).model_validate({"status_code": "200", "schema": {"type": "object"}})
    assert legacy.content_type is None
    assert legacy.examples == []


def test_preserves_json_schema_keyword_metadata() -> None:
    capability = parse_openapi_file(FIXTURES / "schema_keywords.yaml")
    tools = {tool.name: tool for tool in capability.tools}

    get_user = tools["get_keyword_user"]
    assert get_user.parameters[0].schema_["format"] == "uuid"
    assert get_user.parameters[1].schema_["maxLength"] == 254

    response_schema = get_user.responses[0].schema_
    assert response_schema["properties"]["status"]["const"] == "active"
    assert response_schema["properties"]["code"]["pattern"] == r"^[A-Z]{3}-\d{4}$"
    assert response_schema["properties"]["tags"]["uniqueItems"] is True
    assert response_schema["properties"]["metadata"]["patternProperties"]["^x-"]["type"] == "string"

    create_profile = tools["create_keyword_profile"]
    assert create_profile.request_body is not None
    body_schema = create_profile.request_body.schema_
    assert body_schema["dependentRequired"]["email"] == ["status"]
    assert body_schema["if"]["properties"]["status"]["const"] == "active"
    assert body_schema["properties"]["rating"]["exclusiveMaximum"] == 5
    assert body_schema["properties"]["step"]["multipleOf"] == 5


def test_preserves_openapi_security_requirement_combinations() -> None:
    capability = parse_openapi_file(FIXTURES / "security_combinations.yaml")
    tools = {tool.name: tool for tool in capability.tools}

    assert capability.auth.type == "bearer"
    assert capability.auth.location == "authorization"
    assert capability.security_requirements is not None
    assert len(capability.security_requirements.alternatives) == 2

    public = tools["get_public"]
    assert public.auth is not None
    assert public.auth.type == "none"
    assert public.security_requirements is not None
    assert public.security_requirements.alternatives == []

    query = tools["get_query_auth"]
    assert query.auth is not None
    assert query.auth.type == "api_key"
    assert query.auth.location == "query"
    assert query.auth.name == "api_key"

    cookie = tools["get_cookie_auth"]
    assert cookie.auth is not None
    assert cookie.auth.type == "api_key"
    assert cookie.auth.location == "cookie"
    assert cookie.auth.name == "session"

    combined = tools["get_combined_auth"]
    assert combined.auth is not None
    assert combined.auth.type == "api_key"
    assert len(combined.auth.credentials) == 2
    assert {credential["location"] for credential in combined.auth.credentials} == {"header", "query"}

    oauth = tools["get_oauth_metadata"]
    assert oauth.auth is not None
    assert oauth.auth.type == "unknown"
    assert oauth.auth.unsupported_reason == "no supported executable security requirement alternative"
    assert oauth.security_requirements is not None
    assert oauth.security_requirements.alternatives[0].schemes[0].scopes == ["read"]
