from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
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


def create_replacement_registry(path: Path) -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    provider = data["providers"][0]
    provider["id"] = "httpbin_public_ip_v1"
    provider["provider_id"] = "httpbin"
    provider["metadata"]["base_url"] = "https://httpbin.org"
    data["credential_metadata"][0]["provider_id"] = "httpbin"
    data["snapshot"]["version"] = "snapshot_import_replace_live_v1"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_cli_output(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in output.strip().split():
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


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

    container = "api2agent-pg-import-replace-dogfood"
    port = find_free_port()
    dsn = f"postgres://api2agent:api2agent@127.0.0.1:{port}/api2agent?sslmode=disable"
    report: dict = {
        "dogfood": "go_control_plane_import_replace_postgres",
        "status": "started",
        "container": container,
        "dsn": f"postgres://api2agent:REDACTED@127.0.0.1:{port}/api2agent?sslmode=disable",
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
                f"127.0.0.1:{port}:5432",
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
        replacement_registry = workdir / "replacement-registry.json"
        create_replacement_registry(replacement_registry)
        replace = run(
            [
                "go",
                "run",
                "./cmd/api2agent-controlplane",
                "import-replace-postgres",
                "--registry",
                str(replacement_registry),
                "--postgres-dsn",
                dsn,
                "--actor-id",
                "dogfood",
                "--request-id",
                "dogfood-import-replace-1",
                "--idempotency-key",
                "dogfood-import-replace-key",
            ],
            cwd=CONTROL_PLANE,
        )
        noop = run(
            [
                "go",
                "run",
                "./cmd/api2agent-controlplane",
                "import-replace-postgres",
                "--registry",
                str(replacement_registry),
                "--postgres-dsn",
                dsn,
                "--actor-id",
                "dogfood",
                "--request-id",
                "dogfood-import-replace-2",
                "--idempotency-key",
                "dogfood-import-replace-key",
            ],
            cwd=CONTROL_PLANE,
        )
        replace_output = parse_cli_output(replace.stdout)
        noop_output = parse_cli_output(noop.stdout)
        if replace_output.get("noop") != "false":
            raise RuntimeError(f"expected first import to replace, got {replace.stdout}")
        if noop_output.get("noop") != "true":
            raise RuntimeError(f"expected second import to be no-op, got {noop.stdout}")

        snapshot_path = workdir / "postgres-replaced-snapshot.json"
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
                str(snapshot_path),
            ],
            cwd=CONTROL_PLANE,
        )
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        providers = snapshot["providers"]
        if len(providers) != 1 or providers[0]["id"] != "httpbin_public_ip_v1":
            raise RuntimeError(f"expected replaced provider in snapshot, got {providers}")
        if snapshot["snapshot_version"] != "snapshot_import_replace_live_v1":
            raise RuntimeError(f"unexpected snapshot version: {snapshot['snapshot_version']}")

        audit_counts = {
            "registry_revisions": int(query_postgres_scalar(container, "SELECT count(*) FROM registry_revisions;")),
            "admin_audit_events": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_audit_events;")),
            "providers": int(query_postgres_scalar(container, "SELECT count(*) FROM providers;")),
        }
        if audit_counts["registry_revisions"] != 2:
            raise RuntimeError(f"expected seed plus replace registry revisions, got {audit_counts}")
        if audit_counts["admin_audit_events"] != 2:
            raise RuntimeError(f"expected replace plus noop admin audit events, got {audit_counts}")
        if audit_counts["providers"] != 1:
            raise RuntimeError(f"expected one active provider row, got {audit_counts}")

        report.update(
            {
                "status": "passed",
                "seed_stdout": seed.stdout.strip(),
                "replace_stdout": replace.stdout.strip(),
                "noop_stdout": noop.stdout.strip(),
                "replace_noop": replace_output.get("noop"),
                "second_noop": noop_output.get("noop"),
                "registry_fingerprint": snapshot["metadata"]["registry_fingerprint"],
                "snapshot_version": snapshot["snapshot_version"],
                "provider_id": providers[0]["id"],
                "provider_base_url": providers[0]["metadata"]["base_url"],
                "audit_counts": audit_counts,
                "snapshot_path": str(snapshot_path),
                "replacement_registry": str(replacement_registry),
            }
        )
        return 0
    except Exception as exc:
        report.update({"status": "failed", "error": str(exc)})
        return 1
    finally:
        if not args.keep_container:
            subprocess.run(["podman", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

