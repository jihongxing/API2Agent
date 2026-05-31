import json
from pathlib import Path

from typer.testing import CliRunner

from api2agent.cli import app
from api2agent.diagnostics import DIAGNOSTICS_CONTRACT_VERSION, diagnose_capability
from api2agent.generators.package import generate_package
from api2agent.ir.models import AuthConfig, Capability, Parameter, RequestBody, SafetyLevel, Tool
from api2agent.parsers.curl import parse_curl
from api2agent.parsers.openapi import parse_openapi_file


runner = CliRunner()


def test_diagnose_capability_flags_generic_names_and_large_toolset() -> None:
    tools = [
        Tool(name="get", method="GET", path=f"/items/{index}", description="GET /items", safety=SafetyLevel.READ)
        for index in range(51)
    ]
    capability = Capability(name="api", base_url="https://api.example.com", tools=tools)

    diagnostics = diagnose_capability(capability)
    finding_ids = {finding["id"] for finding in diagnostics["findings"]}

    assert diagnostics["contract_version"] == DIAGNOSTICS_CONTRACT_VERSION
    assert diagnostics["status"] == "fail"
    assert "generic_capability_name" in finding_ids
    assert "generic_tool_name" in finding_ids
    assert "large_toolset" in finding_ids


def test_diagnose_capability_flags_write_only_unknown_safety_and_auth_without_env() -> None:
    capability = Capability(
        name="orders",
        base_url="https://api.example.com",
        auth=AuthConfig(type="bearer"),
        tools=[
            Tool(name="create_order", method="POST", path="/orders", description="Create order", safety=SafetyLevel.WRITE),
            Tool(name="mystery", method="POST", path="/mystery", description="Mystery", safety=SafetyLevel.UNKNOWN),
        ],
    )

    diagnostics = diagnose_capability(capability)
    finding_ids = {finding["id"] for finding in diagnostics["findings"]}

    assert diagnostics["status"] == "warn"
    assert "write_only_package" in finding_ids
    assert "write_tools_present" in finding_ids
    assert "unknown_safety" in finding_ids
    assert "auth_env_missing" in finding_ids


def test_diagnose_capability_flags_required_body_without_schema() -> None:
    capability = Capability(
        name="items",
        base_url="https://api.example.com",
        tools=[
            Tool(
                name="create_item",
                method="POST",
                path="/items",
                description="Create item",
                safety=SafetyLevel.WRITE,
                request_body=RequestBody(required=True, schema={}),
            )
        ],
    )

    diagnostics = diagnose_capability(capability)
    finding_ids = {finding["id"] for finding in diagnostics["findings"]}

    assert diagnostics["status"] == "fail"
    assert diagnostics["summary"]["errors"] == 1
    assert "required_body_without_schema" in finding_ids


def test_diagnose_capability_flags_required_parameters_without_descriptions() -> None:
    capability = Capability(
        name="items",
        base_url="https://api.example.com",
        tools=[
            Tool(
                name="get_item",
                method="GET",
                path="/items/{item_id}",
                description="Get item",
                safety=SafetyLevel.READ,
                parameters=[
                    Parameter(name="item_id", location="path", required=True, schema={"type": "string"}),
                ],
            )
        ],
    )

    diagnostics = diagnose_capability(capability)
    finding_ids = {finding["id"] for finding in diagnostics["findings"]}

    assert "missing_parameter_descriptions" in finding_ids


def test_generate_package_writes_diagnostics_json(tmp_path) -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/basic.yaml"))
    package_dir = generate_package(capability, tmp_path / "package")

    diagnostics = json.loads((package_dir / "diagnostics.json").read_text(encoding="utf-8"))
    readme = (package_dir / "README.md").read_text(encoding="utf-8")

    assert diagnostics["contract_version"] == DIAGNOSTICS_CONTRACT_VERSION
    assert diagnostics["metrics"]["tool_count"] == 1
    assert "## Diagnostics" in readme


def test_diagnose_command_prints_json(tmp_path) -> None:
    capability = parse_curl("curl https://api.example.com/items")
    package_dir = generate_package(capability, tmp_path / "package")

    result = runner.invoke(app, ["diagnose", str(package_dir), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["contract_version"] == DIAGNOSTICS_CONTRACT_VERSION
    assert payload["metrics"]["tool_count"] == 1


def test_diagnose_command_works_without_diagnostics_artifact(tmp_path) -> None:
    capability = parse_curl("curl https://api.example.com/items")
    package_dir = generate_package(capability, tmp_path / "package")
    (package_dir / "diagnostics.json").unlink()

    result = runner.invoke(app, ["diagnose", str(package_dir)])

    assert result.exit_code == 0
    assert "Diagnostics:" in result.output


def test_inspect_prints_diagnostics_summary(tmp_path) -> None:
    capability = parse_curl("curl https://api.example.com/items")
    package_dir = generate_package(capability, tmp_path / "package")

    result = runner.invoke(app, ["inspect", str(package_dir)])

    assert result.exit_code == 0
    assert "Diagnostics:" in result.output


def test_diagnose_reports_openapi_security_combinations() -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/security_combinations.yaml"))
    diagnostics = diagnose_capability(capability)
    finding_ids = {finding["id"] for finding in diagnostics["findings"]}

    assert "auth_alternatives_present" in finding_ids
    assert "combined_auth_required" in finding_ids
    assert "query_api_key_auth" in finding_ids
    assert "cookie_api_key_auth" in finding_ids
    assert "metadata_only_oauth" in finding_ids


def test_diagnose_reports_openapi_server_metadata() -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/server_choices.yaml"))
    diagnostics = diagnose_capability(capability)
    finding_ids = {finding["id"] for finding in diagnostics["findings"]}

    assert "multiple_servers_present" in finding_ids
    assert "relative_server_url" in finding_ids
    assert "server_variables_present" in finding_ids
    assert "path_server_override" in finding_ids
    assert "operation_server_override" in finding_ids


def test_diagnose_reports_schema_shaping_hints() -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/schema_shaping.yaml"))
    diagnostics = diagnose_capability(capability)
    finding_ids = {finding["id"] for finding in diagnostics["findings"]}

    assert "nullable_fields_present" in finding_ids
    assert "read_only_request_fields" in finding_ids
    assert "write_only_response_fields" in finding_ids
    assert "additional_properties_present" in finding_ids
    assert "nested_polymorphic_schema" in finding_ids
    assert "array_without_item_schema" in finding_ids


def test_diagnose_reports_discriminator_hints() -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/discriminator.yaml"))
    diagnostics = diagnose_capability(capability)
    finding_ids = {finding["id"] for finding in diagnostics["findings"]}

    assert "discriminator_present" in finding_ids
    assert "discriminator_mapping_present" in finding_ids
    assert "discriminator_missing_property" in finding_ids
    assert "discriminator_without_polymorphism" in finding_ids
    assert "discriminator_mapping_unresolved" in finding_ids
    assert "discriminator_branch_without_tag" in finding_ids


def test_diagnose_reports_response_shape_documentation_hints() -> None:
    capability = parse_openapi_file(Path("tests/fixtures/openapi/response_shapes.yaml"))
    diagnostics = diagnose_capability(capability)
    finding_ids = {finding["id"] for finding in diagnostics["findings"]}

    assert "response_schema_present" in finding_ids
    assert "response_example_present" in finding_ids
    assert "response_without_schema" in finding_ids
    assert "success_response_without_schema" in finding_ids
    assert "error_response_schema_present" in finding_ids
    assert "default_response_present" in finding_ids
    assert "multiple_response_content_types" in finding_ids
    assert "response_polymorphic_schema" in finding_ids
