from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api2agent.capabilities.execution import execute_capability
from api2agent.capabilities.models import ProviderCandidate, RoutingPolicy
from api2agent.control.storage import UsageStore
from api2agent.generators.package import generate_package
from api2agent.parsers.curl import parse_curl


FIXED_IP = "203.0.113.42"


class FakeIPHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] != "/":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"ip": FIXED_IP}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Python and Go data-plane public IP dogfood.")
    parser.add_argument("--output", type=Path, default=Path(".dogfood/go-python-dual-run/report.json"))
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    fake_provider = ThreadingHTTPServer(("127.0.0.1", 0), FakeIPHandler)
    fake_thread = threading.Thread(target=fake_provider.serve_forever, daemon=True)
    fake_thread.start()
    fake_base_url = f"http://127.0.0.1:{fake_provider.server_port}"

    try:
        tmp = Path(tempfile.mkdtemp(prefix="api2agent-dual-run-"))
        try:
            python_package = tmp / "python-ipify"
            capability = parse_curl(f"curl '{fake_base_url}?format=json'", name="network_public_ip_get")
            generate_package(capability, python_package, force=True)
            python_db = tmp / "python.sqlite"
            python_store = UsageStore(python_db)
            python_provider = ProviderCandidate(
                id="ipify_public_ip_v1",
                capability_id="network.public_ip.get",
                provider_id="ipify",
                tool_id="get",
                estimated_cost=0.0,
                regions=["global"],
                geo_affinity="global",
                output_mapping={"ip": "$.ip"},
                metadata={"package_dir": str(python_package)},
            )
            python_result = execute_capability(
                providers=[python_provider],
                capability_id="network.public_ip.get",
                params={},
                store=python_store,
                policy=RoutingPolicy(strategy="first"),
            )

            go_snapshot = tmp / "snapshot.json"
            go_snapshot.write_text(
                json.dumps(
                    {
                        "snapshot_version": "snapshot_dual_run_v1",
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
                                "metadata": {"base_url": fake_base_url},
                            }
                        ],
                        "routing_policy": {
                            "strategy": "first",
                            "routing_mode": "deterministic",
                            "routing_seed": "dual-run-v1",
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            go_dir = Path("services/data-plane")
            exe_name = "api2agent-dataplane.exe" if os.name == "nt" else "api2agent-dataplane"
            exe_path = tmp / exe_name
            subprocess.run(["go", "build", "-o", str(exe_path), "./cmd/api2agent-dataplane"], cwd=go_dir, check=True)

            go_event_dir = tmp / "go-events"
            go_port = free_port()
            env = os.environ.copy()
            env["API2AGENT_DATAPLANE_ADDR"] = f"127.0.0.1:{go_port}"
            env["API2AGENT_EVENT_DIR"] = str(go_event_dir)
            env["API2AGENT_SNAPSHOT"] = str(go_snapshot)
            proc = subprocess.Popen([str(exe_path)], cwd=go_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                wait_for_port(go_port)
                go_result = post_json(
                    f"http://127.0.0.1:{go_port}/v1/execute",
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

            go_events = read_jsonl(go_event_dir / "events.jsonl")
            report = build_report(python_result, go_result, go_events)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(report, indent=2, ensure_ascii=False))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    finally:
        fake_provider.shutdown()
        fake_provider.server_close()

    return 0


def build_report(python_result: dict, go_result: dict, go_events: list[dict]) -> dict:
    python_output = python_result.get("normalized_body")
    go_output = go_result.get("output")
    python_decision = python_result.get("routing_decision") or {}
    go_decision = next((event["record"] for event in go_events if event["event_type"] == "routing_decision"), {})
    go_usage = next((event["record"] for event in go_events if event["event_type"] == "usage_event"), {})
    comparisons = {
        "same_success": bool(python_result.get("ok")) == bool(go_result.get("success")),
        "same_output": python_output == go_output,
        "same_capability_id": python_decision.get("capability_id") == go_usage.get("capability_id"),
        "same_provider_id": python_result.get("provider_id") == go_usage.get("provider_id"),
        "go_has_request_context": any(event["event_type"] == "request_context" for event in go_events),
        "go_has_routing_decision": bool(go_decision),
        "go_has_usage_event": bool(go_usage),
        "go_has_decision_log": any(event["event_type"] == "decision_log" for event in go_events),
        "go_has_snapshot_version": bool(go_decision.get("snapshot_version")),
    }
    return {
        "dogfood": "go_python_dual_run_public_ip",
        "capability_id": "network.public_ip.get",
        "provider_id": "ipify",
        "python": {
            "ok": python_result.get("ok"),
            "provider_id": python_result.get("provider_id"),
            "normalized_body": python_output,
            "routing_strategy": python_decision.get("strategy"),
        },
        "go": {
            "success": go_result.get("success"),
            "output": go_output,
            "request_id": go_result.get("request_id"),
            "routing_decision_id": go_result.get("routing_decision_id"),
            "usage_event_id": go_result.get("usage_event_id"),
            "routing_strategy": go_decision.get("strategy"),
            "snapshot_version": go_decision.get("snapshot_version"),
            "event_types": [event["event_type"] for event in go_events],
        },
        "comparisons": comparisons,
        "passed": all(comparisons.values()),
    }


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
