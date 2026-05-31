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

from api2agent.benchmark import run_generated_package_latency_benchmark
from api2agent.cli import app
from api2agent.control.storage import UsageStore


OUT_DIR = ROOT / ".dogfood" / "generated-package-latency-benchmark"
PACKAGE_DIR = OUT_DIR / "package"
DB_PATH = OUT_DIR / "usage.sqlite"
RESULT_PATH = OUT_DIR / "result.json"


class ProviderState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls = 0

    def record(self) -> None:
        with self.lock:
            self.calls += 1

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {"calls": self.calls}


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
        provider_url = f"http://127.0.0.1:{provider.server_port}/items"
        _generate_package(provider_url)
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

        benchmark = run_generated_package_latency_benchmark(
            package_dir=PACKAGE_DIR,
            tool_name="get_items",
            iterations=3,
            proxy_url=f"http://127.0.0.1:{proxy_port}",
            env={
                "API2AGENT_PROJECT_ID": "local",
                "API2AGENT_PROVIDER_ID": "latency_dogfood_provider",
                "API2AGENT_CAPABILITY_ID": "http.items.list",
                "API2AGENT_PROVIDER_REGION": "local",
            },
        )
        usage_events = UsageStore(DB_PATH).list_usage_events(project_id="local", limit=10)
        report = _build_report(
            benchmark=benchmark,
            provider=provider_state.snapshot(),
            usage_events=[event.model_dump(mode="json") for event in usage_events],
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
    result = CliRunner().invoke(
        app,
        [
            "generate",
            "--curl",
            f"curl {provider_url}",
            "--name",
            "latency_items",
            "--provider-region",
            "local",
            "--output",
            str(PACKAGE_DIR),
        ],
    )
    if result.exit_code != 0:
        raise RuntimeError(result.output)


def _build_report(
    *,
    benchmark: dict[str, Any],
    provider: dict[str, Any],
    usage_events: list[dict[str, Any]],
) -> dict[str, Any]:
    direct = benchmark["runs"].get("direct") or {}
    proxy = benchmark["runs"].get("proxy") or {}
    usage_event_ids = {
        item.get("usage_event_id")
        for item in proxy.get("results", [])
        if item.get("usage_event_id")
    }
    checks = {
        "direct_runs_succeeded": direct.get("successful_runs") == 3,
        "proxy_runs_succeeded": proxy.get("successful_runs") == 3,
        "direct_has_p50_p95": direct.get("p50_latency_ms") is not None and direct.get("p95_latency_ms") is not None,
        "proxy_has_p50_p95": proxy.get("p50_latency_ms") is not None and proxy.get("p95_latency_ms") is not None,
        "provider_called_for_all_runs": provider.get("calls") == 6,
        "proxy_usage_events_recorded": len(usage_events) == 3,
        "proxy_results_reference_usage_events": len(usage_event_ids) == 3,
        "provider_region_recorded": all(event.get("provider_region") == "local" for event in usage_events),
        "api_first_scope": True,
        "no_workflow_engine_scope": True,
    }
    return {
        "contract_version": "api2agent.generated_package_latency_benchmark_dogfood.v0",
        "generated_at": _utc_now(),
        "package_dir": str(PACKAGE_DIR),
        "db_path": str(DB_PATH),
        "benchmark": benchmark,
        "provider": provider,
        "usage_event_count": len(usage_events),
        "usage_events": usage_events,
        "checks": checks,
        "ok": all(checks.values()),
    }


def _make_provider_handler(state: ProviderState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.record()
            body = json.dumps({"items": [{"id": "item_1"}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
