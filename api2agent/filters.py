from dataclasses import dataclass, field
from fnmatch import fnmatch

from api2agent.ir.models import Capability, Tool
from api2agent.utils.naming import snake_name


@dataclass(frozen=True)
class ToolFilter:
    include_tags: list[str] = field(default_factory=list)
    include_paths: list[str] = field(default_factory=list)
    include_operations: list[str] = field(default_factory=list)
    max_tools: int | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.include_tags or self.include_paths or self.include_operations or self.max_tools)


def filter_capability(capability: Capability, filters: ToolFilter) -> Capability:
    if filters.is_empty:
        return capability

    tools = [
        tool for tool in capability.tools
        if _matches_tags(tool, filters.include_tags)
        and _matches_paths(tool, filters.include_paths)
        and _matches_operations(tool, filters.include_operations)
    ]

    if filters.max_tools is not None:
        tools = tools[:filters.max_tools]

    return capability.model_copy(update={"tools": tools})


def _matches_tags(tool: Tool, include_tags: list[str]) -> bool:
    if not include_tags:
        return True

    tool_tags = {tag.lower() for tag in tool.tags}
    return any(tag.lower() in tool_tags for tag in include_tags)


def _matches_paths(tool: Tool, include_paths: list[str]) -> bool:
    if not include_paths:
        return True

    return any(_path_matches(tool.path, pattern) for pattern in include_paths)


def _path_matches(path: str, pattern: str) -> bool:
    if pattern == path:
        return True
    if any(marker in pattern for marker in "*?[]"):
        return fnmatch(path, pattern)
    return pattern in path


def _matches_operations(tool: Tool, include_operations: list[str]) -> bool:
    if not include_operations:
        return True

    operation_names = {tool.name}
    if tool.operation_id:
        operation_names.add(tool.operation_id)
        operation_names.add(snake_name(tool.operation_id))

    return any(operation in operation_names or snake_name(operation) in operation_names for operation in include_operations)
