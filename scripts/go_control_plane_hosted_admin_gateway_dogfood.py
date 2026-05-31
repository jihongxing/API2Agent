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
GATEWAY_SECRET = "dogfood-trusted-gateway-secret"
SUBJECT_ID = "hosted-admin-subject-dogfood"
ACTOR_ID = "hosted-admin-actor-dogfood"
PROJECT_ID = "hosted-project-dogfood"
ORGANIZATION_ID = "hosted-org-dogfood"
TOKEN_ID = "gateway-token-dogfood"


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
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    expected_status: set[int] | None = None,
) -> tuple[int, dict, dict[str, str]]:
    data = None
    request_headers = dict(headers or {})
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


def wait_for_health(url: str, server: subprocess.Popen[str], timeout_seconds: int = 30) -> dict:
    deadline = time.time() + timeout_seconds
    last: Exception | None = None
    while time.time() < deadline:
        if server.poll() is not None:
            stdout = server.stdout.read() if server.stdout is not None else ""
            stderr = server.stderr.read() if server.stderr is not None else ""
            raise RuntimeError(f"control plane exited early ({server.returncode})\nstdout:\n{stdout}\nstderr:\n{stderr}")
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


def create_replacement_registry(path: Path) -> dict:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    provider = data["providers"][0]
    provider["id"] = "httpbin_public_ip_v1"
    provider["provider_id"] = "httpbin"
    provider["metadata"]["base_url"] = "https://httpbin.org"
    data["credential_metadata"][0]["provider_id"] = "httpbin"
    data["snapshot"]["version"] = "snapshot_hosted_admin_gateway_dogfood_v1"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def trusted_gateway_headers(*, permissions: list[str], actor_id: str = ACTOR_ID) -> dict[str, str]:
    return {
        "X-API2Agent-Gateway-Authorization": f"Bearer {GATEWAY_SECRET}",
        "X-API2Agent-Principal-ID": SUBJECT_ID,
        "X-API2Agent-Actor-ID": actor_id,
        "X-API2Agent-Project-ID": PROJECT_ID,
        "X-API2Agent-Organization-ID": ORGANIZATION_ID,
        "X-API2Agent-Token-ID": TOKEN_ID,
        "X-API2Agent-Roles": "control-plane-admin,dogfood",
        "X-API2Agent-Permissions": ",".join(permissions),
    }


def start_control_plane(binary: Path, dsn: str, distribution_dir: Path, addr: str) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["API2AGENT_CONTROL_PLANE_POSTGRES_DSN"] = dsn
    env.pop("API2AGENT_CONTROL_PLANE_ADMIN_TOKEN", None)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    return subprocess.Popen(
        [
            str(binary),
            "serve",
            "--registry-store",
            "postgres",
            "--distribution-dir",
            str(distribution_dir),
            "--addr",
            addr,
            "--admin-identity-mode",
            "hosted",
            "--admin-authenticator",
            "trusted_gateway",
            "--trusted-gateway-secret",
            GATEWAY_SECRET,
        ],
        cwd=str(CONTROL_PLANE),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=flags,
    )


def assert_error_type(payload: dict, expected: str) -> None:
    actual = payload.get("error", {}).get("error_type")
    if actual != expected:
        raise RuntimeError(f"expected {expected}, got {payload}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dogfood hosted trusted-gateway admin auth against a running Go Control Plane service.")
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

    container = "api2agent-pg-hosted-admin-gateway-dogfood"
    pg_port = find_free_port()
    service_port = find_free_port()
    dsn = f"postgres://api2agent:api2agent@127.0.0.1:{pg_port}/api2agent?sslmode=disable"
    server: subprocess.Popen[str] | None = None
    report: dict = {
        "dogfood": "go_control_plane_hosted_admin_trusted_gateway_service",
        "status": "started",
        "container": container,
        "dsn": f"postgres://api2agent:REDACTED@127.0.0.1:{pg_port}/api2agent?sslmode=disable",
        "service_addr": f"127.0.0.1:{service_port}",
        "admin_token_flag_used": False,
        "gateway_secret_redacted": "REDACTED",
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

        replacement_path = workdir / "hosted-admin-gateway-replacement-registry.json"
        replacement_registry = create_replacement_registry(replacement_path)

        binary = workdir / ("api2agent-controlplane-hosted-gateway.exe" if sys.platform == "win32" else "api2agent-controlplane-hosted-gateway")
        run(["go", "build", "-o", str(binary), "./cmd/api2agent-controlplane"], cwd=CONTROL_PLANE)

        distribution_dir = workdir / "distribution"
        base_url = f"http://127.0.0.1:{service_port}"
        server = start_control_plane(binary, dsn, distribution_dir, f"127.0.0.1:{service_port}")
        health = wait_for_health(f"{base_url}/healthz", server)

        validate_permissions = ["control_plane.registry.validate"]
        mutation_permissions = ["control_plane.registry.validate", "control_plane.registry.import_replace"]
        validate_headers = trusted_gateway_headers(permissions=validate_permissions)
        validate_headers["Authorization"] = "Bearer untrusted-public-token"
        validate_headers["X-Actor-ID"] = "spoofed-public-actor"
        validate_status, validate_response, _ = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/validate",
            headers=validate_headers,
            expected_status={200},
        )
        if validate_response.get("valid") is not True:
            raise RuntimeError(f"expected registry validation success, got {validate_response}")

        missing_auth_status, missing_auth_response, _ = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/validate",
            headers={
                "Authorization": "Bearer untrusted-public-token",
                "X-Actor-ID": "spoofed-public-actor",
                "X-API2Agent-Principal-ID": SUBJECT_ID,
                "X-API2Agent-Project-ID": PROJECT_ID,
                "X-API2Agent-Permissions": "control_plane.registry.validate",
            },
            expected_status={401},
        )
        assert_error_type(missing_auth_response, "AUTH_ERROR")

        missing_permission_status, missing_permission_response, _ = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/validate",
            headers=trusted_gateway_headers(permissions=["control_plane.distribution.read_current"]),
            expected_status={403},
        )
        assert_error_type(missing_permission_response, "AUTHZ_DENIED")

        import_headers = trusted_gateway_headers(permissions=mutation_permissions)
        import_headers["X-Request-ID"] = "dogfood-hosted-gateway-import-1"
        import_headers["Idempotency-Key"] = "dogfood-hosted-gateway-idempotency-key"
        import_status, import_response, import_response_headers = request_json(
            "POST",
            f"{base_url}/v1/admin/registry/import-replace",
            headers=import_headers,
            body={"registry": replacement_registry, "source": "dogfood_hosted_admin_gateway"},
            expected_status={201},
        )
        if import_response.get("noop") is not False:
            raise RuntimeError(f"expected hosted gateway import noop=false, got {import_response}")
        if response_header(import_response_headers, "Idempotency-Replayed") != "":
            raise RuntimeError(f"first hosted gateway import should not be replayed, got {import_response_headers}")

        counts = {
            "registry_revisions": int(query_postgres_scalar(container, "SELECT count(*) FROM registry_revisions;")),
            "admin_audit_events": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_audit_events;")),
            "idempotency_records": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_mutation_idempotency_records;")),
            "providers": int(query_postgres_scalar(container, "SELECT count(*) FROM providers;")),
        }
        expected_counts = {
            "registry_revisions": 2,
            "admin_audit_events": 2,
            "idempotency_records": 1,
            "providers": 1,
        }
        if counts != expected_counts:
            raise RuntimeError(f"unexpected persistent counts: {counts}")

        audit_rows = query_postgres_json(
            container,
            f"""
SELECT json_agg(row_to_json(t) ORDER BY id)
FROM (
  SELECT
    id,
    actor_id,
    action,
    outcome,
    request_id,
    metadata->>'principal_subject_id' AS principal_subject_id,
    metadata->>'project_id' AS project_id,
    metadata->>'organization_id' AS organization_id,
    metadata->>'auth_method' AS auth_method,
    metadata->>'token_id' AS token_id,
    metadata->>'local_private' AS local_private,
    metadata::text LIKE '%{GATEWAY_SECRET}%' AS metadata_contains_gateway_secret
  FROM admin_audit_events
) AS t;
""",
        )
        if len(audit_rows) != 2:
            raise RuntimeError(f"expected two audit rows, got {audit_rows}")
        for row in audit_rows:
            if row["actor_id"] != ACTOR_ID:
                raise RuntimeError(f"expected trusted actor id in audit row, got {row}")
            if row["principal_subject_id"] != SUBJECT_ID or row["project_id"] != PROJECT_ID:
                raise RuntimeError(f"expected trusted subject/project metadata, got {row}")
            if row["organization_id"] != ORGANIZATION_ID or row["token_id"] != TOKEN_ID:
                raise RuntimeError(f"expected trusted org/token metadata, got {row}")
            if row["auth_method"] != "trusted_gateway" or row["local_private"] != "false":
                raise RuntimeError(f"expected trusted_gateway non-local audit metadata, got {row}")
            if row["metadata_contains_gateway_secret"]:
                raise RuntimeError(f"gateway secret leaked into audit metadata: {row}")
        validate_audit = next((row for row in audit_rows if row["action"] == "registry.validate"), None)
        import_audit = next((row for row in audit_rows if row["action"] == "registry.import_replace"), None)
        if validate_audit is None or import_audit is None:
            raise RuntimeError(f"expected validate and import audit rows, got {audit_rows}")

        idempotency_rows = query_postgres_json(
            container,
            """
SELECT json_agg(row_to_json(t) ORDER BY id)
FROM (
  SELECT
    id,
    project_id,
    actor_id,
    operation,
    first_request_id,
    status,
    response_status_code,
    registry_revision_id IS NOT NULL AS has_registry_revision,
    admin_audit_event_id IS NOT NULL AS has_admin_audit_event,
    noop
  FROM admin_mutation_idempotency_records
) AS t;
""",
        )
        if len(idempotency_rows) != 1:
            raise RuntimeError(f"expected one idempotency row, got {idempotency_rows}")
        idempotency_row = idempotency_rows[0]
        if idempotency_row["project_id"] != PROJECT_ID or idempotency_row["actor_id"] != ACTOR_ID:
            raise RuntimeError(f"expected trusted principal idempotency scope, got {idempotency_row}")
        if idempotency_row["operation"] != "registry.import_replace":
            raise RuntimeError(f"unexpected idempotency operation, got {idempotency_row}")
        if idempotency_row["response_status_code"] != 201 or idempotency_row["noop"]:
            raise RuntimeError(f"unexpected idempotency response evidence, got {idempotency_row}")
        if not idempotency_row["has_registry_revision"] or not idempotency_row["has_admin_audit_event"]:
            raise RuntimeError(f"expected idempotency evidence links, got {idempotency_row}")

        report.update(
            {
                "status": "passed",
                "seed_stdout": seed.stdout.strip(),
                "health": health,
                "validate_status": validate_status,
                "validate_response": {
                    "valid": validate_response.get("valid"),
                    "registry_store": validate_response.get("registry_store"),
                    "registry_fingerprint": validate_response.get("registry_fingerprint"),
                },
                "missing_gateway_auth_status": missing_auth_status,
                "missing_gateway_auth_error_type": missing_auth_response.get("error", {}).get("error_type"),
                "missing_permission_status": missing_permission_status,
                "missing_permission_error_type": missing_permission_response.get("error", {}).get("error_type"),
                "import_status": import_status,
                "import_response": import_response,
                "audit_counts": counts,
                "audit_rows": audit_rows,
                "idempotency_rows": idempotency_rows,
                "replacement_registry": str(replacement_path),
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
