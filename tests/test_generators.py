import json
from pathlib import Path

from api2agent.generators.package import generate_package
from api2agent.parsers.curl import parse_curl
from api2agent.parsers.openapi import parse_openapi_file


FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


def test_generate_package(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "basic.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    expected_files = [
        "README.md",
        "capability.json",
        "diagnostics.json",
        "tools.json",
        "runner.py",
        "smoke_test.py",
        "manual_write_test.py",
        "mcp_server.py",
        "auth.env.example",
    ]

    for filename in expected_files:
        assert (output_dir / filename).exists()

    capability_json = json.loads((output_dir / "capability.json").read_text())
    tools_json = json.loads((output_dir / "tools.json").read_text())

    assert capability_json["name"] == "basic_api"
    assert tools_json[0]["function"]["name"] == "get_user"


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

    assert "query: verbose string default=true" in readme
    assert "header: X-Trace-Id string default=trace-123" in readme
    assert "body: object {name:string?, active:boolean?} required" in readme
    assert "'body': {'name': 'example', 'active': True}" in readme
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
    assert "'body': {'name': 'example', 'password': 'example'}" in manual_write_test

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
    assert "'body': {'method': 'card', 'card_number': 'example', 'token': 'example'}" in manual_write_test

    body_schema = tools_json[0]["function"]["parameters"]["properties"]["body"]
    assert body_schema["discriminator"]["propertyName"] == "method"
    assert "id" not in body_schema["oneOf"][0]["properties"]
    assert body_schema["oneOf"][0]["properties"]["token"]["writeOnly"] is True


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
