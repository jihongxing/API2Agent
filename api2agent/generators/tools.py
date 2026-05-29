from typing import Any

from api2agent.ir.models import Capability, Tool


def to_openai_tools(capability: Capability) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": _tool_parameters(tool),
            },
        }
        for tool in capability.tools
    ]


def _tool_parameters(tool: Tool) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []

    for parameter in tool.parameters:
        properties[parameter.name] = parameter.schema_ or {"type": "string"}
        if parameter.description:
            properties[parameter.name]["description"] = parameter.description
        if parameter.required:
            required.append(parameter.name)

    if tool.request_body is not None:
        properties["body"] = tool.request_body.schema_ or {"type": "object"}
        if tool.request_body.required:
            required.append("body")

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }

