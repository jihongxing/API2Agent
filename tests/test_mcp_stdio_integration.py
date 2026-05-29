import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from api2agent.generators.package import generate_package
from api2agent.parsers.openapi import parse_openapi_file


FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


def test_generated_mcp_server_over_stdio(tmp_path: Path) -> None:
    capability = parse_openapi_file(FIXTURES / "basic.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")
    _replace_runner_with_fake(output_dir)

    result = asyncio.run(_call_generated_server(output_dir))

    assert result["tool_name"] == "get_user"
    assert result["call_payload"]["ok"] is True
    assert result["call_payload"]["arguments"] == {"user_id": "u_123"}


async def _call_generated_server(output_dir: Path) -> dict:
    server = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        cwd=output_dir,
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_name = tools.tools[0].name
            result = await session.call_tool(tool_name, {"user_id": "u_123"})
            payload = json.loads(result.content[0].text)

    return {"tool_name": tool_name, "call_payload": payload}


def _replace_runner_with_fake(output_dir: Path) -> None:
    (output_dir / "runner.py").write_text(
        """def execute_tool(name, params):\n    return {\"ok\": True, \"name\": name, \"arguments\": params}\n""",
        encoding="utf-8",
    )

