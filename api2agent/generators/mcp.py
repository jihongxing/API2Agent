from api2agent.generators.tools import to_openai_tools
from api2agent.ir.models import Capability


def render_mcp_server(capability: Capability) -> str:
    mcp_tools = [
        {
            "name": tool["function"]["name"],
            "description": tool["function"]["description"],
            "inputSchema": tool["function"]["parameters"],
        }
        for tool in to_openai_tools(capability)
    ]
    tools_data = repr(mcp_tools)
    server_name = capability.name
    server_version = capability.version

    return f'''"""Generated MCP stdio server for {server_name}."""

import asyncio
import json

import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from runner import execute_tool

TOOLS = {tools_data}

server = Server("{server_name}", version="{server_version}")


@server.list_tools()
async def handle_list_tools(request=None):
    return [
        types.Tool(
            name=tool["name"],
            description=tool.get("description") or tool["name"],
            inputSchema=tool["inputSchema"],
        )
        for tool in TOOLS
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    result = execute_tool(name, arguments or {{}})
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False),
        )
    ]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="{server_name}",
                server_version="{server_version}",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={{}},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
'''

