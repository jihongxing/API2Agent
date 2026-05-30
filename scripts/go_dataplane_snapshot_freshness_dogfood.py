from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


FIXED_IP = "203.0.113.120"


class ProviderState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls = 0

    def increment(self) -> None:
        with self.lock:
            self.calls += 1

    def count(self) -> int:
        with self.lock:
            return self.calls


def make_ip_handler(state: ProviderState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.increment()
            body = json.dumps({"ip": FIXED_IP}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Dogfood Go Data Plane snapshot freshness gate.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".dogfood/go-dataplane-snapshot-freshness/report.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-snapshot-freshness-"))
    try:
        go_dir = Path("services/data-plane")
        exe_name = "api2agent-dataplane.exe" if os.name == "nt" else "api2agent-dataplane"
        exe_path = tmp / exe_name
        subprocess.run(["go", "build", "-o", str(exe_path), "./cmd/api2agent-dataplane"], cwd=go_dir, check=True)
        conformance_exe_name = "api2agent-conformance.exe" if os.name == "nt" else "api2agent-conformance"
        conformance_exe = tmp / conformance_exe_name
        subprocess.run(["go", "build", "-o", str(conformance_exe), "./cmd/api2agent-conformance"], cwd=go_dir, check=True)

        active = run_scenario(
            tmp=tmp,
            go_dir=go_dir,
            exe_path=exe_path,
            conformance_exe=conformance_exe,
            name="active_snapshot_executes",
            snapshot_fetched_at="2026-05-30T00:00:00Z",
            snapshot_ttl="8760h",
        )
        expired = run_scenario(
            tmp=tmp,
            go_dir=go_dir,
            exe_path=exe_path,
            conformance_exe=conformance_exe,
            name="expired_snapshot_fails_closed",
            snapshot_fetched_at="2026-01-01T00:00:00Z",
            snapshot_ttl="1h",
        )

        report = {
            "dogfood": "go_dataplane_snapshot_freshness",
            "scenarios": [active, expired],
            "passed": active["passed"] and expired["passed"],
        }
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_scenario(
    *,
    tmp: Path,
    go_dir: Path,
    exe_path: Path,
    conformance_exe: Path,
    name: str,
    snapshot_fetched_at: str,
    snapshot_ttl: str,
) -> dict:
    provider_state = ProviderState()
    provider_server = ThreadingHTTPServer(("127.0.0.1", 0), make_ip_handler(provider_state))
    thread = threading.Thread(target=provider_server.serve_forever, daemon=True)
    thread.start()

    try:
        scenario_dir = tmp / name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        snapshot = write_snapshot(
            scenario_dir / "snapshot.json",
            snapshot_version=f"snapshot_go_freshness_{name}_v1",
            base_url=f"http://127.0.0.1:{provider_server.server_port}",
            snapshot_fetched_at=snapshot_fetched_at,
            snapshot_ttl=snapshot_ttl,
        )
        event_dir = scenario_dir / "events"
        port = free_port()
        env = os.environ.copy()
        env["API2AGENT_DATAPLANE_ADDR"] = f"127.0.0.1:{port}"
        env["API2AGENT_EVENT_DIR"] = str(event_dir)
        env["API2AGENT_SNAPSHOT"] = str(snapshot)
        proc = subprocess.Popen([str(exe_path)], cwd=go_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            wait_for_port(port)
            health = get_json(f"http://127.0.0.1:{port}/healthz")
            response = post_json(
                f"http://127.0.0.1:{port}/v1/execute",
                {
                    "project_id": "local",
                    "capability_id": "network.public_ip.get",
                    "capability_version": "0.1-migrated",
                    "input": {},
                    "execution_mode": "proxy",
                    "timeout_budget_ms": 5000,
                },
            )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        events = read_jsonl(event_dir / "events.jsonl")
        conformance_report = run_conformance(conformance_exe, event_dir / "events.jsonl")
        return build_scenario_report(
            name=name,
            health=health,
            response=response,
            events=events,
            conformance_report=conformance_report,
            provider_calls=provider_state.count(),
        )
    finally:
        provider_server.shutdown()
        provider_server.server_close()


def write_snapshot(
    path: Path,
    *,
    snapshot_version: str,
    base_url: str,
    snapshot_fetched_at: str,
    snapshot_ttl: str,
) -> Path:
    path.write_text(
        json.dumps(
            {
                "snapshot_version": snapshot_version,
                "snapshot_fetched_at": snapshot_fetched_at,
                "snapshot_ttl": snapshot_ttl,
                "snapshot_source": "pull",
                "capabilities": [
                    {
                        "id": "network.public_ip.get",
                        "version": "0.1-migrated",
                        "name": "Public IP Lookup",
                    }
                ],
                "providers": [
                    {
                        "id": "ipify_public_ip_v1",
                        "capability_id": "network.public_ip.get",
                        "capability_version": "0.1-migrated",
                        "provider_id": "ipify",
                        "provider_version": "1.0.0",
                        "mapping_version": "1.0.0",
                        "tool_id": "get_public_ip",
                        "regions": ["global"],
                        "geo_affinity": "global",
                        "estimated_cost": 0,
                        "metadata": {"base_url": base_url},
                    }
                ],
                "routing_policy": {
                    "strategy": "first",
                    "routing_mode": "deterministic",
                    "routing_seed": "go-snapshot-freshness-v1",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def build_scenario_report(
    *,
    name: str,
    health: dict,
    response: dict,
    events: list[dict],
    conformance_report: dict,
    provider_calls: int,
) -> dict:
    event_types = [event["event_type"] for event in events]
    decision_log = next((event["record"] for event in events if event["event_type"] == "decision_log"), {})
    error_type = (response.get("error") or {}).get("error_type")
    if name == "active_snapshot_executes":
        checks = {
            "health_ok": health.get("status") == "ok",
            "health_not_expired": health.get("snapshot_expired") is False,
            "response_success": response.get("success") is True,
            "provider_called_once": provider_calls == 1,
            "event_order_is_execution_graph": event_types == [
                "request_context",
                "routing_decision",
                "usage_event",
                "decision_log",
            ],
            "protocol_conformance": conformance_report.get("passed") is True,
        }
    else:
        checks = {
            "health_degraded": health.get("status") == "degraded",
            "health_expired": health.get("snapshot_expired") is True,
            "response_failed": response.get("success") is False,
            "snapshot_expired_error": error_type == "SNAPSHOT_EXPIRED",
            "provider_not_called": provider_calls == 0,
            "event_order_is_fail_closed_graph": event_types == ["request_context", "decision_log"],
            "decision_log_failure": decision_log.get("outcome") == "failure",
            "decision_log_has_snapshot_error": (decision_log.get("routing_context") or {}).get("error_type")
            == "SNAPSHOT_EXPIRED",
            "protocol_conformance": conformance_report.get("passed") is True,
        }

    return {
        "name": name,
        "health": health,
        "response": response,
        "provider_calls": provider_calls,
        "event_types": event_types,
        "event_sequence_ids": [event["event_sequence_id"] for event in events],
        "decision_log": {
            "outcome": decision_log.get("outcome"),
            "usage_event_ids": decision_log.get("usage_event_ids"),
            "routing_context": decision_log.get("routing_context"),
        },
        "conformance": conformance_report,
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_conformance(exe_path: Path, event_log: Path) -> dict:
    completed = subprocess.run(
        [str(exe_path), "--events", str(event_log)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        report = {
            "passed": False,
            "error": completed.stderr or completed.stdout or "invalid conformance output",
        }
    report["exit_code"] = completed.returncode
    return report


def get_json(url: str) -> dict:
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return json.loads(exc.read().decode("utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_port(port: int) -> None:
    import socket
    import time

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Go data plane did not listen on port {port}")


if __name__ == "__main__":
    raise SystemExit(main())
