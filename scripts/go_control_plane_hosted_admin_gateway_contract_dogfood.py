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
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE = REPO_ROOT / "services" / "control-plane"
SCHEMA = CONTROL_PLANE / "schema" / "postgres" / "001_persistent_registry_store.sql"
REGISTRY = CONTROL_PLANE / "testdata" / "registry" / "network.public_ip.get.json"

GATEWAY_SECRET = "dogfood-trusted-gateway-secret-contract"
GATEWAY_KEY_ID = "dogfood-gateway-key-contract"
PUBLIC_ADMIN_TOKEN = "dogfood-public-admin-token"
PUBLIC_READONLY_TOKEN = "dogfood-public-readonly-token"
STATIC_POLICY_SOURCE = "hosted-admin-gateway-static-dogfood-policy"
STATIC_POLICY_VERSION = "static-v1"

HARNESS_PRINCIPAL_ID = "gateway-harness-principal"
HARNESS_ACTOR_ID = "gateway-harness-actor"
HARNESS_PROJECT_ID = "gateway-harness-project"
HARNESS_ORGANIZATION_ID = "gateway-harness-org"
HARNESS_TOKEN_ID_ADMIN = "gateway-harness-token-admin"
HARNESS_TOKEN_ID_READONLY = "gateway-harness-token-readonly"

SPOOFED_PRINCIPAL_ID = "spoofed-public-principal"
SPOOFED_ACTOR_ID = "spoofed-public-actor"
SPOOFED_PROJECT_ID = "spoofed-public-project"
SPOOFED_ORGANIZATION_ID = "spoofed-public-org"
SPOOFED_TOKEN_ID = "spoofed-public-token-id"

PERMISSION_REGISTRY_VALIDATE = "control_plane.registry.validate"
PERMISSION_REGISTRY_IMPORT_REPLACE = "control_plane.registry.import_replace"
PERMISSION_REGISTRY_PROJECT_PARTITION_REPLACE = "control_plane.registry.project_partition_replace"
PERMISSION_SNAPSHOT_EXPORT_ARTIFACT = "control_plane.snapshot.export_artifact"
PERMISSION_DISTRIBUTION_PUBLISH = "control_plane.distribution.publish"
PERMISSION_DISTRIBUTION_READ_CURRENT = "control_plane.distribution.read_current"

ENDPOINT_PERMISSIONS = {
    ("POST", "/v1/admin/registry/validate"): PERMISSION_REGISTRY_VALIDATE,
    ("POST", "/v1/admin/registry/import-replace"): PERMISSION_REGISTRY_IMPORT_REPLACE,
    ("POST", "/v1/admin/registry/project-partition/replace"): PERMISSION_REGISTRY_PROJECT_PARTITION_REPLACE,
    ("POST", "/v1/admin/snapshots/export-artifact"): PERMISSION_SNAPSHOT_EXPORT_ARTIFACT,
    ("GET", "/v1/admin/distribution/current"): PERMISSION_DISTRIBUTION_READ_CURRENT,
    ("POST", "/v1/admin/distribution/publish"): PERMISSION_DISTRIBUTION_PUBLISH,
}
HEALTH_PATHS = {("GET", "/healthz")}
FORWARDED_PATHS = set(ENDPOINT_PERMISSIONS) | HEALTH_PATHS
PATHS_WITH_METHODS: dict[str, set[str]] = {"/healthz": {"GET"}}
for endpoint_method, endpoint_path in ENDPOINT_PERMISSIONS:
    PATHS_WITH_METHODS.setdefault(endpoint_path, set()).add(endpoint_method)
SAFE_REQUEST_HEADERS = {
    "content-type": "Content-Type",
    "x-request-id": "X-Request-ID",
    "idempotency-key": "Idempotency-Key",
}
HOP_BY_HOP_RESPONSE_HEADERS = {
    "connection",
    "content-length",
    "date",
    "server",
    "transfer-encoding",
}


@dataclass(frozen=True)
class StaticPolicy:
    principal_id: str
    actor_id: str
    project_id: str
    organization_id: str
    token_id: str
    roles: tuple[str, ...]
    permissions: tuple[str, ...]


@dataclass(frozen=True)
class GatewayPermissionDecision:
    allowed: bool
    status: int
    error_type: str
    deny_reason: str
    subject_id: str = ""
    actor_id: str = ""
    project_id: str = ""
    organization_id: str = ""
    token_id: str = ""
    roles: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    policy_source: str = STATIC_POLICY_SOURCE
    policy_version: str = STATIC_POLICY_VERSION
    permission_source: str = STATIC_POLICY_SOURCE
    resolved_at: str = ""


ADMIN_POLICY = StaticPolicy(
    principal_id=HARNESS_PRINCIPAL_ID,
    actor_id=HARNESS_ACTOR_ID,
    project_id=HARNESS_PROJECT_ID,
    organization_id=HARNESS_ORGANIZATION_ID,
    token_id=HARNESS_TOKEN_ID_ADMIN,
    roles=("control-plane-admin", "dogfood"),
    permissions=(
        PERMISSION_REGISTRY_VALIDATE,
        PERMISSION_REGISTRY_IMPORT_REPLACE,
        PERMISSION_REGISTRY_PROJECT_PARTITION_REPLACE,
        PERMISSION_SNAPSHOT_EXPORT_ARTIFACT,
        PERMISSION_DISTRIBUTION_PUBLISH,
        PERMISSION_DISTRIBUTION_READ_CURRENT,
    ),
)
READONLY_POLICY = StaticPolicy(
    principal_id="gateway-harness-readonly-principal",
    actor_id="gateway-harness-readonly-actor",
    project_id=HARNESS_PROJECT_ID,
    organization_id=HARNESS_ORGANIZATION_ID,
    token_id=HARNESS_TOKEN_ID_READONLY,
    roles=("control-plane-readonly", "dogfood"),
    permissions=(PERMISSION_REGISTRY_VALIDATE, PERMISSION_DISTRIBUTION_READ_CURRENT),
)
PUBLIC_TOKEN_POLICIES = {
    PUBLIC_ADMIN_TOKEN: ADMIN_POLICY,
    PUBLIC_READONLY_TOKEN: READONLY_POLICY,
}


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
    raise RuntimeError(f"health did not become ready: {last}")


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
    data["snapshot"]["version"] = "snapshot_hosted_admin_gateway_contract_harness_v1"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


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
            "--trusted-gateway-secrets",
            GATEWAY_SECRET,
            "--trusted-gateway-key-id",
            GATEWAY_KEY_ID,
        ],
        cwd=str(CONTROL_PLANE),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=flags,
    )


def bearer_token(header: str) -> str | None:
    prefix = "Bearer "
    if not header.startswith(prefix):
        return None
    token = header.removeprefix(prefix).strip()
    return token or None


def endpoint_permission(method: str, path: str) -> str | None:
    return ENDPOINT_PERMISSIONS.get((method.upper(), path))


def resolve_gateway_admin_principal(
    headers: Any,
    endpoint_required_permission: str,
    *,
    permission_source_available: bool = True,
    resolved_at: str = "2026-06-01T00:00:00Z",
) -> GatewayPermissionDecision:
    if not permission_source_available:
        return GatewayPermissionDecision(
            allowed=False,
            status=503,
            error_type="PERMISSION_SOURCE_UNAVAILABLE",
            deny_reason="gateway permission source is unavailable",
            resolved_at=resolved_at,
        )

    token = bearer_token(headers.get("Authorization", ""))
    if token is None:
        return GatewayPermissionDecision(
            allowed=False,
            status=401,
            error_type="PUBLIC_AUTH_REQUIRED",
            deny_reason="public bearer authorization is required",
            resolved_at=resolved_at,
        )

    policy = PUBLIC_TOKEN_POLICIES.get(token)
    if policy is None:
        return GatewayPermissionDecision(
            allowed=False,
            status=401,
            error_type="PUBLIC_AUTH_INVALID",
            deny_reason="public bearer authorization is invalid",
            resolved_at=resolved_at,
        )

    if not policy.project_id:
        return GatewayPermissionDecision(
            allowed=False,
            status=403,
            error_type="PUBLIC_AUTHZ_DENIED",
            deny_reason="public principal is missing project scope",
            resolved_at=resolved_at,
        )

    if endpoint_required_permission not in policy.permissions:
        return GatewayPermissionDecision(
            allowed=False,
            status=403,
            error_type="PUBLIC_AUTHZ_DENIED",
            deny_reason="public principal lacks endpoint permission",
            subject_id=policy.principal_id,
            actor_id=policy.actor_id,
            project_id=policy.project_id,
            organization_id=policy.organization_id,
            token_id=policy.token_id,
            roles=policy.roles,
            permissions=policy.permissions,
            resolved_at=resolved_at,
        )

    return GatewayPermissionDecision(
        allowed=True,
        status=200,
        error_type="",
        deny_reason="",
        subject_id=policy.principal_id,
        actor_id=policy.actor_id,
        project_id=policy.project_id,
        organization_id=policy.organization_id,
        token_id=policy.token_id,
        roles=policy.roles,
        permissions=policy.permissions,
        resolved_at=resolved_at,
    )


def forwarded_headers(
    headers: Any,
    decision: GatewayPermissionDecision,
    *,
    gateway_secret: str,
    gateway_key_id: str,
    permissions_override: tuple[str, ...] | None = None,
) -> dict[str, str]:
    if not decision.allowed:
        raise ValueError("cannot forward denied gateway permission decision")
    forwarded: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in SAFE_REQUEST_HEADERS:
            forwarded[SAFE_REQUEST_HEADERS[lower]] = value

    permissions = decision.permissions if permissions_override is None else permissions_override
    forwarded.update(
        {
            "X-API2Agent-Gateway-Authorization": f"Bearer {gateway_secret}",
            "X-API2Agent-Gateway-Key-ID": gateway_key_id,
            "X-API2Agent-Principal-ID": decision.subject_id,
            "X-API2Agent-Actor-ID": decision.actor_id,
            "X-API2Agent-Project-ID": decision.project_id,
            "X-API2Agent-Organization-ID": decision.organization_id,
            "X-API2Agent-Token-ID": decision.token_id,
            "X-API2Agent-Roles": ",".join(decision.roles),
            "X-API2Agent-Permissions": ",".join(permissions),
        }
    )
    return forwarded


def assert_error_type(payload: dict, expected: str) -> None:
    actual = payload.get("error", {}).get("error_type")
    if actual != expected:
        raise RuntimeError(f"expected {expected}, got {payload}")


def assert_contract_helpers() -> None:
    incoming = {
        "Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}",
        "Content-Type": "application/json",
        "X-Request-ID": "contract-request",
        "Idempotency-Key": "contract-idempotency",
        "X-API2Agent-Gateway-Authorization": "Bearer caller-supplied-secret",
        "X-API2Agent-Principal-ID": SPOOFED_PRINCIPAL_ID,
        "X-API2Agent-Actor-ID": SPOOFED_ACTOR_ID,
        "X-API2Agent-Project-ID": SPOOFED_PROJECT_ID,
        "X-API2Agent-Organization-ID": SPOOFED_ORGANIZATION_ID,
        "X-API2Agent-Token-ID": SPOOFED_TOKEN_ID,
        "X-Actor-ID": SPOOFED_ACTOR_ID,
        "X-Project-ID": SPOOFED_PROJECT_ID,
        "Cookie": "session=caller",
        "Proxy-Authorization": "Basic caller",
    }
    decision = resolve_gateway_admin_principal(incoming, PERMISSION_REGISTRY_IMPORT_REPLACE)
    if not decision.allowed:
        raise RuntimeError(f"expected admin policy decision to allow import/replace, got {decision}")
    headers = forwarded_headers(incoming, decision, gateway_secret=GATEWAY_SECRET, gateway_key_id=GATEWAY_KEY_ID)
    if headers.get("Authorization") is not None:
        raise RuntimeError("public Authorization must be consumed locally")
    for stripped in ["X-Actor-ID", "X-Project-ID", "Cookie", "Proxy-Authorization"]:
        if stripped in headers:
            raise RuntimeError(f"expected {stripped} to be stripped")
    if headers["Content-Type"] != "application/json" or headers["X-Request-ID"] != "contract-request":
        raise RuntimeError(f"expected safe headers to be preserved, got {headers}")
    if headers["Idempotency-Key"] != "contract-idempotency":
        raise RuntimeError(f"expected Idempotency-Key to be preserved, got {headers}")
    if headers["X-API2Agent-Gateway-Authorization"] != f"Bearer {GATEWAY_SECRET}":
        raise RuntimeError(f"expected harness gateway secret injection, got {headers}")
    if headers["X-API2Agent-Principal-ID"] != HARNESS_PRINCIPAL_ID:
        raise RuntimeError(f"expected harness principal injection, got {headers}")
    if headers["X-API2Agent-Actor-ID"] != HARNESS_ACTOR_ID or headers["X-API2Agent-Project-ID"] != HARNESS_PROJECT_ID:
        raise RuntimeError(f"expected harness scope injection, got {headers}")
    readonly_decision = resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {PUBLIC_READONLY_TOKEN}"},
        PERMISSION_REGISTRY_VALIDATE,
    )
    if not readonly_decision.allowed:
        raise RuntimeError(f"expected readonly policy decision to allow validation, got {readonly_decision}")
    readonly = forwarded_headers({}, readonly_decision, gateway_secret=GATEWAY_SECRET, gateway_key_id=GATEWAY_KEY_ID)
    if readonly["X-API2Agent-Permissions"] != "control_plane.registry.validate,control_plane.distribution.read_current":
        raise RuntimeError(f"expected readonly policy to inject limited permissions, got {readonly}")
    readonly_import = resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {PUBLIC_READONLY_TOKEN}"},
        PERMISSION_REGISTRY_IMPORT_REPLACE,
    )
    if readonly_import.allowed or readonly_import.error_type != "PUBLIC_AUTHZ_DENIED":
        raise RuntimeError(f"expected readonly import/replace to fail locally, got {readonly_import}")
    if endpoint_permission("POST", "/v1/admin/distribution/publish") != PERMISSION_DISTRIBUTION_PUBLISH:
        raise RuntimeError("expected gateway route map to include distribution publish permission")
    if endpoint_permission("GET", "/v1/admin/distribution/current") != PERMISSION_DISTRIBUTION_READ_CURRENT:
        raise RuntimeError("expected gateway route map to include distribution current permission")
    if (
        endpoint_permission("POST", "/v1/admin/registry/project-partition/replace")
        != PERMISSION_REGISTRY_PROJECT_PARTITION_REPLACE
    ):
        raise RuntimeError("expected gateway route map to include project partition replace permission")


class GatewayHarnessHandler(BaseHTTPRequestHandler):
    server: "GatewayHarnessServer"

    def do_GET(self) -> None:
        self.handle_harness_request()

    def do_POST(self) -> None:
        self.handle_harness_request()

    def do_PUT(self) -> None:
        self.handle_harness_request()

    def do_DELETE(self) -> None:
        self.handle_harness_request()

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def handle_harness_request(self) -> None:
        path = self.path.split("?", 1)[0]
        method = self.command.upper()
        if path not in PATHS_WITH_METHODS:
            self.write_local_error(404, "PUBLIC_ROUTE_NOT_FOUND", "unsupported hosted admin gateway path")
            return
        if method not in PATHS_WITH_METHODS[path]:
            self.write_local_error(405, "PUBLIC_METHOD_NOT_ALLOWED", "method not allowed")
            return
        if (method, path) not in FORWARDED_PATHS:
            self.write_local_error(404, "PUBLIC_ROUTE_NOT_FOUND", "unsupported hosted admin gateway route")
            return
        if path != "/healthz":
            required_permission = endpoint_permission(method, path)
            if required_permission is None:
                self.write_local_error(404, "PUBLIC_ROUTE_NOT_FOUND", "unsupported hosted admin gateway route")
                return
            decision = resolve_gateway_admin_principal(
                self.headers,
                required_permission,
                permission_source_available=self.server.permission_source_available,
                resolved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            if not decision.allowed:
                self.write_local_error(
                    decision.status,
                    decision.error_type,
                    decision.deny_reason,
                    scope="platform" if decision.status == 503 else "caller",
                    retryable=decision.status == 503,
                )
                return
            permissions_override = self.server.force_forwarded_permissions
            headers = forwarded_headers(
                self.headers,
                decision,
                gateway_secret=self.server.gateway_secret,
                gateway_key_id=self.server.gateway_key_id,
                permissions_override=permissions_override,
            )
            self.server.permission_decisions.append(decision)
        else:
            headers = {}
            for key, value in self.headers.items():
                if key.lower() == "x-request-id":
                    headers["X-Request-ID"] = value

        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else None
        self.proxy(method, path, headers, body)

    def proxy(self, method: str, path: str, headers: dict[str, str], body: bytes | None) -> None:
        url = self.server.control_plane_base_url + path
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                self.write_proxy_response(response.status, dict(response.headers.items()), response.read())
        except urllib.error.HTTPError as exc:
            self.write_proxy_response(exc.code, dict(exc.headers.items()), exc.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            self.write_local_error(502, "GATEWAY_FORWARD_FAILED", str(exc), scope="platform", retryable=True)

    def write_proxy_response(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.send_response(status)
        for key, value in headers.items():
            if key.lower() in HOP_BY_HOP_RESPONSE_HEADERS:
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_local_error(
        self,
        status: int,
        error_type: str,
        message: str,
        *,
        scope: str = "caller",
        retryable: bool = False,
    ) -> None:
        body = json.dumps(
            {
                "error": {
                    "error_type": error_type,
                    "error_scope": scope,
                    "message": message,
                    "retryable": retryable,
                }
            },
            sort_keys=True,
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class GatewayHarnessServer(ThreadingHTTPServer):
    def __init__(self, addr: tuple[str, int], control_plane_base_url: str, gateway_secret: str, gateway_key_id: str) -> None:
        super().__init__(addr, GatewayHarnessHandler)
        self.control_plane_base_url = control_plane_base_url
        self.gateway_secret = gateway_secret
        self.gateway_key_id = gateway_key_id
        self.permission_source_available = True
        self.force_forwarded_permissions: tuple[str, ...] | None = None
        self.permission_decisions: list[GatewayPermissionDecision] = []


def start_gateway_harness(port: int, control_plane_base_url: str) -> tuple[GatewayHarnessServer, threading.Thread]:
    server = GatewayHarnessServer(("127.0.0.1", port), control_plane_base_url, GATEWAY_SECRET, GATEWAY_KEY_ID)
    thread = threading.Thread(target=server.serve_forever, name="hosted-admin-gateway-contract-harness", daemon=True)
    thread.start()
    return server, thread


def count_audit_rows(container: str) -> int:
    return int(query_postgres_scalar(container, "SELECT count(*) FROM admin_audit_events;"))


def assert_no_secret_or_public_token_leaks(report: dict) -> None:
    rendered = json.dumps(report, sort_keys=True)
    forbidden = [GATEWAY_SECRET, PUBLIC_ADMIN_TOKEN, PUBLIC_READONLY_TOKEN]
    leaked = [value for value in forbidden if value in rendered]
    if leaked:
        raise RuntimeError("report artifact contains raw secret or public token")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dogfood a local hosted admin gateway contract harness against Go Control Plane.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--keep-container", action="store_true")
    args = parser.parse_args()

    if shutil.which("podman") is None:
        raise RuntimeError("podman is required for live Postgres dogfood")

    assert_contract_helpers()

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    workdir = output.parent / "artifacts"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    container = "api2agent-pg-hosted-admin-gateway-contract-dogfood"
    pg_port = find_free_port()
    service_port = find_free_port()
    gateway_port = find_free_port()
    dsn = f"postgres://api2agent:api2agent@127.0.0.1:{pg_port}/api2agent?sslmode=disable"
    server: subprocess.Popen[str] | None = None
    gateway: GatewayHarnessServer | None = None
    gateway_thread: threading.Thread | None = None
    report: dict = {
        "dogfood": "go_control_plane_hosted_admin_gateway_contract_harness",
        "status": "started",
        "container": container,
        "dsn": f"postgres://api2agent:REDACTED@127.0.0.1:{pg_port}/api2agent?sslmode=disable",
        "service_addr": f"127.0.0.1:{service_port}",
        "gateway_addr": f"127.0.0.1:{gateway_port}",
        "admin_token_flag_used": False,
        "gateway_secret_redacted": "REDACTED",
        "public_tokens_redacted": ["REDACTED"],
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

        replacement_path = workdir / "hosted-admin-gateway-contract-replacement-registry.json"
        replacement_registry = create_replacement_registry(replacement_path)

        binary = workdir / ("api2agent-controlplane-hosted-gateway-contract.exe" if sys.platform == "win32" else "api2agent-controlplane-hosted-gateway-contract")
        run(["go", "build", "-o", str(binary), "./cmd/api2agent-controlplane"], cwd=CONTROL_PLANE)

        distribution_dir = workdir / "distribution"
        control_plane_base_url = f"http://127.0.0.1:{service_port}"
        server = start_control_plane(binary, dsn, distribution_dir, f"127.0.0.1:{service_port}")
        control_plane_health = wait_for_health(f"{control_plane_base_url}/healthz", server)

        gateway, gateway_thread = start_gateway_harness(gateway_port, control_plane_base_url)
        gateway_base_url = f"http://127.0.0.1:{gateway_port}"
        gateway_health = wait_for_health(f"{gateway_base_url}/healthz", server)

        unsupported_path_status, unsupported_path_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/unsupported",
            headers={"Authorization": "Bearer redacted-invalid-token"},
            expected_status={404},
        )
        assert_error_type(unsupported_path_response, "PUBLIC_ROUTE_NOT_FOUND")
        unsupported_method_status, unsupported_method_response, _ = request_json(
            "GET",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={"Authorization": "Bearer redacted-invalid-token"},
            expected_status={405},
        )
        assert_error_type(unsupported_method_response, "PUBLIC_METHOD_NOT_ALLOWED")

        audit_rows_before_missing_auth = count_audit_rows(container)
        missing_public_auth_status, missing_public_auth_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={
                "X-API2Agent-Gateway-Authorization": "Bearer caller-supplied-secret",
                "X-API2Agent-Principal-ID": SPOOFED_PRINCIPAL_ID,
                "X-API2Agent-Actor-ID": SPOOFED_ACTOR_ID,
                "X-API2Agent-Project-ID": SPOOFED_PROJECT_ID,
            },
            expected_status={401},
        )
        assert_error_type(missing_public_auth_response, "PUBLIC_AUTH_REQUIRED")
        audit_rows_after_missing_auth = count_audit_rows(container)
        if audit_rows_after_missing_auth != audit_rows_before_missing_auth:
            raise RuntimeError("gateway-local public auth failure must not create Control Plane audit rows")

        invalid_public_auth_status, invalid_public_auth_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={"Authorization": "Bearer redacted-invalid-token"},
            expected_status={401},
        )
        assert_error_type(invalid_public_auth_response, "PUBLIC_AUTH_INVALID")
        audit_rows_after_invalid_auth = count_audit_rows(container)
        if audit_rows_after_invalid_auth != audit_rows_before_missing_auth:
            raise RuntimeError("gateway-local invalid public auth failure must not create Control Plane audit rows")

        gateway.permission_source_available = False
        unavailable_status, unavailable_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={"Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}"},
            expected_status={503},
        )
        gateway.permission_source_available = True
        assert_error_type(unavailable_response, "PERMISSION_SOURCE_UNAVAILABLE")
        audit_rows_after_unavailable = count_audit_rows(container)
        if audit_rows_after_unavailable != audit_rows_before_missing_auth:
            raise RuntimeError("gateway-local permission source failure must not create Control Plane audit rows")

        validate_status, validate_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={
                "Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}",
                "X-Request-ID": "dogfood-gateway-contract-validate-1",
                "X-API2Agent-Gateway-Authorization": "Bearer caller-supplied-secret",
                "X-API2Agent-Gateway-Key-ID": "caller-supplied-key",
                "X-API2Agent-Principal-ID": SPOOFED_PRINCIPAL_ID,
                "X-API2Agent-Actor-ID": SPOOFED_ACTOR_ID,
                "X-API2Agent-Project-ID": SPOOFED_PROJECT_ID,
                "X-API2Agent-Organization-ID": SPOOFED_ORGANIZATION_ID,
                "X-API2Agent-Token-ID": SPOOFED_TOKEN_ID,
                "X-API2Agent-Roles": "caller-role",
                "X-API2Agent-Permissions": "caller.permission",
                "X-Actor-ID": SPOOFED_ACTOR_ID,
                "X-Project-ID": SPOOFED_PROJECT_ID,
                "X-Organization-ID": SPOOFED_ORGANIZATION_ID,
                "Cookie": "session=caller",
                "Proxy-Authorization": "Basic caller",
            },
            expected_status={200},
        )
        if validate_response.get("valid") is not True:
            raise RuntimeError(f"expected registry validation success, got {validate_response}")

        readonly_validate_status, readonly_validate_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={
                "Authorization": f"Bearer {PUBLIC_READONLY_TOKEN}",
                "X-Request-ID": "dogfood-gateway-contract-readonly-validate",
            },
            expected_status={200},
        )
        if readonly_validate_response.get("valid") is not True:
            raise RuntimeError(f"expected readonly registry validation success, got {readonly_validate_response}")
        readonly_import_status, readonly_import_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/import-replace",
            headers={
                "Authorization": f"Bearer {PUBLIC_READONLY_TOKEN}",
                "X-Request-ID": "dogfood-gateway-contract-readonly-import",
                "Idempotency-Key": "dogfood-gateway-contract-readonly-idempotency",
            },
            body={"registry": replacement_registry, "source": "dogfood_hosted_admin_gateway_contract_readonly"},
            expected_status={403},
        )
        assert_error_type(readonly_import_response, "PUBLIC_AUTHZ_DENIED")

        audit_rows_after_readonly_deny = count_audit_rows(container)
        if audit_rows_after_readonly_deny != audit_rows_before_missing_auth + 2:
            raise RuntimeError("gateway-local readonly denial must not create Control Plane audit rows")

        gateway.force_forwarded_permissions = (PERMISSION_DISTRIBUTION_READ_CURRENT,)
        insufficient_forward_status, insufficient_forward_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={"Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}"},
            expected_status={403},
        )
        gateway.force_forwarded_permissions = None
        assert_error_type(insufficient_forward_response, "AUTHZ_DENIED")
        audit_rows_after_insufficient_forward = count_audit_rows(container)
        if audit_rows_after_insufficient_forward != audit_rows_after_readonly_deny:
            raise RuntimeError("Control Plane authz denial before handler must not create audit rows")

        import_status, import_response, import_response_headers = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/import-replace",
            headers={
                "Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}",
                "X-Request-ID": "dogfood-gateway-contract-import-1",
                "Idempotency-Key": "dogfood-gateway-contract-idempotency-key",
                "X-API2Agent-Gateway-Authorization": "Bearer caller-supplied-secret",
                "X-API2Agent-Principal-ID": SPOOFED_PRINCIPAL_ID,
                "X-API2Agent-Actor-ID": SPOOFED_ACTOR_ID,
                "X-API2Agent-Project-ID": SPOOFED_PROJECT_ID,
            },
            body={"registry": replacement_registry, "source": "dogfood_hosted_admin_gateway_contract_harness"},
            expected_status={201},
        )
        if import_response.get("noop") is not False:
            raise RuntimeError(f"expected hosted gateway contract import noop=false, got {import_response}")
        if any(key.lower() == "idempotency-replayed" for key in import_response_headers):
            raise RuntimeError(f"first hosted gateway contract import should not be replayed, got {import_response_headers}")

        counts = {
            "registry_revisions": int(query_postgres_scalar(container, "SELECT count(*) FROM registry_revisions;")),
            "admin_audit_events": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_audit_events;")),
            "idempotency_records": int(query_postgres_scalar(container, "SELECT count(*) FROM admin_mutation_idempotency_records;")),
            "providers": int(query_postgres_scalar(container, "SELECT count(*) FROM providers;")),
        }
        expected_counts = {
            "registry_revisions": 2,
            "admin_audit_events": 3,
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
    metadata->>'gateway_key_id' AS gateway_key_id,
    metadata->>'local_private' AS local_private,
    metadata::text LIKE '%{SPOOFED_PRINCIPAL_ID}%' OR metadata::text LIKE '%{SPOOFED_ACTOR_ID}%' OR metadata::text LIKE '%{SPOOFED_PROJECT_ID}%' AS metadata_contains_spoofed_identity,
    metadata::text LIKE '%{GATEWAY_SECRET}%' AS metadata_contains_gateway_secret,
    metadata::text LIKE '%{PUBLIC_ADMIN_TOKEN}%' OR metadata::text LIKE '%{PUBLIC_READONLY_TOKEN}%' AS metadata_contains_public_token
  FROM admin_audit_events
) AS t;
""",
        )
        if len(audit_rows) != 3:
            raise RuntimeError(f"expected three audit rows, got {audit_rows}")
        expected_audit_identities = {
            "dogfood-gateway-contract-validate-1": (HARNESS_ACTOR_ID, HARNESS_PRINCIPAL_ID, HARNESS_TOKEN_ID_ADMIN),
            "dogfood-gateway-contract-readonly-validate": (
                READONLY_POLICY.actor_id,
                READONLY_POLICY.principal_id,
                HARNESS_TOKEN_ID_READONLY,
            ),
            "dogfood-gateway-contract-import-1": (HARNESS_ACTOR_ID, HARNESS_PRINCIPAL_ID, HARNESS_TOKEN_ID_ADMIN),
        }
        for row in audit_rows:
            expected_identity = expected_audit_identities.get(row["request_id"])
            if expected_identity is None:
                raise RuntimeError(f"unexpected audit request id, got {row}")
            expected_actor_id, expected_subject_id, expected_token_id = expected_identity
            if row["actor_id"] != expected_actor_id:
                raise RuntimeError(f"expected policy actor id in audit row, got {row}")
            if row["principal_subject_id"] != expected_subject_id or row["project_id"] != HARNESS_PROJECT_ID:
                raise RuntimeError(f"expected policy principal/project metadata, got {row}")
            if row["organization_id"] != HARNESS_ORGANIZATION_ID or row["token_id"] != expected_token_id:
                raise RuntimeError(f"expected policy org/token metadata, got {row}")
            if row["gateway_key_id"] != GATEWAY_KEY_ID:
                raise RuntimeError(f"expected harness gateway key id metadata, got {row}")
            if row["auth_method"] != "trusted_gateway" or row["local_private"] != "false":
                raise RuntimeError(f"expected trusted_gateway non-local audit metadata, got {row}")
            if row["metadata_contains_spoofed_identity"] or row["metadata_contains_gateway_secret"] or row["metadata_contains_public_token"]:
                raise RuntimeError(f"trusted/private value leaked into audit metadata: {row}")

        idempotency_rows = query_postgres_json(
            container,
            f"""
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
    noop,
    row_to_json(admin_mutation_idempotency_records)::text LIKE '%{GATEWAY_SECRET}%' AS row_contains_gateway_secret,
    row_to_json(admin_mutation_idempotency_records)::text LIKE '%{PUBLIC_ADMIN_TOKEN}%' OR row_to_json(admin_mutation_idempotency_records)::text LIKE '%{PUBLIC_READONLY_TOKEN}%' AS row_contains_public_token
  FROM admin_mutation_idempotency_records
) AS t;
""",
        )
        if len(idempotency_rows) != 1:
            raise RuntimeError(f"expected one idempotency row, got {idempotency_rows}")
        idempotency_row = idempotency_rows[0]
        if idempotency_row["project_id"] != HARNESS_PROJECT_ID or idempotency_row["actor_id"] != HARNESS_ACTOR_ID:
            raise RuntimeError(f"expected harness idempotency scope, got {idempotency_row}")
        if idempotency_row["operation"] != "registry.import_replace":
            raise RuntimeError(f"unexpected idempotency operation, got {idempotency_row}")
        if idempotency_row["response_status_code"] != 201 or idempotency_row["noop"]:
            raise RuntimeError(f"unexpected idempotency response evidence, got {idempotency_row}")
        if not idempotency_row["has_registry_revision"] or not idempotency_row["has_admin_audit_event"]:
            raise RuntimeError(f"expected idempotency evidence links, got {idempotency_row}")
        if idempotency_row["row_contains_gateway_secret"] or idempotency_row["row_contains_public_token"]:
            raise RuntimeError(f"secret or public token leaked into idempotency evidence: {idempotency_row}")

        report.update(
            {
                "status": "passed",
                "seed_stdout": seed.stdout.strip(),
                "control_plane_health": control_plane_health,
                "gateway_health": gateway_health,
                "permission_source": STATIC_POLICY_SOURCE,
                "policy_version": STATIC_POLICY_VERSION,
                "endpoint_permission_map": {
                    f"{method} {path}": permission for (method, path), permission in sorted(ENDPOINT_PERMISSIONS.items())
                },
                "unsupported_path_status": unsupported_path_status,
                "unsupported_path_error_type": unsupported_path_response.get("error", {}).get("error_type"),
                "unsupported_method_status": unsupported_method_status,
                "unsupported_method_error_type": unsupported_method_response.get("error", {}).get("error_type"),
                "missing_public_auth_status": missing_public_auth_status,
                "missing_public_auth_error_type": missing_public_auth_response.get("error", {}).get("error_type"),
                "invalid_public_auth_status": invalid_public_auth_status,
                "invalid_public_auth_error_type": invalid_public_auth_response.get("error", {}).get("error_type"),
                "permission_source_unavailable_status": unavailable_status,
                "permission_source_unavailable_error_type": unavailable_response.get("error", {}).get("error_type"),
                "audit_rows_before_missing_public_auth": audit_rows_before_missing_auth,
                "audit_rows_after_missing_public_auth": audit_rows_after_missing_auth,
                "audit_rows_after_invalid_public_auth": audit_rows_after_invalid_auth,
                "audit_rows_after_permission_source_unavailable": audit_rows_after_unavailable,
                "validate_status": validate_status,
                "validate_response": {
                    "valid": validate_response.get("valid"),
                    "registry_store": validate_response.get("registry_store"),
                    "registry_fingerprint": validate_response.get("registry_fingerprint"),
                },
                "readonly_validate_status": readonly_validate_status,
                "readonly_validate_response": {
                    "valid": readonly_validate_response.get("valid"),
                    "registry_store": readonly_validate_response.get("registry_store"),
                    "registry_fingerprint": readonly_validate_response.get("registry_fingerprint"),
                },
                "readonly_import_status": readonly_import_status,
                "readonly_import_error_type": readonly_import_response.get("error", {}).get("error_type"),
                "audit_rows_after_readonly_deny": audit_rows_after_readonly_deny,
                "insufficient_forward_status": insufficient_forward_status,
                "insufficient_forward_error_type": insufficient_forward_response.get("error", {}).get("error_type"),
                "audit_rows_after_insufficient_forward": audit_rows_after_insufficient_forward,
                "import_status": import_status,
                "import_response": import_response,
                "permission_decisions": [
                    {
                        "allowed": decision.allowed,
                        "subject_id": decision.subject_id,
                        "actor_id": decision.actor_id,
                        "project_id": decision.project_id,
                        "organization_id": decision.organization_id,
                        "token_id": decision.token_id,
                        "roles": list(decision.roles),
                        "permissions": list(decision.permissions),
                        "policy_source": decision.policy_source,
                        "policy_version": decision.policy_version,
                        "permission_source": decision.permission_source,
                        "resolved_at": decision.resolved_at,
                    }
                    for decision in gateway.permission_decisions
                ],
                "audit_counts": counts,
                "audit_rows": audit_rows,
                "idempotency_rows": idempotency_rows,
                "replacement_registry": str(replacement_path),
            }
        )
        assert_no_secret_or_public_token_leaks(report)
        return 0
    except Exception as exc:
        report.update({"status": "failed", "error": str(exc)})
        return 1
    finally:
        if gateway is not None:
            gateway.shutdown()
            gateway.server_close()
        if gateway_thread is not None:
            gateway_thread.join(timeout=5)
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
