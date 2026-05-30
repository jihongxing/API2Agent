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


SECRET_ENV = "API2AGENT_DOGFOOD_BEARER"
SECRET_VALUE = "local-dogfood-secret"
FIXED_IP = "203.0.113.120"


class AuthenticatedIPHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.headers.get("Authorization") != f"Bearer {SECRET_VALUE}":
            self.send_response(401)
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
    parser = argparse.ArgumentParser(description="Dogfood Go Data Plane env credential resolution.")
    parser.add_argument("--output", type=Path, default=Path(".dogfood/go-dataplane-credential/report.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    provider_server = ThreadingHTTPServer(("127.0.0.1", 0), AuthenticatedIPHandler)
    thread = threading.Thread(target=provider_server.serve_forever, daemon=True)
    thread.start()

    try:
        tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-credential-"))
        try:
            provider_url = f"http://127.0.0.1:{provider_server.server_port}"
            snapshot = tmp / "snapshot.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "snapshot_version": "snapshot_go_credential_v1",
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
                                "id": "ipify_auth_v1",
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
                            "routing_seed": "go-credential-v1",
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
            env[SECRET_ENV] = SECRET_VALUE
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
                        "credential": {
                            "credential_id": "cred_dogfood_bearer",
                            "owner_type": "project",
                            "owner_id": "local",
                            "provider_id": "ipify",
                            "auth_type": "bearer",
                            "injection_mode": "header",
                            "injection_name": "Authorization",
                            "source": "env",
                            "secret_ref": SECRET_ENV,
                            "status": "active",
                        },
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
        provider_server.shutdown()
        provider_server.server_close()
    return 0


def build_report(response: dict, events: list[dict]) -> dict:
    usage = next((event["record"] for event in events if event["event_type"] == "usage_event"), {})
    credential_metadata = (usage.get("request_metadata") or {}).get("credential") or {}
    serialized_events = json.dumps(events, ensure_ascii=False)
    checks = {
        "response_success": response.get("success") is True,
        "provider_output": (response.get("output") or {}).get("ip") == FIXED_IP,
        "usage_success": usage.get("success") is True,
        "credential_reference": (usage.get("credential_reference") or {}).get("credential_reference") == f"env:{SECRET_ENV}",
        "redacted_metadata_has_secret_ref": credential_metadata.get("secret_ref") == SECRET_ENV,
        "raw_secret_not_recorded": SECRET_VALUE not in serialized_events,
    }
    return {
        "dogfood": "go_dataplane_credential_resolution",
        "capability_id": "network.public_ip.get",
        "response": response,
        "event_types": [event["event_type"] for event in events],
        "usage": {
            "id": usage.get("id"),
            "success": usage.get("success"),
            "credential_reference": usage.get("credential_reference"),
            "credential_metadata": credential_metadata,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


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
    server = ThreadingHTTPServer(("127.0.0.1", 0), AuthenticatedIPHandler)
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
