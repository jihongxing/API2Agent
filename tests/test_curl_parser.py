from api2agent.ir.models import SafetyLevel
from api2agent.parsers.curl import parse_curl


def test_parse_curl_bearer_and_path() -> None:
    capability = parse_curl(
        "curl -X POST https://api.example.com/items/123 -H 'Authorization: Bearer token'"
    )

    assert capability.base_url == "https://api.example.com"
    assert capability.auth.type == "bearer"
    assert capability.tools[0].method == "POST"
    assert capability.tools[0].path == "/items/123"
    assert capability.tools[0].safety == SafetyLevel.WRITE


def test_parse_curl_query_headers_and_json_body() -> None:
    capability = parse_curl(
        """curl 'https://api.example.com/items?verbose=true&limit=10' \
        -H 'X-Trace-Id: trace-123' \
        --json '{"name":"demo","active":true,"count":3}'"""
    )
    tool = capability.tools[0]
    params = {parameter.name: parameter for parameter in tool.parameters}

    assert tool.method == "POST"
    assert tool.path == "/items"
    assert params["verbose"].location == "query"
    assert params["verbose"].schema_["default"] == "true"
    assert params["limit"].schema_["default"] == "10"
    assert params["X-Trace-Id"].location == "header"
    assert params["X-Trace-Id"].schema_["default"] == "trace-123"

    assert tool.request_body is not None
    assert tool.request_body.required is True
    assert tool.request_body.schema_["properties"]["name"]["type"] == "string"
    assert tool.request_body.schema_["properties"]["active"]["type"] == "boolean"
    assert tool.request_body.schema_["properties"]["count"]["type"] == "integer"


def test_parse_curl_escaped_json_body() -> None:
    capability = parse_curl("""curl https://api.example.com/items --json '{\\"name\\":\\"demo\\"}'""")

    assert capability.tools[0].request_body is not None
    assert capability.tools[0].request_body.schema_["properties"]["name"]["type"] == "string"


def test_parse_curl_doubly_escaped_json_body() -> None:
    capability = parse_curl("""curl https://api.example.com/items --json '{\\\\"name\\\\":\\\\"demo\\\\"}'""")

    assert capability.tools[0].request_body is not None
    assert capability.tools[0].request_body.schema_["properties"]["name"]["type"] == "string"
