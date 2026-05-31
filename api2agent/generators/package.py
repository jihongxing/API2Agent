import json
from pathlib import Path

from api2agent.diagnostics import diagnose_capability
from api2agent.generators.mcp import render_mcp_server
from api2agent.generators.readme import render_readme
from api2agent.generators.runner import render_runner
from api2agent.generators.smoke_test import render_manual_write_test, render_smoke_test
from api2agent.generators.tools import to_openai_tools
from api2agent.ir.models import Capability


def generate_package(capability: Capability, output_dir: Path, force: bool = False) -> Path:
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(
            f"Output directory is not empty: {output_dir}. Use --force to overwrite generated files."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    examples_dir = output_dir / "examples"
    examples_dir.mkdir(exist_ok=True)
    diagnostics = diagnose_capability(capability)

    _write_json(output_dir / "capability.json", capability.model_dump(mode="json", by_alias=True))
    _write_json(output_dir / "tools.json", to_openai_tools(capability))
    _write_json(output_dir / "diagnostics.json", diagnostics)
    _write_text(output_dir / "auth.env.example", _render_auth_env(capability))
    _write_text(output_dir / "README.md", render_readme(capability, diagnostics=diagnostics))
    _write_text(output_dir / "runner.py", render_runner(capability))
    _write_text(output_dir / "smoke_test.py", render_smoke_test(capability))
    _write_text(output_dir / "manual_write_test.py", render_manual_write_test(capability))
    _write_text(output_dir / "mcp_server.py", render_mcp_server(capability))
    _write_text(examples_dir / "openai_agent.py", _render_openai_placeholder(capability))
    _write_text(examples_dir / "claude_desktop_config.json", _render_claude_config_placeholder())

    return output_dir


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _render_auth_env(capability: Capability) -> str:
    env_names = []
    for auth in [capability.auth] + [tool.auth for tool in capability.tools if tool.auth is not None]:
        for env in _auth_env_names(auth):
            if env not in env_names:
                env_names.append(env)

    if not env_names:
        return "# This API does not require auth based on the parsed spec.\n"
    lines = ["# Fill these before running generated tools that require auth."]
    lines.extend(f"{name}=" for name in env_names)
    return "\n".join(lines) + "\n"


def _auth_env_names(auth) -> list[str]:
    credentials = auth.credentials or []
    if not credentials:
        credentials = [auth.model_dump(mode="json", by_alias=True)]

    envs: list[str] = []
    for credential in credentials:
        if credential.get("type") in {"api_key", "bearer"} and credential.get("env"):
            envs.append(str(credential["env"]))
    return envs


def _render_openai_placeholder(capability: Capability) -> str:
    return f'''"""OpenAI adapter example placeholder for {capability.name}."""

import json
from pathlib import Path


tools = json.loads(Path("../tools.json").read_text())
print(json.dumps(tools, indent=2))
'''


def _render_claude_config_placeholder() -> str:
    return '{\n  "mcpServers": {}\n}\n'
