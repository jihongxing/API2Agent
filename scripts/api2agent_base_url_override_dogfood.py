from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api2agent.cli import app
from api2agent.control.storage import UsageStore


OUT_DIR = ROOT / ".dogfood" / "base-url-override"
SPEC_PATH = OUT_DIR / "base-url.yaml"
PACKAGE_DIR = OUT_DIR / "package"
DB_PATH = OUT_DIR / "usage.sqlite"
RESULT_PATH = OUT_DIR / "result.json"


class ProviderState:
    def __init__(self, label: str) -> None:
        self.label = label
        self.lock = threading.Lock()
        self.calls: list[str] = []

    def record(self, path: str) -> None:
        with self.lock:
            self.calls.append(path)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {"label": self.label, "calls": list(self.calls)}


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    original_state = ProviderState("original")
    override_state = ProviderState("override")
    tool_state = ProviderState("tool")
    original = ThreadingHTTPServer(("127.0.0.1", 0), _make_provider_handler(original_state))
    override = ThreadingHTTPServer(("127.0.0.1", 0), _make_provider_handler(override_state))
    tool = ThreadingHTTPServer(("127.0.0.1", 0), _make_provider_handler(tool_state))
    for server in [original, override, tool]:
        threading.Thread(target=server.serve_forever, daemon=True).start()

    proxy_port = _free_port()
    proxy_proc: subprocess.Popen[str] | None = None
    try:
        original_base_url = f"http://127.0.0.1:{original.server_port}/v1"
        override_base_url = f"http://127.0.0.1:{override.server_port}/staging"
        tool_base_url = f"http://127.0.0.1:{tool.server_port}/tool"
        _write_spec(original_base_url)
        _generate_package(original_base_url)

        proxy_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "api2agent.cli",
                "proxy",
                "--host",
                "127.0.0.1",
                "--port",
                str(proxy_port),
                "--db",
                str(DB_PATH),
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_port(proxy_port)

        direct_default = _execute_generated_runner({})
        direct_global_override = _execute_generated_runner({"API2AGENT_BASE_URL": override_base_url})
        direct_tool_override = _execute_generated_runner(
            {
                "API2AGENT_BASE_URL": override_base_url,
                "API2AGENT_TOOL_BASE_URL_GET_ITEMS": tool_base_url,
            }
        )
        invalid_override = _execute_generated_runner({"API2AGENT_BASE_URL": "localhost:9001"})
        proxy_override = _execute_generated_runner(
            {
                "API2AGENT_PROXY_URL": f"http://127.0.0.1:{proxy_port}",
                "API2AGENT_PROJECT_ID": "local",
                "API2AGENT_PROVIDER_ID": "base_url_provider",
                "API2AGENT_CAPABILITY_ID": "http.items.list",
                "API2AGENT_PROVIDER_REGION": "local",
                "API2AGENT_BASE_URL": override_base_url,
            }
        )

        events = UsageStore(DB_PATH).list_usage_events(project_id="local", limit=10)
        report = _build_report(
            original_base_url=original_base_url,
            override_base_url=override_base_url,
            tool_base_url=tool_base_url,
            direct_default=direct_default,
            direct_global_override=direct_global_override,
            direct_tool_override=direct_tool_override,
            invalid_override=invalid_override,
            proxy_override=proxy_override,
            providers={
                "original": original_state.snapshot(),
                "override": override_state.snapshot(),
                "tool": tool_state.snapshot(),
            },
            usage_events=[event.model_dump(mode="json") for event in events],
        )
        RESULT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not report["ok"]:
            raise SystemExit(1)
    finally:
        if proxy_proc is not None:
            proxy_proc.terminate()
            try:
                proxy_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proxy_proc.kill()
        for server in [original, override, tool]:
            server.shutdown()
            server.server_close()


def _generate_package(base_url: str) -> None:
    result = CliRunner().invoke(
        app,
        [
            "generate",
            str(SPEC_PATH),
            "--name",
            "base_url_items",
            "--provider-region",
            "local",
            "--output",
            str(PACKAGE_DIR),
        ],
    )
    if result.exit_code != 0:
        raise RuntimeError(result.output)


def _write_spec(base_url: str) -> None:
    SPEC_PATH.write_text(
        f"""openapi: 3.0.3
info:
  title: Base URL Items
  version: 1.0.0
servers:
  - url: {base_url}
paths:
  /items:
    get:
      operationId: getItems
      summary: List items.
      responses:
        "200":
          description: OK
""",
        encoding="utf-8",
    )


def _execute_generated_runner(env: dict[str, str]) -> dict[str, Any]:
    module = _load_runner_module(PACKAGE_DIR)
    old_env = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(old_env)
        for key in [
            "API2AGENT_BASE_URL",
            "API2AGENT_TOOL_BASE_URL_GET_ITEMS",
            "API2AGENT_PROXY_URL",
            "API2AGENT_PROJECT_ID",
            "API2AGENT_PROVIDER_ID",
            "API2AGENT_CAPABILITY_ID",
            "API2AGENT_PROVIDER_REGION",
        ]:
            os.environ.pop(key, None)
        os.environ.update(env)
        return module.execute_tool("get_items", {})
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def _build_report(
    *,
    original_base_url: str,
    override_base_url: str,
    tool_base_url: str,
    direct_default: dict[str, Any],
    direct_global_override: dict[str, Any],
    direct_tool_override: dict[str, Any],
    invalid_override: dict[str, Any],
    proxy_override: dict[str, Any],
    providers: dict[str, dict[str, Any]],
    usage_events: list[dict[str, Any]],
) -> dict[str, Any]:
    proxy_event = usage_events[0] if usage_events else {}
    proxy_url = (proxy_event.get("request_metadata") or {}).get("url")
    checks = {
        "direct_default_success": direct_default.get("ok") is True,
        "direct_global_override_success": direct_global_override.get("ok") is True,
        "direct_tool_override_success": direct_tool_override.get("ok") is True,
        "invalid_override_fails_fast": invalid_override.get("error", {}).get("type") == "invalid_base_url_override",
        "proxy_override_success": proxy_override.get("ok") is True and proxy_override.get("proxied") is True,
        "original_provider_called_once": providers["original"].get("calls") == ["/v1/items"],
        "override_provider_called_twice": providers["override"].get("calls") == ["/staging/items", "/staging/items"],
        "tool_provider_called_once": providers["tool"].get("calls") == ["/tool/items"],
        "usage_event_recorded": len(usage_events) == 1,
        "usage_event_url_uses_override": proxy_url is not None and str(proxy_url).startswith(override_base_url),
        "provider_region_preserved": proxy_event.get("provider_region") == "local",
        "credential_reference_none": proxy_event.get("credential_reference") == "none",
        "api_first_scope": True,
        "no_workflow_engine_scope": True,
    }
    return {
        "contract_version": "api2agent.base_url_override_dogfood.v0",
        "generated_at": _utc_now(),
        "package_dir": str(PACKAGE_DIR),
        "db_path": str(DB_PATH),
        "base_urls": {
            "original": original_base_url,
            "global_override": override_base_url,
            "tool_override": tool_base_url,
        },
        "results": {
            "direct_default": direct_default,
            "direct_global_override": direct_global_override,
            "direct_tool_override": direct_tool_override,
            "invalid_override": invalid_override,
            "proxy_override": proxy_override,
        },
        "providers": providers,
        "usage_events": usage_events,
        "checks": checks,
        "ok": all(checks.values()),
    }


def _make_provider_handler(state: ProviderState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.record(self.path)
            body = json.dumps({"provider": state.label, "path": self.path}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def _load_runner_module(package_dir: Path):
    module_name = f"api2agent_base_url_override_runner_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, package_dir / "runner.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load runner module from {package_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Proxy did not listen on port {port}")


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    main()
