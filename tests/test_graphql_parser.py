from pathlib import Path

import pytest

from api2agent.ir.models import SafetyLevel
from api2agent.parsers.graphql import parse_graphql_file, parse_graphql_manifest


FIXTURES = Path(__file__).parent / "fixtures" / "graphql"


def test_parse_graphql_manifest_to_operation_tools() -> None:
    capability = parse_graphql_file(FIXTURES / "basic_manifest.json")

    assert capability.name == "git_hub_graph_ql_demo"
    assert capability.version == "1.0.0"
    assert capability.base_url == "https://api.github.com"
    assert capability.source.endswith("basic_manifest.json")
    assert capability.auth.type == "bearer"
    assert capability.auth.env == "GITHUB_GRAPHQL_TOKEN"
    assert capability.auth.header == "Authorization"
    assert len(capability.tools) == 2

    query_tool = capability.tools[0]
    assert query_tool.name == "get_viewer"
    assert query_tool.method == "POST"
    assert query_tool.path == "/graphql"
    assert query_tool.tags == ["graphql", "query"]
    assert query_tool.safety == SafetyLevel.READ
    assert query_tool.request_body is not None
    assert query_tool.request_body.schema_["required"] == ["login"]
    assert query_tool.request_body.schema_["properties"]["login"]["type"] == "string"
    assert query_tool.request_body.schema_["x-api2agent-graphql"] == {
        "query": "query GetViewer($login: String!) { user(login: $login) { login name } }",
        "operationName": "GetViewer",
    }
    assert query_tool.request_body.example == {"login": "octocat"}
    assert query_tool.responses[0].schema_["properties"]["data"]["type"] == "object"

    mutation_tool = capability.tools[1]
    assert mutation_tool.name == "add_star"
    assert mutation_tool.tags == ["graphql", "mutation"]
    assert mutation_tool.safety == SafetyLevel.WRITE
    assert mutation_tool.request_body is not None
    assert mutation_tool.request_body.schema_["required"] == ["starrableId"]


def test_graphql_manifest_requires_http_endpoint() -> None:
    with pytest.raises(ValueError, match="endpoint.url"):
        parse_graphql_manifest({"name": "bad", "endpoint": {"url": "ftp://example.com/graphql"}, "operations": []})


def test_graphql_manifest_requires_operations() -> None:
    with pytest.raises(ValueError, match="at least one operation"):
        parse_graphql_manifest({"name": "bad", "endpoint": {"url": "https://api.example.com/graphql"}})


def test_graphql_manifest_requires_operation_objects() -> None:
    with pytest.raises(ValueError, match="operations must be objects"):
        parse_graphql_manifest({"endpoint": {"url": "https://api.example.com/graphql"}, "operations": [None]})


def test_graphql_manifest_requires_operation_query() -> None:
    with pytest.raises(ValueError, match="query must be a non-empty string"):
        parse_graphql_manifest({"endpoint": {"url": "https://api.example.com/graphql"}, "operations": [{"name": "bad"}]})
