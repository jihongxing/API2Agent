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


FIXED_IP = "203.0.113.140"
SECRET_VALUE = "config-secret"


class ProviderState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls = 0
        self.received_api_keys: list[str] = []

    def record(self, api_key: str) -> None:
        with self.lock:
            self.calls += 1
            self.received_api_keys.append(api_key)

    def snapshot(self) -> dict:
        with self.lock:
            return {"calls": self.calls, "received_api_keys": list(self.received_api_keys)}


def make_ip_handler(state: ProviderState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            from urllib.parse import parse_qs, urlparse

            query = parse_qs(urlparse(self.path).query)
            api_key = (query.get("api_key") or [""])[0]
            state.record(api_key)
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
    parser = argparse.ArgumentParser(description="Dogfood Go Data Plane credential config resolution.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".dogfood/go-dataplane-credential-config/report.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-credential-config-"))
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
            "dogfood": "go_dataplane_credential_config",
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
        scenario_dir = tmp / "credential-config"
        scenario_dir.mkdir(parents=True, exist_ok=True)
        snapshot = write_snapshot(scenario_dir / "snapshot.json", f"http://127.0.0.1:{provider_server.server_port}")
        credential_config = write_credential_config(scenario_dir / "credentials.json")
        event_dir = scenario_dir / "events"
        port = free_port()
        env = os.environ.copy()
        env["API2AGENT_DATAPLANE_ADDR"] = f"127.0.0.1:{port}"
        env["API2AGENT_EVENT_DIR"] = str(event_dir)
        env["API2AGENT_SNAPSHOT"] = str(snapshot)
        env["API2AGENT_CREDENTIAL_CONFIG"] = str(credential_config)
        env["API2AGENT_CONFIG_TOKEN"] = SECRET_VALUE
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
            health = get_json(f"http://127.0.0.1:{port}/healthz")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        events = read_jsonl(event_dir / "events.jsonl")
        conformance_report = run_conformance(conformance_exe, event_dir / "events.jsonl")
        return build_report(response=response, health=health, events=events, conformance_report=conformance_report, provider=provider_state.snapshot())
    finally:
        provider_server.shutdown()
        provider_server.server_close()


def write_snapshot(path: Path, base_url: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "snapshot_version": "snapshot_go_credential_config_v1",
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
                    "routing_seed": "go-credential-config-v1",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_credential_config(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "credential_id": "cred_config_ipify",
                        "owner_type": "project",
                        "owner_id": "local",
                        "provider_id": "ipify",
                        "auth_type": "api_key",
                        "injection_mode": "query",
                        "injection_name": "api_key",
                        "source": "config",
                        "secret_ref": "API2AGENT_CONFIG_TOKEN",
                        "scope": ["capability:network.public_ip.get"],
                        "status": "active",
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def build_report(*, response: dict, health: dict, events: list[dict], conformance_report: dict, provider: dict) -> dict:
    usage = next((event["record"] for event in events if event["event_type"] == "usage_event"), {})
    credential_reference = usage.get("credential_reference") or {}
    metadata = (usage.get("request_metadata") or {}).get("credential") or {}
    encoded_events = json.dumps(events, ensure_ascii=False)
    checks = {
        "health_ok": health.get("status") == "ok",
        "response_success": response.get("success") is True,
        "provider_called_once": provider.get("calls") == 1,
        "provider_received_config_secret": provider.get("received_api_keys") == [SECRET_VALUE],
        "usage_has_config_reference": credential_reference.get("credential_reference") == "config:cred_config_ipify",
        "usage_strategy_static": credential_reference.get("resolution_strategy") == "static",
        "metadata_source_config": metadata.get("source") == "config",
        "raw_secret_not_logged": SECRET_VALUE not in encoded_events,
        "protocol_conformance": conformance_report.get("passed") is True,
    }
    return {
        "health": health,
        "response": response,
        "provider": provider,
        "event_types": [event["event_type"] for event in events],
        "event_sequence_ids": [event["event_sequence_id"] for event in events],
        "credential_reference": credential_reference,
        "credential_metadata": metadata,
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
