from pathlib import Path

from api2agent.filters import ToolFilter, filter_capability
from api2agent.parsers.openapi import parse_openapi_file


FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


def test_filter_by_tag() -> None:
    capability = parse_openapi_file(FIXTURES / "multi_tools.yaml")

    filtered = filter_capability(capability, ToolFilter(include_tags=["repos"]))

    assert [tool.name for tool in filtered.tools] == ["list_repos", "list_org_repos"]


def test_filter_by_path_substring() -> None:
    capability = parse_openapi_file(FIXTURES / "multi_tools.yaml")

    filtered = filter_capability(capability, ToolFilter(include_paths=["/orgs"]))

    assert [tool.name for tool in filtered.tools] == ["list_org_repos"]


def test_filter_by_path_glob() -> None:
    capability = parse_openapi_file(FIXTURES / "multi_tools.yaml")

    filtered = filter_capability(capability, ToolFilter(include_paths=["/*/*/repos"]))

    assert [tool.name for tool in filtered.tools] == ["list_org_repos"]


def test_filter_by_operation_id_or_tool_name() -> None:
    capability = parse_openapi_file(FIXTURES / "multi_tools.yaml")

    by_operation_id = filter_capability(capability, ToolFilter(include_operations=["listUsers"]))
    by_tool_name = filter_capability(capability, ToolFilter(include_operations=["list_repos"]))

    assert [tool.name for tool in by_operation_id.tools] == ["list_users"]
    assert [tool.name for tool in by_tool_name.tools] == ["list_repos"]


def test_filter_categories_are_intersected_and_max_tools_applies_last() -> None:
    capability = parse_openapi_file(FIXTURES / "multi_tools.yaml")

    filtered = filter_capability(
        capability,
        ToolFilter(include_tags=["repos"], include_paths=["repos"], max_tools=1),
    )

    assert [tool.name for tool in filtered.tools] == ["list_repos"]
