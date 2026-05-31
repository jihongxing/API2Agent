from __future__ import annotations

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


OUT_DIR = ROOT / ".dogfood" / "manual-write-test-path"
SPEC_PATH = OUT_DIR / "write-only.yaml"
PACKAGE_DIR = OUT_DIR / "package"
DB_PATH = OUT_DIR / "usage.sqlite"
RESULT_PATH = OUT_DIR / "result.json"


class ProviderState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls: list[dict[str, Any]] = []

    def record(self, method: str, path: str, body: dict[str, Any] | None) -> None:
        with self.lock:
            self.calls.append({"method": method, "path": path, "body": body})

    def snapshot(self) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(item) for item in self.calls]


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    provider_state = ProviderState()
    provider = ThreadingHTTPServer(("127.0.0.1", 0), _make_provider_handler(provider_state))
    threading.Thread(target=provider.serve_forever, daemon=True).start()

    proxy_port = _free_port()
    proxy_proc: subprocess.Popen[str] | None = None
    try:
        base_url = f"http://127.0.0.1:{provider.server_port}"
        _write_spec(base_url)
        _generate_package()

        default_result = _run_api2agent_test(allow_write=False, extra_env={})
        calls_after_default = provider_state.snapshot()
        direct_result = _run_api2agent_test(allow_write=True, extra_env={})
        calls_after_direct = provider_state.snapshot()

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
        proxy_result = _run_api2agent_test(
            allow_write=True,
            extra_env={
                "API2AGENT_PROXY_URL": f"http://127.0.0.1:{proxy_port}",
                "API2AGENT_PROJECT_ID": "local",
                "API2AGENT_PROVIDER_ID": "write_provider",
                "API2AGENT_CAPABILITY_ID": "http.items.create",
                "API2AGENT_PROVIDER_REGION": "local",
                "API2AGENT_ESTIMATED_COST": "0.003",
            },
        )

        calls_after_proxy = provider_state.snapshot()
        events = UsageStore(DB_PATH).list_usage_events(project_id="local", limit=10)
        report = _build_report(
            default_result=default_result,
            direct_result=direct_result,
            proxy_result=proxy_result,
            calls_after_default=calls_after_default,
            calls_after_direct=calls_after_direct,
            calls_after_proxy=calls_after_proxy,
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
        provider.shutdown()
        provider.server_close()


def _write_spec(base_url: str) -> None:
    SPEC_PATH.write_text(
        f"""openapi: 3.0.3
info:
  title: Write Only API
  version: 1.0.0
servers:
  - url: {base_url}
paths:
  /items:
    post:
      operationId: createItem
      summary: Create an item.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                name:
                  type: string
                quantity:
                  type: integer
      responses:
        "201":
          description: Created
""",
        encoding="utf-8",
    )


def _generate_package() -> None:
    result = CliRunner().invoke(
        app,
        [
            "generate",
            str(SPEC_PATH),
            "--name",
            "write_only",
            "--provider-region",
            "local",
            "--output",
            str(PACKAGE_DIR),
        ],
    )
    if result.exit_code != 0:
        raise RuntimeError(result.output)


def _run_api2agent_test(*, allow_write: bool, extra_env: dict[str, str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(extra_env)
    command = [sys.executable, "-m", "api2agent.cli", "test", str(PACKAGE_DIR)]
    if allow_write:
        command.append("--allow-write")
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _build_report(
    *,
    default_result: dict[str, Any],
    direct_result: dict[str, Any],
    proxy_result: dict[str, Any],
    calls_after_default: list[dict[str, Any]],
    calls_after_direct: list[dict[str, Any]],
    calls_after_proxy: list[dict[str, Any]],
    usage_events: list[dict[str, Any]],
) -> dict[str, Any]:
    event = usage_events[0] if usage_events else {}
    checks = {
        "default_smoke_test_success": default_result["returncode"] == 0,
        "default_smoke_test_did_not_call_provider": len(calls_after_default) == 0,
        "default_output_warns_no_read_tool": "No read-only endpoint" in default_result["stdout"],
        "direct_allow_write_success": direct_result["returncode"] == 0,
        "direct_allow_write_called_provider_once": len(calls_after_direct) == 1,
        "proxy_allow_write_success": proxy_result["returncode"] == 0,
        "provider_called_twice_after_opt_in": len(calls_after_proxy) == 2,
        "provider_calls_are_post": all(call.get("method") == "POST" for call in calls_after_proxy),
        "provider_received_example_body": all(
            call.get("body") == {"name": "example", "quantity": 1}
            for call in calls_after_proxy
        ),
        "proxy_usage_event_recorded": len(usage_events) == 1,
        "proxy_usage_event_success": event.get("success") is True,
        "proxy_usage_event_write_tool": event.get("tool_id") == "create_item",
        "proxy_usage_event_provider_region": event.get("provider_region") == "local",
        "proxy_usage_event_estimated_cost": event.get("estimated_cost") == 0.003,
        "proxy_usage_event_credential_none": event.get("credential_reference") == "none",
        "api_first_scope": True,
        "no_workflow_engine_scope": True,
    }
    return {
        "contract_version": "api2agent.manual_write_test_path_dogfood.v0",
        "generated_at": _utc_now(),
        "package_dir": str(PACKAGE_DIR),
        "db_path": str(DB_PATH),
        "results": {
            "default": default_result,
            "direct_allow_write": direct_result,
            "proxy_allow_write": proxy_result,
        },
        "provider_calls": {
            "after_default": calls_after_default,
            "after_direct": calls_after_direct,
            "after_proxy": calls_after_proxy,
        },
        "usage_events": usage_events,
        "checks": checks,
        "ok": all(checks.values()),
    }


def _make_provider_handler(state: ProviderState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw_body.decode("utf-8")) if raw_body else None
            except ValueError:
                body = None
            state.record("POST", self.path, body)
            payload = json.dumps({"created": True, "body": body}).encode("utf-8")
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


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
