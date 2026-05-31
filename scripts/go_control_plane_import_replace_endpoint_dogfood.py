from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE = REPO_ROOT / "services" / "control-plane"
SCHEMA = CONTROL_PLANE / "schema" / "postgres" / "001_persistent_registry_store.sql"
REGISTRY = CONTROL_PLANE / "testdata" / "registry" / "network.public_ip.get.json"


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
    raise RuntimeError(f"control plane health did not become ready: {last}")


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


def create_replacement_registry(path: Path) -> dict:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    provider = data["providers"][0]
    provider["id"] = "httpbin_public_ip_v1"
    provider["provider_id"] = "httpbin"
    provider["metadata"]["base_url"] = "https://httpbin.org"
    data["credential_metadata"][0]["provider_id"] = "httpbin"
    data["snapshot"]["version"] = "snapshot_http_import_replace_live_v1"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def start_control_plane(binary: Path, dsn: str, distribution_dir: Path, addr: str) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["API2AGENT_CONTROL_PLANE_POSTGRES_DSN"] = dsn
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(
        [
            str(binary),
            "serve",
            "--registry-store",
            "postgres",
            "--admin-token",
            "dogfood-token",
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

    container = "api2agent-pg-import-replace-endpoint-dogfood"
    pg_port = find_free_port()
    service_port = find_free_port()
    dsn = f"postgres://api2agent:api2agent@127.0.0.1:{pg_port}/api2agent?sslmode=disable"
    server: subprocess.Popen[str] | None = None
    report: dict = {
        "dogfood": "go_control_plane_import_replace_endpoint",
        "status": "started",
        "container": container,
        "dsn": f"postgres://api2agent:REDACTED@127.0.0.1:{pg_port}/api2agent?sslmode=disable",
        "service_addr": f"127.0.0.1:{service_port}",
    }
    try:
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
                str(REGISTRY),
                "--postgres-dsn",
                dsn,
            ],
            cwd=CONTROL_PLANE,
        )

        replacement_registry_path = workdir / "http-import-replace-registry.json"
        replacement_registry = create_replacement_registry(replacement_registry_path)

        server_binary = workdir / ("api2agent-controlplane-import-endpoint.exe" if sys.platform == "win32" else "api2agent-controlplane-import-endpoint")
        run(["go", "build", "-o", str(server_binary), "./cmd/api2agent-controlplane"], cwd=CONTROL_PLANE)

        distribution_dir = workdir / "distribution"
        base_url = f"http://127.0.0.1:{service_port}"
        server = start_control_plane(server_binary, dsn, distribution_dir, f"127.0.0.1:{service_port}")
        health = wait_for_health(f"{base_url}/healthz")

        import_headers = {
            "X-Request-ID": "dogfood-http-import-replace-1",
            "Idempotency-Key": "dogfood-http-import-replace-key-1",
            "X-Actor-ID": "dogfood-http",
        }
        replace_status, replace_response = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/import-replace",
            token="dogfood-token",
            headers=import_headers,
            body={"registry": replacement_registry, "source": "dogfood_http_import"},
            expected_status={201},
        )
        if replace_response.get("noop") is not False:
            raise RuntimeError(f"expected replacement noop=false, got {replace_response}")

        noop_headers = {
            "X-Request-ID": "dogfood-http-import-replace-2",
            "Idempotency-Key": "dogfood-http-import-replace-key-2",
            "X-Actor-ID": "dogfood-http",
        }
        noop_status, noop_response = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/import-replace",
            token="dogfood-token",
            headers=noop_headers,
            body={"registry": replacement_registry, "source": "dogfood_http_import"},
            expected_status={200},
        )
        if noop_response.get("noop") is not True:
            raise RuntimeError(f"expected second import noop=true, got {noop_response}")

        _, validation = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/validate",
            token="dogfood-token",
            expected_status={200},
        )
        service_artifact_dir = workdir / "http-import-replace-artifact"
        _, exported = request_json(
            "POST",
            f"{base_url}/v1/admin/snapshots/export-artifact",
            token="dogfood-token",
            body={"output_dir": str(service_artifact_dir)},
            expected_status={201},
        )
        snapshot = json.loads((service_artifact_dir / "snapshot.json").read_text(encoding="utf-8"))
        providers = snapshot["providers"]
        if len(providers) != 1 or providers[0]["id"] != "httpbin_public_ip_v1":
            raise RuntimeError(f"expected replaced provider in exported snapshot, got {providers}")
        if snapshot["snapshot_version"] != "snapshot_http_import_replace_live_v1":
            raise RuntimeError(f"unexpected exported snapshot version: {snapshot['snapshot_version']}")

        audit_counts = {
            "registry_revisions": int(query_postgres_scalar(container, "SELECT count(*) FROM registry_revisions;")),
            "admin_audit_events": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_audit_events;")),
            "providers": int(query_postgres_scalar(container, "SELECT count(*) FROM providers;")),
        }
        if audit_counts["registry_revisions"] != 3:
            raise RuntimeError(f"expected seed plus replace plus export registry revisions, got {audit_counts}")
        if audit_counts["admin_audit_events"] != 4:
            raise RuntimeError(f"expected replace, noop, validate, export admin audit events, got {audit_counts}")
        if audit_counts["providers"] != 1:
            raise RuntimeError(f"expected one active provider row, got {audit_counts}")

        report.update(
            {
                "status": "passed",
                "seed_stdout": seed.stdout.strip(),
                "health": health,
                "replace_status": replace_status,
                "replace_response": replace_response,
                "noop_status": noop_status,
                "noop_response": noop_response,
                "validation": validation,
                "exported_snapshot_version": exported["manifest"]["snapshot_version"],
                "registry_fingerprint": snapshot["metadata"]["registry_fingerprint"],
                "snapshot_version": snapshot["snapshot_version"],
                "provider_id": providers[0]["id"],
                "provider_base_url": providers[0]["metadata"]["base_url"],
                "audit_counts": audit_counts,
                "replacement_registry": str(replacement_registry_path),
                "service_artifact_manifest": str(service_artifact_dir / "manifest.json"),
            }
        )
        return 0
    except Exception as exc:
        report.update({"status": "failed", "error": str(exc)})
        return 1
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        if not args.keep_container:
            subprocess.run(["podman", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
