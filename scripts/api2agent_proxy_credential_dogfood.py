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


OUT_DIR = ROOT / ".dogfood" / "proxy-credential"
PACKAGE_DIR = OUT_DIR / "package"
DB_PATH = OUT_DIR / "usage.sqlite"
CONFIG_PATH = OUT_DIR / "credentials.json"
RESULT_PATH = OUT_DIR / "result.json"
SECRET_ENV = "API2AGENT_DOGFOOD_CONFIG_TOKEN"
SECRET_VALUE = "proxy-config-secret"
REQUEST_INTENT_ENV = "DOGFOOD_AUTH_TOKEN"
PROVIDER_ID = "dogfood_provider"
CAPABILITY_ID = "http.authenticated.get"


class ProviderState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls = 0
        self.received_authorization: list[str] = []

    def record(self, authorization: str | None) -> None:
        with self.lock:
            self.calls += 1
            self.received_authorization.append(authorization or "")

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "calls": self.calls,
                "received_authorization": list(self.received_authorization),
            }


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
        provider_url = f"http://127.0.0.1:{provider.server_port}/bearer"
        _generate_package(provider_url)
        _write_credential_config()

        proxy_env = os.environ.copy()
        proxy_env[SECRET_ENV] = SECRET_VALUE
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

        result = _execute_generated_runner(proxy_port)
        events = UsageStore(DB_PATH).list_usage_events(project_id="local", limit=10)
        report = _build_report(
            result=result,
            provider=provider_state.snapshot(),
            events=[event.model_dump(mode="json") for event in events],
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


def _generate_package(provider_url: str) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "generate",
            "--curl",
            f"curl {provider_url} -H 'Authorization: Bearer placeholder'",
            "--name",
            "dogfood_auth",
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
                        "credential_id": "cred_proxy_dogfood",
                        "owner_type": "project",
                        "owner_id": "local",
                        "provider_id": PROVIDER_ID,
                        "auth_type": "bearer",
                        "injection_mode": "header",
                        "injection_name": "Authorization",
                        "source": "config",
                        "secret_ref": SECRET_ENV,
                        "scope": [f"capability:{CAPABILITY_ID}"],
                        "status": "active",
                        "rotation_hint": "dogfood-only",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _execute_generated_runner(proxy_port: int) -> dict[str, Any]:
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
                "API2AGENT_ROUTING_DECISION_ID": "decision_proxy_credential_dogfood",
            }
        )
        # Deliberately omit DOGFOOD_AUTH_TOKEN. The generated package sends
        # credential intent only; the proxy resolves the local config credential.
        os.environ.pop(REQUEST_INTENT_ENV, None)
        return module.execute_tool("get_bearer", {})
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def _build_report(*, result: dict[str, Any], provider: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    event = events[0] if events else {}
    metadata = (event.get("request_metadata") or {}).get("credential") or {}
    safe_provider = {
        "calls": provider.get("calls"),
        "received_authorization": [
            "[REDACTED]" if value else ""
            for value in provider.get("received_authorization", [])
        ],
    }
    encoded = json.dumps({"result": result, "events": events, "provider": safe_provider}, ensure_ascii=False)
    checks = {
        "generated_runner_proxy_success": result.get("ok") is True and result.get("proxied") is True,
        "provider_called_once": provider.get("calls") == 1,
        "proxy_injected_config_secret": provider.get("received_authorization") == [f"Bearer {SECRET_VALUE}"],
        "usage_event_recorded": len(events) == 1,
        "usage_event_success": event.get("success") is True,
        "credential_reference_config": event.get("credential_reference") == "config:cred_proxy_dogfood",
        "credential_metadata_source_config": metadata.get("source") == "config",
        "credential_metadata_rotation_hint": metadata.get("rotation_hint") == "dogfood-only",
        "provider_region_recorded": event.get("provider_region") == "local",
        "raw_secret_not_logged": SECRET_VALUE not in encoded,
        "request_intent_secret_not_required": REQUEST_INTENT_ENV not in os.environ,
        "api_first_scope": True,
        "no_vault_scope": True,
    }
    return {
        "contract_version": "api2agent.proxy_credential_dogfood.v0",
        "generated_at": _utc_now(),
        "package_dir": str(PACKAGE_DIR),
        "db_path": str(DB_PATH),
        "credential_config": str(CONFIG_PATH),
        "result": result,
        "provider": safe_provider,
        "usage_events": events,
        "checks": checks,
        "ok": all(checks.values()),
    }


def _make_provider_handler(state: ProviderState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            authorization = self.headers.get("Authorization")
            state.record(authorization)
            if authorization != f"Bearer {SECRET_VALUE}":
                body = json.dumps({"ok": False, "error": "unauthorized"}).encode("utf-8")
                self.send_response(401)
            else:
                body = json.dumps({"authenticated": True}).encode("utf-8")
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def _load_runner_module(package_dir: Path):
    module_name = f"api2agent_proxy_credential_runner_{time.time_ns()}"
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
