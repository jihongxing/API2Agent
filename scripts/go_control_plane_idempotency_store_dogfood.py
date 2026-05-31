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
ADMIN_TOKEN = "dogfood-token"


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
) -> tuple[int, dict, dict[str, str]]:
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
            response_headers = dict(response.headers.items())
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        response_headers = dict(exc.headers.items())
        payload = json.loads(exc.read().decode("utf-8"))
    if expected_status is not None and status not in expected_status:
        raise RuntimeError(f"unexpected HTTP status {status} for {url}: {payload}")
    return status, payload, response_headers


def wait_for_health(url: str, timeout_seconds: int = 30) -> dict:
    deadline = time.time() + timeout_seconds
    last: Exception | None = None
    while time.time() < deadline:
        try:
            _, payload, _ = request_json("GET", url, expected_status={200})
            return payload
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last = exc
            time.sleep(1)
    raise RuntimeError(f"control plane health did not become ready: {last}")


def response_header(headers: dict[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return ""


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


def query_postgres_json(container: str, sql: str) -> list[dict]:
    raw = query_postgres_scalar(container, sql)
    if raw == "":
        return []
    return json.loads(raw)


def create_replacement_registry(path: Path, *, snapshot_version: str) -> dict:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    provider = data["providers"][0]
    provider["id"] = "httpbin_public_ip_v1"
    provider["provider_id"] = "httpbin"
    provider["metadata"]["base_url"] = "https://httpbin.org"
    data["credential_metadata"][0]["provider_id"] = "httpbin"
    data["snapshot"]["version"] = snapshot_version
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


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

    container = "api2agent-pg-idempotency-dogfood"
    pg_port = find_free_port()
    service_port = find_free_port()
    dsn = f"postgres://api2agent:api2agent@127.0.0.1:{pg_port}/api2agent?sslmode=disable"
    server: subprocess.Popen[str] | None = None
    report: dict = {
        "dogfood": "go_control_plane_admin_mutation_idempotency_store",
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

        replacement_path = workdir / "idempotency-replacement-registry.json"
        replacement_registry = create_replacement_registry(
            replacement_path,
            snapshot_version="snapshot_idempotency_store_live_v1",
        )

        binary = workdir / ("api2agent-controlplane-idempotency.exe" if sys.platform == "win32" else "api2agent-controlplane-idempotency")
        run(["go", "build", "-o", str(binary), "./cmd/api2agent-controlplane"], cwd=CONTROL_PLANE)

        distribution_dir = workdir / "distribution"
        base_url = f"http://127.0.0.1:{service_port}"
        server = start_control_plane(binary, dsn, distribution_dir, f"127.0.0.1:{service_port}")
        health = wait_for_health(f"{base_url}/healthz")

        idempotency_headers = {
            "X-Request-ID": "dogfood-idempotency-first",
            "Idempotency-Key": "dogfood-idempotency-key-replay",
            "X-Actor-ID": "dogfood-idempotency",
        }
        body = {"registry": replacement_registry, "source": "dogfood_idempotency_store"}
        first_status, first_response, first_headers = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/import-replace",
            token=ADMIN_TOKEN,
            headers=idempotency_headers,
            body=body,
            expected_status={201},
        )
        if first_response.get("noop") is not False:
            raise RuntimeError(f"expected first import noop=false, got {first_response}")

        replay_headers = dict(idempotency_headers)
        replay_headers["X-Request-ID"] = "dogfood-idempotency-replay"
        replay_status, replay_response, replay_response_headers = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/import-replace",
            token=ADMIN_TOKEN,
            headers=replay_headers,
            body=body,
            expected_status={201},
        )
        if replay_response != first_response:
            raise RuntimeError(f"expected replay response to match first response, got {replay_response} vs {first_response}")
        if response_header(replay_response_headers, "Idempotency-Replayed") != "true":
            raise RuntimeError(f"expected replay header, got {replay_response_headers}")
        if response_header(replay_response_headers, "Idempotency-Record-ID") == "":
            raise RuntimeError(f"expected replay record id header, got {replay_response_headers}")

        conflict_body = {"registry": replacement_registry, "source": "dogfood_idempotency_store_conflict"}
        conflict_headers = dict(idempotency_headers)
        conflict_headers["X-Request-ID"] = "dogfood-idempotency-conflict"
        conflict_status, conflict_response, _ = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/import-replace",
            token=ADMIN_TOKEN,
            headers=conflict_headers,
            body=conflict_body,
            expected_status={409},
        )
        if conflict_response.get("error", {}).get("error_type") != "IDEMPOTENCY_KEY_CONFLICT":
            raise RuntimeError(f"expected IDEMPOTENCY_KEY_CONFLICT, got {conflict_response}")

        noop_headers = {
            "X-Request-ID": "dogfood-idempotency-noop",
            "Idempotency-Key": "dogfood-idempotency-key-noop",
            "X-Actor-ID": "dogfood-idempotency",
        }
        noop_status, noop_response, _ = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/import-replace",
            token=ADMIN_TOKEN,
            headers=noop_headers,
            body=body,
            expected_status={200},
        )
        if noop_response.get("noop") is not True:
            raise RuntimeError(f"expected independent no-op import, got {noop_response}")

        snapshot_path = workdir / "idempotency-postgres-snapshot.json"
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

        audit_counts = {
            "registry_revisions": int(query_postgres_scalar(container, "SELECT count(*) FROM registry_revisions;")),
            "admin_audit_events": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_audit_events;")),
            "idempotency_records": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_mutation_idempotency_records;")),
            "providers": int(query_postgres_scalar(container, "SELECT count(*) FROM providers;")),
        }
        if audit_counts != {
            "registry_revisions": 2,
            "admin_audit_events": 2,
            "idempotency_records": 2,
            "providers": 1,
        }:
            raise RuntimeError(f"unexpected persistent counts: {audit_counts}")

        idempotency_rows = query_postgres_json(
            container,
            """
SELECT json_agg(row_to_json(t) ORDER BY response_status_code DESC)
FROM (
  SELECT
    status,
    response_status_code,
    registry_revision_id IS NOT NULL AS has_registry_revision,
    admin_audit_event_id IS NOT NULL AS has_admin_audit_event,
    replay_count,
    last_replay_request_id,
    noop,
    idempotency_key_hash LIKE 'sha256:%' AS key_is_hashed,
    idempotency_key_prefix LIKE 'sha256:%' AS key_prefix_is_hashed
  FROM admin_mutation_idempotency_records
) AS t;
""",
        )
        if len(idempotency_rows) != 2:
            raise RuntimeError(f"expected two idempotency rows, got {idempotency_rows}")
        replace_row = next((row for row in idempotency_rows if row["response_status_code"] == 201), None)
        noop_row = next((row for row in idempotency_rows if row["response_status_code"] == 200), None)
        if replace_row is None or noop_row is None:
            raise RuntimeError(f"expected 201 and 200 idempotency rows, got {idempotency_rows}")
        if not replace_row["has_registry_revision"] or not replace_row["has_admin_audit_event"]:
            raise RuntimeError(f"replacement idempotency row missing evidence links: {replace_row}")
        if replace_row["replay_count"] != 1 or replace_row["last_replay_request_id"] != "dogfood-idempotency-replay":
            raise RuntimeError(f"replacement idempotency row missing replay metadata: {replace_row}")
        if noop_row["has_registry_revision"] or not noop_row["has_admin_audit_event"] or not noop_row["noop"]:
            raise RuntimeError(f"noop idempotency row has wrong linkage: {noop_row}")
        if not all(row["key_is_hashed"] and row["key_prefix_is_hashed"] for row in idempotency_rows):
            raise RuntimeError(f"expected hashed idempotency keys, got {idempotency_rows}")

        report.update(
            {
                "status": "passed",
                "seed_stdout": seed.stdout.strip(),
                "health": health,
                "first_status": first_status,
                "first_response": first_response,
                "first_replay_header": response_header(first_headers, "Idempotency-Replayed"),
                "replay_status": replay_status,
                "replay_response": replay_response,
                "replay_headers": {
                    "Idempotency-Replayed": response_header(replay_response_headers, "Idempotency-Replayed"),
                    "Idempotency-Record-ID": response_header(replay_response_headers, "Idempotency-Record-ID"),
                },
                "conflict_status": conflict_status,
                "conflict_response": conflict_response,
                "noop_status": noop_status,
                "noop_response": noop_response,
                "snapshot_version": snapshot["snapshot_version"],
                "provider_id": providers[0]["id"],
                "provider_base_url": providers[0]["metadata"]["base_url"],
                "audit_counts": audit_counts,
                "idempotency_rows": idempotency_rows,
                "replacement_registry": str(replacement_path),
                "snapshot_path": str(snapshot_path),
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
