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
        "tools.json",
        "runner.py",
        "smoke_test.py",
        "mcp_server.py",
        "auth.env.example",
    ]

    for filename in expected_files:
        assert (output_dir / filename).exists()

    capability_json = json.loads((output_dir / "capability.json").read_text())
    tools_json = json.loads((output_dir / "tools.json").read_text())

    assert capability_json["name"] == "basic_api"
    assert tools_json[0]["function"]["name"] == "get_user"


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
    assert "body: object {name:string, active:boolean} required" in readme
    assert "'body': {'name': 'example', 'active': True}" in readme


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
