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


def request_json(method: str, url: str, token: str | None = None, body: dict | None = None) -> dict:
    data = None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_health(url: str, timeout_seconds: int = 30) -> dict:
    deadline = time.time() + timeout_seconds
    last: Exception | None = None
    while time.time() < deadline:
        try:
            return request_json("GET", url)
        except (urllib.error.URLError, TimeoutError) as exc:
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


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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
        cwd=str(REPO_ROOT),
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

    container = "api2agent-pg-dogfood"
    dsn = "postgres://api2agent:api2agent@127.0.0.1:55432/api2agent?sslmode=disable"
    server: subprocess.Popen[str] | None = None
    report: dict = {
        "dogfood": "go_control_plane_live_postgres_store",
        "status": "started",
        "container": container,
        "dsn": "postgres://api2agent:REDACTED@127.0.0.1:55432/api2agent?sslmode=disable",
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
                "127.0.0.1:55432:5432",
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
        file_snapshot = workdir / "file-snapshot.json"
        pg_snapshot = workdir / "postgres-snapshot.json"
        run(
            [
                "go",
                "run",
                "./cmd/api2agent-controlplane",
                "export-snapshot",
                "--registry",
                str(REGISTRY),
                "--output",
                str(file_snapshot),
            ],
            cwd=CONTROL_PLANE,
        )
        run(
            [
                "go",
                "run",
                "./cmd/api2agent-controlplane",
                "export-snapshot",
                "--registry-store",
                "postgres",
                "--postgres-dsn",
                dsn,
                "--output",
                str(pg_snapshot),
            ],
            cwd=CONTROL_PLANE,
        )
        file_data = json.loads(file_snapshot.read_text(encoding="utf-8"))
        pg_data = json.loads(pg_snapshot.read_text(encoding="utf-8"))
        if file_data != pg_data:
            raise RuntimeError("file and postgres snapshots differ")

        cli_artifact = workdir / "postgres-cli-artifact"
        run(
            [
                "go",
                "run",
                "./cmd/api2agent-controlplane",
                "export-artifact",
                "--registry-store",
                "postgres",
                "--postgres-dsn",
                dsn,
                "--output-dir",
                str(cli_artifact),
            ],
            cwd=CONTROL_PLANE,
        )
        distribution_dir = workdir / "distribution"
        server_binary = workdir / ("api2agent-controlplane-dogfood.exe" if sys.platform == "win32" else "api2agent-controlplane-dogfood")
        run(["go", "build", "-o", str(server_binary), "./cmd/api2agent-controlplane"], cwd=CONTROL_PLANE)
        port = find_free_port()
        base_url = f"http://127.0.0.1:{port}"
        server = start_control_plane(server_binary, dsn, distribution_dir, f"127.0.0.1:{port}")
        health = wait_for_health(f"{base_url}/healthz")
        validation = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/validate",
            token="dogfood-token",
        )
        service_artifact_dir = workdir / "postgres-service-artifact"
        exported = request_json(
            "POST",
            f"{base_url}/v1/admin/snapshots/export-artifact",
            token="dogfood-token",
            body={"output_dir": str(service_artifact_dir)},
        )
        published = request_json(
            "POST",
            f"{base_url}/v1/admin/distribution/publish",
            token="dogfood-token",
            body={"artifact_dir": str(service_artifact_dir)},
        )
        current = request_json(
            "GET",
            f"{base_url}/v1/admin/distribution/current",
            token="dogfood-token",
        )
        audit_counts = {
            "registry_revisions": int(query_postgres_scalar(container, "SELECT count(*) FROM registry_revisions;")),
            "snapshot_artifact_publications": int(
                query_postgres_scalar(container, "SELECT count(*) FROM snapshot_artifact_publications;")
            ),
            "admin_audit_events": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_audit_events;")),
        }
        if audit_counts["registry_revisions"] < 1:
            raise RuntimeError(f"expected registry_revisions audit rows, got {audit_counts}")
        if audit_counts["snapshot_artifact_publications"] < 1:
            raise RuntimeError(f"expected snapshot_artifact_publications audit rows, got {audit_counts}")
        if audit_counts["admin_audit_events"] < 4:
            raise RuntimeError(f"expected admin_audit_events audit rows, got {audit_counts}")

        report.update(
            {
                "status": "passed",
                "seed_stdout": seed.stdout.strip(),
                "snapshots_equal": True,
                "registry_fingerprint": pg_data["metadata"]["registry_fingerprint"],
                "service_addr": f"127.0.0.1:{port}",
                "health": health,
                "validation": validation,
                "cli_artifact_manifest": str(cli_artifact / "manifest.json"),
                "service_artifact_manifest": str(service_artifact_dir / "manifest.json"),
                "service_exported_snapshot_version": exported["manifest"]["snapshot_version"],
                "service_published_snapshot_version": published["pointer"]["snapshot_version"],
                "service_current_snapshot_version": current["pointer"]["snapshot_version"],
                "audit_counts": audit_counts,
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
