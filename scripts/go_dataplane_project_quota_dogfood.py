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


FIXED_IP = "203.0.113.130"


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
    parser = argparse.ArgumentParser(description="Dogfood Go Data Plane project quota gate.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".dogfood/go-dataplane-project-quota/report.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-project-quota-"))
    try:
        go_dir = Path("services/data-plane")
        exe_name = "api2agent-dataplane.exe" if os.name == "nt" else "api2agent-dataplane"
        exe_path = tmp / exe_name
        subprocess.run(["go", "build", "-o", str(exe_path), "./cmd/api2agent-dataplane"], cwd=go_dir, check=True)
        conformance_exe_name = "api2agent-conformance.exe" if os.name == "nt" else "api2agent-conformance"
        conformance_exe = tmp / conformance_exe_name
        subprocess.run(["go", "build", "-o", str(conformance_exe), "./cmd/api2agent-conformance"], cwd=go_dir, check=True)

        scenario = run_scenario(tmp=tmp, go_dir=go_dir, exe_path=exe_path, conformance_exe=conformance_exe)
        report = {
            "dogfood": "go_dataplane_project_quota",
            "scenario": scenario,
            "passed": scenario["passed"],
        }
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_scenario(*, tmp: Path, go_dir: Path, exe_path: Path, conformance_exe: Path) -> dict:
    provider_state = ProviderState()
    provider_server = ThreadingHTTPServer(("127.0.0.1", 0), make_ip_handler(provider_state))
    thread = threading.Thread(target=provider_server.serve_forever, daemon=True)
    thread.start()

    try:
        scenario_dir = tmp / "quota"
        scenario_dir.mkdir(parents=True, exist_ok=True)
        snapshot = write_snapshot(scenario_dir / "snapshot.json", f"http://127.0.0.1:{provider_server.server_port}")
        event_dir = scenario_dir / "events"
        port = free_port()
        env = os.environ.copy()
        env["API2AGENT_DATAPLANE_ADDR"] = f"127.0.0.1:{port}"
        env["API2AGENT_EVENT_DIR"] = str(event_dir)
        env["API2AGENT_SNAPSHOT"] = str(snapshot)
        env["API2AGENT_PROJECT_QUOTA"] = "1"
        proc = subprocess.Popen([str(exe_path)], cwd=go_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            wait_for_port(port)
            first = post_json(
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
            second = post_json(
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
            health = get_json(f"http://127.0.0.1:{port}/healthz")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        events = read_jsonl(event_dir / "events.jsonl")
        conformance_report = run_conformance(conformance_exe, event_dir / "events.jsonl")
        return build_report(
            first=first,
            second=second,
            health=health,
            events=events,
            conformance_report=conformance_report,
            provider_calls=provider_state.count(),
        )
    finally:
        provider_server.shutdown()
        provider_server.server_close()


def write_snapshot(path: Path, base_url: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "snapshot_version": "snapshot_go_project_quota_v1",
                "snapshot_fetched_at": "2026-05-30T00:00:00Z",
                "snapshot_ttl": "24h",
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
                    "routing_seed": "go-project-quota-v1",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def build_report(*, first: dict, second: dict, health: dict, events: list[dict], conformance_report: dict, provider_calls: int) -> dict:
    decision_logs = [event["record"] for event in events if event["event_type"] == "decision_log"]
    first_decision, second_decision = decision_logs[0], decision_logs[1]
    first_error_type = ((first.get("error") or {}).get("error_type"))
    second_error_type = ((second.get("error") or {}).get("error_type"))
    checks = {
        "health_ok": health.get("status") == "ok",
        "first_request_success": first.get("success") is True,
        "second_request_quota_exceeded": second.get("success") is False and second_error_type == "QUOTA_EXCEEDED",
        "provider_called_once": provider_calls == 1,
        "first_decision_success": first_decision.get("outcome") == "success",
        "second_decision_failure": second_decision.get("outcome") == "failure",
        "second_decision_has_quota_error": (second_decision.get("routing_context") or {}).get("error_type") == "QUOTA_EXCEEDED",
        "second_decision_no_usage": len(second_decision.get("usage_event_ids") or []) == 0,
        "protocol_conformance": conformance_report.get("passed") is True,
    }
    return {
        "health": health,
        "first_response": first,
        "second_response": second,
        "provider_calls": provider_calls,
        "event_types": [event["event_type"] for event in events],
        "event_sequence_ids": [event["event_sequence_id"] for event in events],
        "decision_logs": [
            {
                "outcome": first_decision.get("outcome"),
                "routing_context": first_decision.get("routing_context"),
                "usage_event_ids": first_decision.get("usage_event_ids"),
            },
            {
                "outcome": second_decision.get("outcome"),
                "routing_context": second_decision.get("routing_context"),
                "usage_event_ids": second_decision.get("usage_event_ids"),
            },
        ],
        "conformance": conformance_report,
        "checks": checks,
        "passed": all(checks.values()),
        "error_types": {
            "first": first_error_type,
            "second": second_error_type,
        },
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


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return json.loads(exc.read().decode("utf-8"))


def get_json(url: str) -> dict:
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


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
