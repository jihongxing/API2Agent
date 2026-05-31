from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE = REPO_ROOT / "services" / "control-plane"
DATA_PLANE = REPO_ROOT / "services" / "data-plane"
SCHEMA = CONTROL_PLANE / "schema" / "postgres" / "001_persistent_registry_store.sql"
REGISTRY = CONTROL_PLANE / "testdata" / "registry" / "network.public_ip.get.json"
ADMIN_TOKEN = "dogfood-token"
FIXED_IP = "203.0.113.88"


def run(cmd: list[str], *, cwd: Path = REPO_ROOT, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_postgres(container: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    last = ""
    while time.time() < deadline:
        result = subprocess.run(
            ["podman", "exec", container, "pg_isready", "-U", "api2agent", "-d", "api2agent"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        last = result.stdout.strip()
        if result.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError(f"postgres was not ready: {last}")


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    expected_status: set[int] | None = None,
) -> tuple[int, dict]:
    data = None
    request_headers = dict(headers or {})
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        payload = json.loads(exc.read().decode("utf-8"))
    if expected_status is not None and status not in expected_status:
        raise RuntimeError(f"unexpected HTTP status {status} for {url}: {payload}")
    return status, payload


def wait_for_health(url: str, timeout_seconds: int = 30) -> dict:
    deadline = time.time() + timeout_seconds
    last: Exception | None = None
    while time.time() < deadline:
        try:
            _, payload = request_json("GET", url, expected_status={200})
            return payload
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last = exc
            time.sleep(1)
    raise RuntimeError(f"service health did not become ready: {last}")


def make_httpbin_like_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps({"origin": FIXED_IP}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def start_httpbin_like_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_httpbin_like_handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}/ip"


def prepare_registry(path: Path, *, provider: str, base_url: str | None, snapshot_version: str) -> dict:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data["snapshot"]["version"] = snapshot_version
    data["snapshot"]["fetched_at"] = now
    data["snapshot"]["ttl"] = "168h"
    if provider == "httpbin":
        data["providers"][0]["id"] = "httpbin_public_ip_v1"
        data["providers"][0]["provider_id"] = "httpbin"
        data["providers"][0]["metadata"]["base_url"] = base_url
        data["credential_metadata"][0]["credential_id"] = "cred_local_httpbin"
        data["credential_metadata"][0]["provider_id"] = "httpbin"
        data["routing_policy"]["routing_seed"] = "control-plane-public-ip-httpbin-v1"
    elif provider == "ipify":
        if base_url:
            data["providers"][0]["metadata"]["base_url"] = base_url
    else:
        raise ValueError(f"unknown provider {provider}")
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def query_postgres_scalar(container: str, sql: str) -> str:
    result = run(
        [
            "podman",
            "exec",
            container,
            "psql",
            "-U",
            "api2agent",
            "-d",
            "api2agent",
            "-t",
            "-A",
            "-c",
            sql,
        ]
    )
    return result.stdout.strip()


def start_control_plane(binary: Path, dsn: str, distribution_dir: Path, addr: str) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["API2AGENT_CONTROL_PLANE_POSTGRES_DSN"] = dsn
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    return subprocess.Popen(
        [
            str(binary),
            "serve",
            "--registry-store",
            "postgres",
            "--admin-token",
            ADMIN_TOKEN,
            "--distribution-dir",
            str(distribution_dir),
            "--addr",
            addr,
        ],
        cwd=str(CONTROL_PLANE),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=flags,
    )


def start_data_plane(binary: Path, distribution_dir: Path, event_dir: Path, addr: str) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["API2AGENT_DATAPLANE_ADDR"] = addr
    env["API2AGENT_EVENT_DIR"] = str(event_dir)
    env["API2AGENT_SNAPSHOT"] = str(distribution_dir)
    env["API2AGENT_SNAPSHOT_RELOAD_POLICY"] = "manual"
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    return subprocess.Popen(
        [str(binary)],
        cwd=str(DATA_PLANE),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=flags,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stop_process(proc: subprocess.Popen[str] | None, label: str) -> dict:
    if proc is None:
        return {}
    proc.terminate()
    try:
        stdout, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
    return {f"{label}_stdout": stdout.strip(), f"{label}_stderr": stderr.strip()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--keep-container", action="store_true")
    args = parser.parse_args()

    if shutil.which("podman") is None:
        raise RuntimeError("podman is required for live Postgres dogfood")

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    workdir = output.parent / "artifacts"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    container = "api2agent-pg-snapshot-propagation-dogfood"
    pg_port = find_free_port()
    cp_port = find_free_port()
    dp_port = find_free_port()
    dsn = f"postgres://api2agent:api2agent@127.0.0.1:{pg_port}/api2agent?sslmode=disable"
    control_plane: subprocess.Popen[str] | None = None
    data_plane: subprocess.Popen[str] | None = None
    provider_server: ThreadingHTTPServer | None = None
    report: dict = {
        "dogfood": "go_control_plane_import_replace_snapshot_propagation",
        "status": "started",
        "container": container,
        "dsn": f"postgres://api2agent:REDACTED@127.0.0.1:{pg_port}/api2agent?sslmode=disable",
        "control_plane_addr": f"127.0.0.1:{cp_port}",
        "data_plane_addr": f"127.0.0.1:{dp_port}",
    }
    try:
        provider_server, httpbin_base_url = start_httpbin_like_server()
        initial_registry_path = workdir / "initial-registry.json"
        replacement_registry_path = workdir / "replacement-registry.json"
        prepare_registry(
            initial_registry_path,
            provider="ipify",
            base_url=None,
            snapshot_version="snapshot_propagation_ipify_v1",
        )
        replacement_registry = prepare_registry(
            replacement_registry_path,
            provider="httpbin",
            base_url=httpbin_base_url,
            snapshot_version="snapshot_propagation_httpbin_v2",
        )

        subprocess.run(["podman", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run(
            [
                "podman",
                "run",
                "-d",
                "--rm",
                "--name",
                container,
                "-e",
                "POSTGRES_PASSWORD=api2agent",
                "-e",
                "POSTGRES_USER=api2agent",
                "-e",
                "POSTGRES_DB=api2agent",
                "-p",
                f"127.0.0.1:{pg_port}:5432",
                "docker.io/library/postgres:16-alpine",
            ]
        )
        wait_for_postgres(container)
        run(
            ["podman", "exec", "-i", container, "psql", "-U", "api2agent", "-d", "api2agent", "-v", "ON_ERROR_STOP=1"],
            input_text=SCHEMA.read_text(encoding="utf-8"),
        )
        seed = run(
            [
                "go",
                "run",
                "./cmd/api2agent-controlplane",
                "seed-postgres",
                "--registry",
                str(initial_registry_path),
                "--postgres-dsn",
                dsn,
            ],
            cwd=CONTROL_PLANE,
        )

        cp_binary = workdir / ("api2agent-controlplane-propagation.exe" if sys.platform == "win32" else "api2agent-controlplane-propagation")
        dp_binary = workdir / ("api2agent-dataplane-propagation.exe" if sys.platform == "win32" else "api2agent-dataplane-propagation")
        run(["go", "build", "-o", str(cp_binary), "./cmd/api2agent-controlplane"], cwd=CONTROL_PLANE)
        run(["go", "build", "-o", str(dp_binary), "./cmd/api2agent-dataplane"], cwd=DATA_PLANE)

        distribution_dir = workdir / "distribution"
        cp_base_url = f"http://127.0.0.1:{cp_port}"
        control_plane = start_control_plane(cp_binary, dsn, distribution_dir, f"127.0.0.1:{cp_port}")
        cp_health = wait_for_health(f"{cp_base_url}/healthz")

        initial_artifact_dir = workdir / "initial-artifact"
        _, initial_export = request_json(
            "POST",
            f"{cp_base_url}/v1/admin/snapshots/export-artifact",
            token=ADMIN_TOKEN,
            body={"output_dir": str(initial_artifact_dir)},
            expected_status={201},
        )
        _, initial_publish = request_json(
            "POST",
            f"{cp_base_url}/v1/admin/distribution/publish",
            token=ADMIN_TOKEN,
            body={"artifact_dir": str(initial_artifact_dir)},
            expected_status={201},
        )

        event_dir = workdir / "events"
        dp_base_url = f"http://127.0.0.1:{dp_port}"
        data_plane = start_data_plane(dp_binary, distribution_dir, event_dir, f"127.0.0.1:{dp_port}")
        dp_health_before = wait_for_health(f"{dp_base_url}/healthz")
        if dp_health_before.get("snapshot_version") != "snapshot_propagation_ipify_v1":
            raise RuntimeError(f"expected Data Plane to start on v1, got {dp_health_before}")

        _, import_response = request_json(
            "POST",
            f"{cp_base_url}/v1/admin/registry/import-replace",
            token=ADMIN_TOKEN,
            headers={
                "X-Request-ID": "dogfood-propagation-import-replace",
                "Idempotency-Key": "dogfood-propagation-import-replace-key",
                "X-Actor-ID": "dogfood-propagation",
            },
            body={"registry": replacement_registry, "source": "dogfood_snapshot_propagation"},
            expected_status={201},
        )
        if import_response.get("noop") is not False:
            raise RuntimeError(f"expected import/replace noop=false, got {import_response}")

        replacement_artifact_dir = workdir / "replacement-artifact"
        _, replacement_export = request_json(
            "POST",
            f"{cp_base_url}/v1/admin/snapshots/export-artifact",
            token=ADMIN_TOKEN,
            body={"output_dir": str(replacement_artifact_dir)},
            expected_status={201},
        )
        _, replacement_publish = request_json(
            "POST",
            f"{cp_base_url}/v1/admin/distribution/publish",
            token=ADMIN_TOKEN,
            body={"artifact_dir": str(replacement_artifact_dir)},
            expected_status={201},
        )
        current_pointer = read_json(distribution_dir / "current.json")
        if current_pointer.get("snapshot_version") != "snapshot_propagation_httpbin_v2":
            raise RuntimeError(f"expected distribution current to point to v2, got {current_pointer}")

        _, reload_response = request_json(
            "POST",
            f"{dp_base_url}/v1/admin/reload-snapshot",
            body={},
            expected_status={200},
        )
        if reload_response.get("snapshot_version") != "snapshot_propagation_httpbin_v2":
            raise RuntimeError(f"expected reload to v2, got {reload_response}")
        dp_health_after = wait_for_health(f"{dp_base_url}/healthz")
        if dp_health_after.get("snapshot_version") != "snapshot_propagation_httpbin_v2":
            raise RuntimeError(f"expected Data Plane health to show v2, got {dp_health_after}")

        _, execute_response = request_json(
            "POST",
            f"{dp_base_url}/v1/execute",
            body={
                "project_id": "local",
                "capability_id": "network.public_ip.get",
                "capability_version": "0.1-migrated",
                "input": {},
                "execution_mode": "proxy",
                "timeout_budget_ms": 5000,
            },
            expected_status={200},
        )
        if execute_response.get("success") is not True:
            raise RuntimeError(f"expected successful Data Plane execution, got {execute_response}")
        if (execute_response.get("output") or {}).get("ip") != FIXED_IP:
            raise RuntimeError(f"expected fixed provider IP {FIXED_IP}, got {execute_response}")

        events = read_jsonl(event_dir / "events.jsonl")
        usage_events = [event["record"] for event in events if event["event_type"] == "usage_event"]
        decision_logs = [event["record"] for event in events if event["event_type"] == "decision_log"]
        reload_events = [event["record"] for event in events if event["event_type"] == "snapshot_reload_event"]
        usage = usage_events[-1] if usage_events else {}
        decision_log = decision_logs[-1] if decision_logs else {}
        if usage.get("provider_id") != "httpbin":
            raise RuntimeError(f"expected usage provider_id httpbin, got {usage}")
        if (usage.get("request_metadata") or {}).get("snapshot_version") != "snapshot_propagation_httpbin_v2":
            raise RuntimeError(f"expected usage snapshot v2, got {usage}")
        if decision_log.get("selected_provider_id") != "httpbin_public_ip_v1":
            raise RuntimeError(f"expected decision selected_provider_id httpbin_public_ip_v1, got {decision_log}")

        audit_counts = {
            "registry_revisions": int(query_postgres_scalar(container, "SELECT count(*) FROM registry_revisions;")),
            "snapshot_artifact_publications": int(query_postgres_scalar(container, "SELECT count(*) FROM snapshot_artifact_publications;")),
            "admin_audit_events": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_audit_events;")),
            "providers": int(query_postgres_scalar(container, "SELECT count(*) FROM providers;")),
        }
        if audit_counts["providers"] != 1:
            raise RuntimeError(f"expected one active provider row, got {audit_counts}")

        report.update(
            {
                "status": "passed",
                "seed_stdout": seed.stdout.strip(),
                "local_httpbin_base_url": httpbin_base_url,
                "control_plane_health": cp_health,
                "data_plane_health_before": dp_health_before,
                "data_plane_health_after": dp_health_after,
                "initial_exported_snapshot_version": initial_export["manifest"]["snapshot_version"],
                "initial_published_snapshot_version": initial_publish["pointer"]["snapshot_version"],
                "import_response": import_response,
                "replacement_exported_snapshot_version": replacement_export["manifest"]["snapshot_version"],
                "replacement_published_snapshot_version": replacement_publish["pointer"]["snapshot_version"],
                "reload_response": reload_response,
                "execute_response": execute_response,
                "usage_provider_id": usage.get("provider_id"),
                "usage_snapshot_version": (usage.get("request_metadata") or {}).get("snapshot_version"),
                "decision_selected_provider_id": decision_log.get("selected_provider_id"),
                "reload_event_count": len(reload_events),
                "event_types": [event["event_type"] for event in events],
                "audit_counts": audit_counts,
                "distribution_current": current_pointer,
            }
        )
        return 0
    except Exception as exc:
        report.update({"status": "failed", "error": str(exc)})
        return 1
    finally:
        report.update(stop_process(data_plane, "data_plane"))
        report.update(stop_process(control_plane, "control_plane"))
        if provider_server is not None:
            provider_server.shutdown()
        if not args.keep_container:
            subprocess.run(["podman", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
