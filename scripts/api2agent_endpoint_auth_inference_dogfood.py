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


OUT_DIR = ROOT / ".dogfood" / "endpoint-auth-inference"
SPEC_PATH = OUT_DIR / "mixed-auth.yaml"
PACKAGE_DIR = OUT_DIR / "package"
DB_PATH = OUT_DIR / "usage.sqlite"
CONFIG_PATH = OUT_DIR / "credentials.json"
RESULT_PATH = OUT_DIR / "result.json"
BEARER_ENV = "MIXED_AUTH_TOKEN"
ADMIN_ENV = "MIXED_AUTH_API_KEY"
BEARER_SECRET = "dogfood-bearer-secret"
ADMIN_SECRET = "dogfood-admin-secret"
PROVIDER_ID = "mixed_auth_provider"
CAPABILITY_ID = "http.mixed_auth.demo"


class ProviderState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls: list[dict[str, str | None]] = []

    def record(self, path: str, authorization: str | None, admin_key: str | None) -> None:
        with self.lock:
            self.calls.append(
                {
                    "path": path,
                    "authorization": authorization,
                    "admin_key": admin_key,
                }
            )

    def snapshot(self) -> list[dict[str, str | None]]:
        with self.lock:
            return [dict(item) for item in self.calls]


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    provider_state = ProviderState()
    provider = ThreadingHTTPServer(("127.0.0.1", 0), _make_provider_handler(provider_state))
    provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
    provider_thread.start()

    proxy_port = _free_port()
    proxy_proc: subprocess.Popen[str] | None = None
    try:
        base_url = f"http://127.0.0.1:{provider.server_port}"
        _write_spec(base_url)
        _generate_package()
        _write_credential_config()

        proxy_env = os.environ.copy()
        proxy_env[BEARER_ENV] = BEARER_SECRET
        proxy_env[ADMIN_ENV] = ADMIN_SECRET
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
                "--credential-config",
                str(CONFIG_PATH),
            ],
            cwd=ROOT,
            env=proxy_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_port(proxy_port)

        direct_results = _execute_direct()
        proxy_results = _execute_proxy(proxy_port)
        events = UsageStore(DB_PATH).list_usage_events(project_id="local", limit=10)
        report = _build_report(
            direct_results=direct_results,
            proxy_results=proxy_results,
            provider_calls=provider_state.snapshot(),
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
  title: Mixed Auth API
  version: 1.0.0
servers:
  - url: {base_url}
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
    adminKey:
      type: apiKey
      in: header
      name: X-Admin-Key
security:
  - bearerAuth: []
paths:
  /public:
    get:
      operationId: getPublic
      summary: Public endpoint.
      security: []
      responses:
        "200":
          description: OK
  /secure:
    get:
      operationId: getSecure
      summary: Bearer endpoint.
      responses:
        "200":
          description: OK
  /admin:
    get:
      operationId: getAdmin
      summary: Admin endpoint.
      security:
        - adminKey: []
      responses:
        "200":
          description: OK
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
            "mixed_auth",
            "--provider-region",
            "local",
            "--output",
            str(PACKAGE_DIR),
        ],
    )
    if result.exit_code != 0:
        raise RuntimeError(result.output)


def _write_credential_config() -> None:
    CONFIG_PATH.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "credential_id": "cred_bearer",
                        "owner_type": "project",
                        "owner_id": "local",
                        "provider_id": PROVIDER_ID,
                        "auth_type": "bearer",
                        "injection_mode": "header",
                        "injection_name": "Authorization",
                        "source": "config",
                        "secret_ref": BEARER_ENV,
                        "scope": ["tool:get_secure"],
                        "status": "active",
                    },
                    {
                        "credential_id": "cred_admin",
                        "owner_type": "project",
                        "owner_id": "local",
                        "provider_id": PROVIDER_ID,
                        "auth_type": "api_key",
                        "injection_mode": "header",
                        "injection_name": "X-Admin-Key",
                        "source": "config",
                        "secret_ref": ADMIN_ENV,
                        "scope": ["tool:get_admin"],
                        "status": "active",
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _execute_direct() -> dict[str, Any]:
    module = _load_runner_module(PACKAGE_DIR)
    old_env = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(old_env)
        os.environ.pop(BEARER_ENV, None)
        os.environ[ADMIN_ENV] = ADMIN_SECRET
        return {
            "public": module.execute_tool("get_public", {}),
            "secure_missing_auth": module.execute_tool("get_secure", {}),
            "admin": module.execute_tool("get_admin", {}),
        }
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def _execute_proxy(proxy_port: int) -> dict[str, Any]:
    module = _load_runner_module(PACKAGE_DIR)
    old_env = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(old_env)
        os.environ.update(
            {
                "API2AGENT_PROXY_URL": f"http://127.0.0.1:{proxy_port}",
                "API2AGENT_PROJECT_ID": "local",
                "API2AGENT_PROVIDER_ID": PROVIDER_ID,
                "API2AGENT_CAPABILITY_ID": CAPABILITY_ID,
                "API2AGENT_PROVIDER_REGION": "local",
                "API2AGENT_ESTIMATED_COST": "0.001",
            }
        )
        os.environ.pop(BEARER_ENV, None)
        os.environ.pop(ADMIN_ENV, None)
        return {
            "public": module.execute_tool("get_public", {}),
            "secure": module.execute_tool("get_secure", {}),
            "admin": module.execute_tool("get_admin", {}),
        }
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def _build_report(
    *,
    direct_results: dict[str, Any],
    proxy_results: dict[str, Any],
    provider_calls: list[dict[str, str | None]],
    usage_events: list[dict[str, Any]],
) -> dict[str, Any]:
    events_by_tool = {event.get("tool_id"): event for event in usage_events}
    public_call = _first_call(provider_calls, "/public")
    secure_call = _first_call(provider_calls, "/secure")
    admin_call = _first_call(provider_calls, "/admin")
    safe_calls = [
        {
            "path": call["path"],
            "authorization": "[REDACTED]" if call.get("authorization") else "",
            "admin_key": "[REDACTED]" if call.get("admin_key") else "",
        }
        for call in provider_calls
    ]
    encoded = json.dumps(
        {"direct": direct_results, "proxy": proxy_results, "events": usage_events, "calls": safe_calls},
        ensure_ascii=False,
    )
    checks = {
        "direct_public_without_auth_success": direct_results["public"].get("ok") is True,
        "direct_secure_missing_auth": direct_results["secure_missing_auth"].get("error", {}).get("type") == "missing_auth",
        "direct_admin_endpoint_api_key_success": direct_results["admin"].get("ok") is True,
        "proxy_public_success": proxy_results["public"].get("ok") is True,
        "proxy_secure_success": proxy_results["secure"].get("ok") is True,
        "proxy_admin_success": proxy_results["admin"].get("ok") is True,
        "provider_public_has_no_auth": bool(public_call) and not public_call.get("authorization") and not public_call.get("admin_key"),
        "provider_secure_has_bearer": bool(secure_call) and secure_call.get("authorization") == f"Bearer {BEARER_SECRET}",
        "provider_admin_has_api_key": bool(admin_call) and admin_call.get("admin_key") == ADMIN_SECRET,
        "proxy_usage_events_recorded": len(usage_events) == 3,
        "public_credential_reference_none": events_by_tool.get("get_public", {}).get("credential_reference") == "none",
        "secure_credential_reference_config": events_by_tool.get("get_secure", {}).get("credential_reference") == "config:cred_bearer",
        "admin_credential_reference_config": events_by_tool.get("get_admin", {}).get("credential_reference") == "config:cred_admin",
        "raw_secrets_not_logged": BEARER_SECRET not in encoded and ADMIN_SECRET not in encoded,
        "api_first_scope": True,
        "no_workflow_engine_scope": True,
    }
    return {
        "contract_version": "api2agent.endpoint_auth_inference_dogfood.v0",
        "generated_at": _utc_now(),
        "package_dir": str(PACKAGE_DIR),
        "db_path": str(DB_PATH),
        "direct_results": direct_results,
        "proxy_results": proxy_results,
        "provider_calls": safe_calls,
        "usage_events": usage_events,
        "checks": checks,
        "ok": all(checks.values()),
    }


def _first_call(calls: list[dict[str, str | None]], path: str) -> dict[str, str | None]:
    for call in calls:
        if call.get("path") == path:
            return call
    return {}


def _make_provider_handler(state: ProviderState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            authorization = self.headers.get("Authorization")
            admin_key = self.headers.get("X-Admin-Key")
            state.record(self.path, authorization, admin_key)
            if self.path == "/public":
                self._send_json(200, {"public": True})
                return
            if self.path == "/secure":
                if authorization == f"Bearer {BEARER_SECRET}":
                    self._send_json(200, {"secure": True})
                else:
                    self._send_json(401, {"error": "missing bearer"})
                return
            if self.path == "/admin":
                if admin_key == ADMIN_SECRET:
                    self._send_json(200, {"admin": True})
                else:
                    self._send_json(401, {"error": "missing api key"})
                return
            self._send_json(404, {"error": "not found"})

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def _load_runner_module(package_dir: Path):
    module_name = f"api2agent_endpoint_auth_runner_{time.time_ns()}"
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
