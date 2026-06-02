import json
import importlib.util
from pathlib import Path

import pytest

from api2agent.generators.package import generate_package
from api2agent.parsers.asyncapi import parse_asyncapi_file
from api2agent.parsers.bruno import parse_bruno_file
from api2agent.parsers.curl import parse_curl
from api2agent.parsers.graphql import parse_graphql_file
from api2agent.parsers.har import parse_har_file
from api2agent.parsers.insomnia import parse_insomnia_file
from api2agent.parsers.openapi import parse_openapi_file
from api2agent.parsers.postman import parse_postman_file
from api2agent.parsers.protobuf import parse_proto_file
from api2agent.parsers.workflow import parse_workflow_file


FIXTURES = Path(__file__).parent / "fixtures" / "openapi"
EXPECTED_PACKAGE_FILES = [
    "README.md",
    "capability.json",
    "diagnostics.json",
    "tools.json",
    "runner.py",
    "smoke_test.py",
    "manual_write_test.py",
    "mcp_server.py",
    "auth.env.example",
    "examples/openai_agent.py",
    "examples/claude_desktop_config.json",
]

SOURCE_PACKAGE_CASES = [
    ("openapi", lambda: parse_openapi_file(Path("tests/fixtures/openapi/basic.yaml"))),
    ("curl", lambda: parse_curl("curl https://api.example.com/items?verbose=true")),
    ("har", lambda: parse_har_file(Path("tests/fixtures/har/basic_capture.har"))),
    ("postman", lambda: parse_postman_file(Path("tests/fixtures/postman/basic_collection.json"))),
    ("insomnia", lambda: parse_insomnia_file(Path("tests/fixtures/insomnia/basic_export.json"))),
    ("bruno", lambda: parse_bruno_file(Path("tests/fixtures/bruno/basic_collection.json"))),
    ("graphql", lambda: parse_graphql_file(Path("tests/fixtures/graphql/basic_manifest.json"))),
    ("workflow", lambda: parse_workflow_file(Path("tests/fixtures/workflow/basic_manifest.json"))),
    ("protobuf", lambda: parse_proto_file(Path("tests/fixtures/protobuf/user_service.proto"))),
    ("asyncapi", lambda: parse_asyncapi_file(Path("tests/fixtures/asyncapi/basic_webhook.yaml"))),
]


def test_generate_package(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "basic.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    for filename in EXPECTED_PACKAGE_FILES:
        assert (output_dir / filename).exists()

    capability_json = json.loads((output_dir / "capability.json").read_text())
    tools_json = json.loads((output_dir / "tools.json").read_text())
    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    smoke_test = (output_dir / "smoke_test.py").read_text(encoding="utf-8")
    openai_example = (output_dir / "examples" / "openai_agent.py").read_text(encoding="utf-8")
    claude_config = json.loads((output_dir / "examples" / "claude_desktop_config.json").read_text(encoding="utf-8"))

    assert capability_json["name"] == "basic_api"
    assert tools_json[0]["function"]["name"] == "get_user"
    assert "'user_id': 'user_123'" in readme
    assert "'user_id': 'user_123'" in smoke_test
    assert "## MCP Server" in readme
    assert "python mcp_server.py" in readme
    assert "examples/claude_desktop_config.json" in readme
    assert "def dispatch_tool_call" in openai_example
    assert "client.responses.create" in openai_example
    assert claude_config["mcpServers"]["basic_api"]["args"][0].endswith("mcp_server.py")


@pytest.mark.parametrize("source_name,capability_factory", SOURCE_PACKAGE_CASES)
def test_generate_package_consistency_across_sources(tmp_path: Path, source_name, capability_factory) -> None:
    capability = capability_factory()
    output_dir = generate_package(capability, tmp_path / source_name)

    for filename in EXPECTED_PACKAGE_FILES:
        assert (output_dir / filename).exists()

    capability_json = json.loads((output_dir / "capability.json").read_text(encoding="utf-8"))
    tools_json = json.loads((output_dir / "tools.json").read_text(encoding="utf-8"))
    diagnostics_json = json.loads((output_dir / "diagnostics.json").read_text(encoding="utf-8"))
    serialized_tools = json.dumps(tools_json)
    runner = _load_generated_module(output_dir / "runner.py", f"generated_runner_{source_name}")

    assert capability_json["tools"]
    assert len(tools_json) == len(capability_json["tools"])
    assert "x-api2agent-" not in serialized_tools
    for tool in tools_json:
        assert tool["type"] == "function"
        assert tool["function"]["name"]
        assert tool["function"]["parameters"]["type"] == "object"

    assert diagnostics_json["contract_version"] == "api2agent.capability_diagnostics.v0"
    assert diagnostics_json["status"] in {"pass", "warn", "fail"}
    assert isinstance(diagnostics_json["score"], int)
    assert isinstance(diagnostics_json["findings"], list)
    assert hasattr(runner, "execute_tool")


def test_generated_protobuf_runner_fails_clearly_until_transport_is_wired(tmp_path: Path) -> None:
    capability = parse_proto_file(Path("tests/fixtures/protobuf/user_service.proto"))
    output_dir = generate_package(capability, tmp_path / "protobuf")
    runner = _load_generated_module(output_dir / "runner.py", "generated_runner_protobuf")

    result = runner.execute_tool("user_service_get_user", {"body": {"user_id": "user_123"}})

    assert result["ok"] is False
    assert result["error"]["type"] == "grpc_unimplemented"
    assert result["error"]["grpc"]["method"] == "GetUser"


def test_generated_openai_example_dispatches_to_runner(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "basic.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")
    (output_dir / "runner.py").write_text(
        "def execute_tool(name, params):\n"
        "    return {\"ok\": True, \"name\": name, \"arguments\": params}\n",
        encoding="utf-8",
    )

    module = _load_generated_example(output_dir / "examples" / "openai_agent.py")
    result = module.dispatch_tool_call({"name": "get_user", "arguments": "{\"user_id\":\"u_123\"}"})
    tools = module.load_tools()

    assert result == {"ok": True, "name": "get_user", "arguments": {"user_id": "u_123"}}
    assert tools[0]["type"] == "function"
    assert tools[0]["name"] == "get_user"
    assert "function" not in tools[0]
    assert tools[0]["parameters"]["properties"]["user_id"]["type"] == "string"


def _load_generated_example(path: Path):
    return _load_generated_module(path, "generated_openai_agent")


def _load_generated_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load generated module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_package_includes_guarded_manual_write_test(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "unsafe.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    smoke_test = (output_dir / "smoke_test.py").read_text(encoding="utf-8")
    manual_write_test = (output_dir / "manual_write_test.py").read_text(encoding="utf-8")
    readme = (output_dir / "README.md").read_text(encoding="utf-8")

    assert "No read-only endpoint was detected" in smoke_test
    assert "API2AGENT_ALLOW_WRITE_TEST" in manual_write_test
    assert 'execute_tool("create_order", {})' in manual_write_test
    assert "api2agent test . --allow-write" in readme


def test_generated_readme_includes_parameter_and_body_details(tmp_path: Path) -> None:
    capability = parse_curl(
        """curl 'https://api.example.com/items?verbose=true' \
        -H 'X-Trace-Id: trace-123' \
        --json '{"name":"demo","active":true}'"""
    )
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    readme = (output_dir / "README.md").read_text(encoding="utf-8")

    assert "## Package Overview" in readme
    assert "- Tools: 1" in readme
    assert "- Diagnostics: warn score=" in readme
    assert "query: verbose string default=true" in readme
    assert "header: X-Trace-Id string default=trace-123" in readme
    assert "body: object {name:string?, active:boolean?} required" in readme
    assert "'body': {'name': 'Demo', 'active': True}" in readme
    assert "api2agent test . --tool" in readme


def test_generated_readme_and_tests_use_openapi_examples(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "examples_defaults.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    smoke_test = (output_dir / "smoke_test.py").read_text(encoding="utf-8")
    manual_write_test = (output_dir / "manual_write_test.py").read_text(encoding="utf-8")

    assert "user_id string required example=user_123" in readme
    assert "X-Trace-Id string default=trace-123 required example=trace-123" in readme
    assert "'user_id': 'user_123'" in readme
    assert "'X-Trace-Id': 'trace-123'" in readme
    assert "'user_id': 'user_123'" in smoke_test
    assert "'X-Trace-Id': 'trace-123'" in smoke_test
    assert "'body': {'sku': 'sku_123', 'quantity': 2}" in manual_write_test


def test_generated_auth_docs_include_security_combinations(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "security_combinations.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    auth_env = (output_dir / "auth.env.example").read_text(encoding="utf-8")

    assert "Key caveats: success_response_without_schema(5), weak_tool_description(5)" in readme
    assert "auth: combined api_key via header:X-API-Key" in readme
    assert "api_key via query:api_key" in readme
    assert "api_key via cookie:session" in readme
    assert "SECURITY_COMBINATIONS_API_API_KEY=" in auth_env


def test_generated_readme_lists_openapi_server_choices(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "server_choices.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    readme = (output_dir / "README.md").read_text(encoding="utf-8")

    assert "Known OpenAPI servers:" in readme
    assert "`https://api.example.com/v1` (document hints=production)" in readme
    assert "`https://staging.example.com/v1` (document hints=staging)" in readme
    assert "`/api/v3` (document relative hints=relative)" in readme
    assert "`get_admin`: GET /admin [read] [auth: inherit] [server: path]" in readme


def test_schema_shaping_affects_readme_examples_and_openai_tools(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "schema_shaping.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    manual_write_test = (output_dir / "manual_write_test.py").read_text(encoding="utf-8")
    tools_json = json.loads((output_dir / "tools.json").read_text(encoding="utf-8"))

    assert "body: object {name:string, nickname:string nullable?, password:string writeOnly" in readme
    assert "labels:object map[string]?" in readme
    assert "loose:array[unknown]?" in readme
    assert "id:string" not in readme.split("body: ", 1)[1].split("\n", 1)[0]
    assert "'body': {'name': 'Demo', 'password': 'REPLACE_ME'}" in manual_write_test

    body_schema = tools_json[0]["function"]["parameters"]["properties"]["body"]
    assert "id" not in body_schema["properties"]
    assert body_schema["required"] == ["name", "password"]
    assert "password" in body_schema["properties"]


def test_discriminator_shaping_affects_readme_examples_and_openai_tools(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "discriminator.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    manual_write_test = (output_dir / "manual_write_test.py").read_text(encoding="utf-8")
    tools_json = json.loads((output_dir / "tools.json").read_text(encoding="utf-8"))

    assert "oneOf[discriminator=method: card=>CardPayment | bank_transfer=>BankTransfer | cash=>CashPayment]" in readme
    assert "'body': {'method': 'card', 'card_number': 'example', 'token': 'REPLACE_ME'}" in manual_write_test

    body_schema = tools_json[0]["function"]["parameters"]["properties"]["body"]
    assert body_schema["discriminator"]["propertyName"] == "method"
    assert "id" not in body_schema["oneOf"][0]["properties"]
    assert body_schema["oneOf"][0]["properties"]["token"]["writeOnly"] is True


def test_response_shape_documentation_affects_readme(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "response_shapes.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    readme = (output_dir / "README.md").read_text(encoding="utf-8")

    assert "  - responses:" in readme
    assert "200 success application/json object {id:string readOnly, name:string}" in readme
    assert 'example={"id": "item_123", "name": "Demo"} - OK' in readme
    assert "204 success no documented body - No Content" in readme
    assert "400 client_error application/json object {error:string, code:string?}" in readme
    assert "default default application/json object {error:string, code:string?}" in readme
    assert "202 success application/json undocumented schema - Accepted" in readme
    assert "password:string" not in readme


def test_json_schema_keyword_coverage_affects_docs_examples_and_tools(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "schema_keywords.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    manual_write_test = (output_dir / "manual_write_test.py").read_text(encoding="utf-8")
    tools_json = json.loads((output_dir / "tools.json").read_text(encoding="utf-8"))

    assert "user_id string format=uuid required" in readme
    assert "email string format=email maxLength=254" in readme
    assert "status:string const=active" in readme
    assert "age:integer min=0 max=150" in readme
    assert r"code:string pattern=^[A-Z]{3}-\d{4}$" in readme
    assert "tags:array[string] minItems=1 maxItems=5 uniqueItems" in readme
    assert "legacy_code:string deprecated" in readme
    assert "'email': 'user@example.com'" in manual_write_test
    assert "'age': 1" in manual_write_test
    assert "'tags': ['example', 'example']" in manual_write_test
    assert "'status': 'active'" in manual_write_test

    body_schema = tools_json[1]["function"]["parameters"]["properties"]["body"]
    assert body_schema["properties"]["email"]["format"] == "email"
    assert body_schema["properties"]["tags"]["minItems"] == 2
    assert body_schema["properties"]["status"]["const"] == "active"
    assert body_schema["dependentRequired"]["email"] == ["status"]
    assert body_schema["if"]["properties"]["status"]["const"] == "active"


def test_generate_package_refuses_non_empty_output_without_force(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "basic.yaml")
    output_dir = tmp_path / "api2agent-output"
    output_dir.mkdir()
    (output_dir / "custom.txt").write_text("keep me", encoding="utf-8")

    try:
        generate_package(capability, output_dir)
    except FileExistsError as exc:
        assert "Use --force" in str(exc)
    else:
        raise AssertionError("Expected FileExistsError")


def test_generate_package_allows_force_on_non_empty_output(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "basic.yaml")
    output_dir = tmp_path / "api2agent-output"
    output_dir.mkdir()
    (output_dir / "custom.txt").write_text("keep me", encoding="utf-8")

    generate_package(capability, output_dir, force=True)

    assert (output_dir / "capability.json").exists()
    assert (output_dir / "custom.txt").read_text(encoding="utf-8") == "keep me"
