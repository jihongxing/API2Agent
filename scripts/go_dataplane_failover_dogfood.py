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


FIXED_IP = "203.0.113.99"


class FailingIPHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(500)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"primary failed")

    def log_message(self, format: str, *args) -> None:
        return


class FallbackIPHandler(BaseHTTPRequestHandler):
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
    parser = argparse.ArgumentParser(description="Dogfood Go Data Plane retry/failover behavior.")
    parser.add_argument("--output", type=Path, default=Path(".dogfood/go-dataplane-failover/report.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    failing_provider = ThreadingHTTPServer(("127.0.0.1", 0), FailingIPHandler)
    fallback_provider = ThreadingHTTPServer(("127.0.0.1", 0), FallbackIPHandler)
    threads = [
        threading.Thread(target=failing_provider.serve_forever, daemon=True),
        threading.Thread(target=fallback_provider.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()

    try:
        tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-failover-"))
        try:
            failing_url = f"http://127.0.0.1:{failing_provider.server_port}"
            fallback_url = f"http://127.0.0.1:{fallback_provider.server_port}"
            snapshot = tmp / "snapshot.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "snapshot_version": "snapshot_go_failover_v1",
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
                            provider("ipify_primary_v1", failing_url),
                            provider("ipify_fallback_v1", fallback_url),
                        ],
                        "routing_policy": {
                            "strategy": "first",
                            "routing_mode": "deterministic",
                            "routing_seed": "go-failover-v1",
                            "failover_policy": {
                                "enabled": True,
                                "max_attempts": 2,
                                "retry_on_error_types": ["PROVIDER_ERROR", "TIMEOUT"],
                                "retry_on_status_codes": [500, 502, 503, 504],
                                "attempt_timeout_policy": "fixed",
                            },
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

            event_dir = tmp / "events"
            port = free_port()
            env = os.environ.copy()
            env["API2AGENT_DATAPLANE_ADDR"] = f"127.0.0.1:{port}"
            env["API2AGENT_EVENT_DIR"] = str(event_dir)
            env["API2AGENT_SNAPSHOT"] = str(snapshot)
            proc = subprocess.Popen([str(exe_path)], cwd=go_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                wait_for_port(port)
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
            report = build_report(response, events)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(report, indent=2, ensure_ascii=False))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    finally:
        failing_provider.shutdown()
        failing_provider.server_close()
        fallback_provider.shutdown()
        fallback_provider.server_close()
    return 0


def provider(provider_id: str, base_url: str) -> dict:
    return {
        "id": provider_id,
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


def build_report(response: dict, events: list[dict]) -> dict:
    usage_events = [event["record"] for event in events if event["event_type"] == "usage_event"]
    decision_log = next((event["record"] for event in events if event["event_type"] == "decision_log"), {})
    first_usage = usage_events[0] if usage_events else {}
    second_usage = usage_events[1] if len(usage_events) > 1 else {}
    checks = {
        "response_success": response.get("success") is True,
        "fallback_output": (response.get("output") or {}).get("ip") == FIXED_IP,
        "two_usage_events": len(usage_events) == 2,
        "first_attempt_failed": first_usage.get("success") is False,
        "first_attempt_provider_error": ((first_usage.get("error") or {}).get("error_type") == "PROVIDER_ERROR"),
        "second_attempt_succeeded": second_usage.get("success") is True,
        "decision_log_success": decision_log.get("outcome") == "success",
        "decision_log_references_both_attempts": len(decision_log.get("usage_event_ids") or []) == 2,
        "selected_fallback_provider": decision_log.get("selected_provider_id") == "ipify_fallback_v1",
    }
    return {
        "dogfood": "go_dataplane_failover",
        "capability_id": "network.public_ip.get",
        "response": response,
        "event_types": [event["event_type"] for event in events],
        "usage_attempts": [
            {
                "id": usage.get("id"),
                "provider_id": usage.get("provider_id"),
                "success": usage.get("success"),
                "status_code": usage.get("status_code"),
                "error": usage.get("error"),
                "attempt_index": (usage.get("request_metadata") or {}).get("attempt_index"),
            }
            for usage in usage_events
        ],
        "decision_log": {
            "outcome": decision_log.get("outcome"),
            "selected_provider_id": decision_log.get("selected_provider_id"),
            "usage_event_ids": decision_log.get("usage_event_ids"),
            "routing_context": decision_log.get("routing_context"),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def free_port() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FallbackIPHandler)
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
