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
from urllib.request import Request, urlopen


FIXED_IP = "203.0.113.130"


class FakeIPHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({"ip": FIXED_IP}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Dogfood Go Data Plane durable event ingestion.")
    parser.add_argument("--output", type=Path, default=Path(".dogfood/go-dataplane-durable-events/report.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    provider_server = ThreadingHTTPServer(("127.0.0.1", 0), FakeIPHandler)
    thread = threading.Thread(target=provider_server.serve_forever, daemon=True)
    thread.start()

    try:
        tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-durable-events-"))
        try:
            provider_url = f"http://127.0.0.1:{provider_server.server_port}"
            snapshot = write_snapshot(tmp / "snapshot.json", provider_url)
            go_dir = Path("services/data-plane")
            exe_name = "api2agent-dataplane.exe" if os.name == "nt" else "api2agent-dataplane"
            exe_path = tmp / exe_name
            subprocess.run(["go", "build", "-o", str(exe_path), "./cmd/api2agent-dataplane"], cwd=go_dir, check=True)
            conformance_exe_name = "api2agent-conformance.exe" if os.name == "nt" else "api2agent-conformance"
            conformance_exe = tmp / conformance_exe_name
            subprocess.run(["go", "build", "-o", str(conformance_exe), "./cmd/api2agent-conformance"], cwd=go_dir, check=True)

            event_dir = tmp / "events"
            first_response = run_once(exe_path, go_dir, snapshot, event_dir)
            second_response = run_once(exe_path, go_dir, snapshot, event_dir)

            event_log = event_dir / "events.jsonl"
            events = read_jsonl(event_log)
            conformance_report = run_conformance(conformance_exe, event_log)
            report = build_report(first_response, second_response, event_log, events, conformance_report)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(report, indent=2, ensure_ascii=False))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    finally:
        provider_server.shutdown()
        provider_server.server_close()
    return 0


def write_snapshot(path: Path, provider_url: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "snapshot_version": "snapshot_go_durable_events_v1",
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
                        "id": "ipify_durable_v1",
                        "capability_id": "network.public_ip.get",
                        "capability_version": "0.1-migrated",
                        "provider_id": "ipify",
                        "provider_version": "1.0.0",
                        "mapping_version": "1.0.0",
                        "tool_id": "get_public_ip",
                        "regions": ["global"],
                        "geo_affinity": "global",
                        "estimated_cost": 0,
                        "metadata": {"base_url": provider_url},
                    }
                ],
                "routing_policy": {
                    "strategy": "first",
                    "routing_mode": "deterministic",
                    "routing_seed": "go-durable-events-v1",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def run_once(exe_path: Path, go_dir: Path, snapshot: Path, event_dir: Path) -> dict:
    port = free_port()
    env = os.environ.copy()
    env["API2AGENT_DATAPLANE_ADDR"] = f"127.0.0.1:{port}"
    env["API2AGENT_EVENT_DIR"] = str(event_dir)
    env["API2AGENT_SNAPSHOT"] = str(snapshot)
    proc = subprocess.Popen([str(exe_path)], cwd=go_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        wait_for_port(port)
        return post_json(
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


def build_report(
    first_response: dict,
    second_response: dict,
    event_log: Path,
    events: list[dict],
    conformance_report: dict,
) -> dict:
    sequences = [event.get("event_sequence_id") for event in events]
    expected_sequences = list(range(1, len(events) + 1))
    event_types = [event.get("event_type") for event in events]
    checks = {
        "first_response_success": first_response.get("success") is True,
        "second_response_success": second_response.get("success") is True,
        "event_log_exists": event_log.exists(),
        "eight_events_for_two_calls": len(events) == 8,
        "sequence_continues_after_restart": sequences == expected_sequences,
        "no_duplicate_sequences": len(set(sequences)) == len(sequences),
        "two_request_contexts": event_types.count("request_context") == 2,
        "two_usage_events": event_types.count("usage_event") == 2,
        "two_decision_logs": event_types.count("decision_log") == 2,
        "protocol_conformance": conformance_report.get("passed") is True,
    }
    return {
        "dogfood": "go_dataplane_durable_events",
        "event_log": str(event_log),
        "first_response": first_response,
        "second_response": second_response,
        "event_count": len(events),
        "event_types": event_types,
        "event_sequence_ids": sequences,
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


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def free_port() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeIPHandler)
    port = server.server_port
    server.server_close()
    return port


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
