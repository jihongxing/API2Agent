import asyncio
import importlib
import json
import sys
from pathlib import Path

from api2agent.generators.package import generate_package
from api2agent.parsers.openapi import parse_openapi_file


FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


def test_generated_mcp_server_lists_and_calls_tools(tmp_path, monkeypatch) -> None:
    capability = parse_openapi_file(FIXTURES / "basic.yaml")
    output_dir = generate_package(capability, tmp_path / "api2agent-output")

    sys.path.insert(0, str(output_dir))
    try:
        mcp_server = importlib.import_module("mcp_server")
        monkeypatch.setattr(
            mcp_server,
            "execute_tool",
            lambda name, arguments: {"ok": True, "name": name, "arguments": arguments},
        )

        tools = asyncio.run(mcp_server.handle_list_tools())
        assert tools[0].name == "get_user"
        assert tools[0].inputSchema["properties"]["user_id"]["type"] == "string"

        result = asyncio.run(mcp_server.handle_call_tool("get_user", {"user_id": "u_123"}))
        payload = json.loads(result[0].text)

        assert payload["ok"] is True
        assert payload["name"] == "get_user"
        assert payload["arguments"] == {"user_id": "u_123"}
    finally:
        sys.path.remove(str(output_dir))
        sys.modules.pop("mcp_server", None)
        sys.modules.pop("runner", None)

