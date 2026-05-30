from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SLOW_PRIMARY_IP = "203.0.113.101"
FALLBACK_IP = "203.0.113.102"


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


def make_ip_handler(state: ProviderState, status_code: int, body: dict | None = None, delay_seconds: float = 0) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.increment()
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            payload = json.dumps(body or {"ip": FALLBACK_IP}).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, socket.timeout):
                return

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Dogfood Go Data Plane request-level timeout budget semantics.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".dogfood/go-dataplane-timeout-budget/report.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-timeout-budget-"))
    try:
        go_dir = Path("services/data-plane")
        exe_name = "api2agent-dataplane.exe" if os.name == "nt" else "api2agent-dataplane"
        exe_path = tmp / exe_name
        subprocess.run(["go", "build", "-o", str(exe_path), "./cmd/api2agent-dataplane"], cwd=go_dir, check=True)
        conformance_exe_name = "api2agent-conformance.exe" if os.name == "nt" else "api2agent-conformance"
        conformance_exe = tmp / conformance_exe_name
        subprocess.run(["go", "build", "-o", str(conformance_exe), "./cmd/api2agent-conformance"], cwd=go_dir, check=True)

        exhausted = run_scenario(
            tmp=tmp,
            go_dir=go_dir,
            exe_path=exe_path,
            conformance_exe=conformance_exe,
            name="budget_exhausted_prevents_fallback",
            primary_status=200,
            primary_body={"ip": SLOW_PRIMARY_IP},
            primary_delay_seconds=0.25,
            timeout_budget_ms=50,
        )
        fast_failure = run_scenario(
            tmp=tmp,
            go_dir=go_dir,
            exe_path=exe_path,
            conformance_exe=conformance_exe,
            name="fast_failure_allows_fallback",
            primary_status=500,
            primary_body={"error": "primary failed fast"},
            primary_delay_seconds=0,
            timeout_budget_ms=1000,
        )

        report = {
            "dogfood": "go_dataplane_timeout_budget",
            "scenarios": [exhausted, fast_failure],
            "passed": exhausted["passed"] and fast_failure["passed"],
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
    primary_status: int,
    primary_body: dict,
    primary_delay_seconds: float,
    timeout_budget_ms: int,
) -> dict:
    primary_state = ProviderState()
    fallback_state = ProviderState()
    primary = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_ip_handler(primary_state, primary_status, primary_body, primary_delay_seconds),
    )
    fallback = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_ip_handler(fallback_state, 200, {"ip": FALLBACK_IP}, 0),
    )
    threads = [
        threading.Thread(target=primary.serve_forever, daemon=True),
        threading.Thread(target=fallback.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()

    try:
        scenario_dir = tmp / name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        snapshot = write_snapshot(
            scenario_dir / "snapshot.json",
            snapshot_version=f"snapshot_go_timeout_budget_{name}_v1",
            primary_url=f"http://127.0.0.1:{primary.server_port}",
            fallback_url=f"http://127.0.0.1:{fallback.server_port}",
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
            response = post_json(
                f"http://127.0.0.1:{port}/v1/execute",
                {
                    "project_id": "local",
                    "capability_id": "network.public_ip.get",
                    "capability_version": "0.1-migrated",
                    "input": {},
                    "execution_mode": "proxy",
                    "timeout_budget_ms": timeout_budget_ms,
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
            timeout_budget_ms=timeout_budget_ms,
            response=response,
            events=events,
            conformance_report=conformance_report,
            primary_calls=primary_state.count(),
            fallback_calls=fallback_state.count(),
        )
    finally:
        primary.shutdown()
        primary.server_close()
        fallback.shutdown()
        fallback.server_close()


def write_snapshot(path: Path, *, snapshot_version: str, primary_url: str, fallback_url: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "snapshot_version": snapshot_version,
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
                    provider("ipify_primary_v1", primary_url),
                    provider("ipify_fallback_v1", fallback_url),
                ],
                "routing_policy": {
                    "strategy": "first",
                    "routing_mode": "deterministic",
                    "routing_seed": "go-timeout-budget-v1",
                    "failover_policy": {
                        "enabled": True,
                        "max_attempts": 2,
                        "retry_on_error_types": ["PROVIDER_ERROR", "TIMEOUT"],
                        "retry_on_status_codes": [500, 502, 503, 504],
                        "attempt_timeout_policy": "remaining_budget",
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


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


def build_scenario_report(
    *,
    name: str,
    timeout_budget_ms: int,
    response: dict,
    events: list[dict],
    conformance_report: dict,
    primary_calls: int,
    fallback_calls: int,
) -> dict:
    usage_events = [event["record"] for event in events if event["event_type"] == "usage_event"]
    decision_log = next((event["record"] for event in events if event["event_type"] == "decision_log"), {})
    attempts = [
        {
            "id": usage.get("id"),
            "success": usage.get("success"),
            "status_code": usage.get("status_code"),
            "error_type": ((usage.get("error") or {}).get("error_type")),
            "attempt_index": (usage.get("request_metadata") or {}).get("attempt_index"),
            "total_timeout_budget_ms": (usage.get("request_metadata") or {}).get("total_timeout_budget_ms"),
            "attempt_timeout_budget_ms": (usage.get("request_metadata") or {}).get("attempt_timeout_budget_ms"),
            "remaining_timeout_budget_ms": (usage.get("request_metadata") or {}).get("remaining_timeout_budget_ms"),
            "timeout_budget_policy": (usage.get("request_metadata") or {}).get("timeout_budget_policy"),
        }
        for usage in usage_events
    ]

    if name == "budget_exhausted_prevents_fallback":
        checks = {
            "response_failed": response.get("success") is False,
            "response_timeout": ((response.get("error") or {}).get("error_type") == "TIMEOUT"),
            "one_usage_event": len(usage_events) == 1,
            "fallback_not_called": fallback_calls == 0,
            "decision_log_failure": decision_log.get("outcome") == "failure",
            "timeout_budget_exhausted": (decision_log.get("routing_context") or {}).get("timeout_budget_exhausted") is True,
            "attempt_uses_total_deadline": all(attempt.get("timeout_budget_policy") == "total_deadline" for attempt in attempts),
            "protocol_conformance": conformance_report.get("passed") is True,
        }
    else:
        checks = {
            "response_success": response.get("success") is True,
            "fallback_output": (response.get("output") or {}).get("ip") == FALLBACK_IP,
            "two_usage_events": len(usage_events) == 2,
            "fallback_called_once": fallback_calls == 1,
            "decision_log_success": decision_log.get("outcome") == "success",
            "timeout_budget_not_exhausted": (decision_log.get("routing_context") or {}).get("timeout_budget_exhausted") is False,
            "attempts_use_total_deadline": all(attempt.get("timeout_budget_policy") == "total_deadline" for attempt in attempts),
            "protocol_conformance": conformance_report.get("passed") is True,
        }

    return {
        "name": name,
        "timeout_budget_ms": timeout_budget_ms,
        "provider_calls": {
            "primary": primary_calls,
            "fallback": fallback_calls,
        },
        "response": response,
        "event_types": [event["event_type"] for event in events],
        "event_sequence_ids": [event["event_sequence_id"] for event in events],
        "attempts": attempts,
        "decision_log": {
            "outcome": decision_log.get("outcome"),
            "selected_provider_id": decision_log.get("selected_provider_id"),
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
