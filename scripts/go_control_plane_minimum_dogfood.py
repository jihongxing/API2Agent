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


FIXED_IP = "203.0.113.250"


def make_ip_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
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
    parser = argparse.ArgumentParser(description="Dogfood Go Control Plane minimum snapshot export and Go Data Plane consumption.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".dogfood/go-control-plane-minimum/report.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-control-plane-"))
    try:
        cp_dir = Path("services/control-plane")
        dp_dir = Path("services/data-plane")
        cp_exe_name = "api2agent-controlplane.exe" if os.name == "nt" else "api2agent-controlplane"
        dp_exe_name = "api2agent-dataplane.exe" if os.name == "nt" else "api2agent-dataplane"
        snapshot_check_exe_name = "api2agent-snapshot-check.exe" if os.name == "nt" else "api2agent-snapshot-check"
        cp_exe = tmp / cp_exe_name
        dp_exe = tmp / dp_exe_name
        snapshot_check_exe = tmp / snapshot_check_exe_name
        subprocess.run(["go", "build", "-o", str(cp_exe), "./cmd/api2agent-controlplane"], cwd=cp_dir, check=True)
        subprocess.run(["go", "build", "-o", str(dp_exe), "./cmd/api2agent-dataplane"], cwd=dp_dir, check=True)
        subprocess.run(["go", "build", "-o", str(snapshot_check_exe), "./cmd/api2agent-snapshot-check"], cwd=dp_dir, check=True)

        report = run_scenario(tmp=tmp, cp_exe=cp_exe, dp_exe=dp_exe, snapshot_check_exe=snapshot_check_exe, dp_dir=dp_dir)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_scenario(*, tmp: Path, cp_exe: Path, dp_exe: Path, snapshot_check_exe: Path, dp_dir: Path) -> dict:
    provider_server = ThreadingHTTPServer(("127.0.0.1", 0), make_ip_handler())
    thread = threading.Thread(target=provider_server.serve_forever, daemon=True)
    thread.start()
    try:
        scenario_dir = tmp / "control-plane-minimum"
        scenario_dir.mkdir(parents=True, exist_ok=True)
        registry = write_registry(scenario_dir / "registry.json", f"http://127.0.0.1:{provider_server.server_port}")
        invalid_registry = write_invalid_registry(scenario_dir / "invalid-registry.json", f"http://127.0.0.1:{provider_server.server_port}")
        snapshot = scenario_dir / "snapshot.json"
        subprocess.run(
            [str(cp_exe), "export-snapshot", "--registry", str(registry), "--output", str(snapshot)],
            cwd=dp_dir.parent,
            check=True,
        )
        snapshot_check = subprocess.run(
            [str(snapshot_check_exe), "--snapshot", str(snapshot)],
            cwd=dp_dir,
            check=False,
            capture_output=True,
            text=True,
        )
        snapshot_check_report = parse_json_report(snapshot_check)
        invalid_export = subprocess.run(
            [str(cp_exe), "export-snapshot", "--registry", str(invalid_registry), "--output", str(scenario_dir / "invalid-snapshot.json")],
            cwd=dp_dir.parent,
            check=False,
            capture_output=True,
            text=True,
        )
        event_dir = scenario_dir / "events"
        port = free_port()
        env = os.environ.copy()
        env["API2AGENT_DATAPLANE_ADDR"] = f"127.0.0.1:{port}"
        env["API2AGENT_EVENT_DIR"] = str(event_dir)
        env["API2AGENT_SNAPSHOT"] = str(snapshot)
        proc = subprocess.Popen([str(dp_exe)], cwd=dp_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        usage = next((event["record"] for event in events if event["event_type"] == "usage_event"), {})
        routing_decision = next((event["record"] for event in events if event["event_type"] == "routing_decision"), {})
        checks = {
            "control_plane_export_success": snapshot.exists(),
            "snapshot_check_passed": snapshot_check.returncode == 0
            and snapshot_check_report.get("passed") is True,
            "invalid_registry_rejected": invalid_export.returncode != 0
            and "references unknown project" in invalid_export.stderr,
            "health_snapshot_version_matches": health.get("snapshot_version") == "snapshot_control_plane_public_ip_v1",
            "response_success": response.get("success") is True,
            "response_ip_matches_provider": (response.get("output") or {}).get("ip") == FIXED_IP,
            "usage_has_attempt_id": (usage.get("request_metadata") or {}).get("attempt_id") == usage.get("id"),
            "routing_snapshot_version_matches": routing_decision.get("snapshot_version") == "snapshot_control_plane_public_ip_v1",
            "event_order_is_graph": [event["event_type"] for event in events] == [
                "request_context",
                "routing_decision",
                "usage_event",
                "decision_log",
            ],
        }
        return {
            "dogfood": "go_control_plane_minimum",
            "registry_path": str(registry),
            "invalid_registry_path": str(invalid_registry),
            "invalid_registry_exit_code": invalid_export.returncode,
            "invalid_registry_error": invalid_export.stderr.strip(),
            "snapshot_check": snapshot_check_report,
            "snapshot_path": str(snapshot),
            "health": health,
            "response": response,
            "event_types": [event["event_type"] for event in events],
            "event_sequence_ids": [event["event_sequence_id"] for event in events],
            "routing_decision": routing_decision,
            "usage_event": usage,
            "checks": checks,
            "passed": all(checks.values()),
        }
    finally:
        provider_server.shutdown()
        provider_server.server_close()


def write_registry(path: Path, base_url: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "projects": [
                    {
                        "id": "local",
                        "name": "Local Dogfood Project",
                        "status": "active",
                        "default_mode": "proxy",
                    }
                ],
                "api_keys": [
                    {
                        "id": "key_local_dev",
                        "project_id": "local",
                        "key_prefix": "local_",
                        "status": "active",
                    }
                ],
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
                        "status": "active",
                    }
                ],
                "routing_policy": {
                    "strategy": "first",
                    "routing_mode": "deterministic",
                    "routing_seed": "control-plane-public-ip-v1",
                },
                "snapshot": {
                    "version": "snapshot_control_plane_public_ip_v1",
                    "fetched_at": "2026-05-30T00:00:00Z",
                    "ttl": "24h",
                    "source": "pull",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_invalid_registry(path: Path, base_url: str) -> Path:
    write_registry(path, base_url)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["api_keys"][0]["project_id"] = "missing_project"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def parse_json_report(completed: subprocess.CompletedProcess[str]) -> dict:
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        report = {
            "passed": False,
            "error": completed.stderr or completed.stdout or "invalid json report",
        }
    report["exit_code"] = completed.returncode
    return report


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


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
