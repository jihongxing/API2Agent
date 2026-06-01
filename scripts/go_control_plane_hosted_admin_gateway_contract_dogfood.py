from __future__ import annotations

import argparse
import hashlib
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
from typing import Any, Protocol


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE = REPO_ROOT / "services" / "control-plane"
SCHEMA = CONTROL_PLANE / "schema" / "postgres" / "001_persistent_registry_store.sql"
REGISTRY = CONTROL_PLANE / "testdata" / "registry" / "network.public_ip.get.json"

GATEWAY_SECRET = "dogfood-trusted-gateway-secret-contract"
GATEWAY_KEY_ID = "dogfood-gateway-key-contract"
PUBLIC_ADMIN_TOKEN = "dogfood-public-admin-token"
PUBLIC_READONLY_TOKEN = "dogfood-public-readonly-token"
PUBLIC_NO_MEMBERSHIP_TOKEN = "dogfood-public-no-membership-token"
PUBLIC_SUSPENDED_TOKEN = "dogfood-public-suspended-token"
PUBLIC_REVOKED_TOKEN = "dogfood-public-revoked-token"
HOSTED_PERMISSION_STORE_SOURCE = "hosted-permission-store-fixture"
HOSTED_POLICY_VERSION = "hosted-policy-v1"
HOSTED_POLICY_FINGERPRINT = "sha256:hosted-permission-store-fixture-v1"
STATIC_POLICY_SOURCE = HOSTED_PERMISSION_STORE_SOURCE
STATIC_POLICY_VERSION = HOSTED_POLICY_VERSION

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
class PublicPrincipal:
    public_principal_id: str
    external_subject_ref: str
    subject_id: str
    token_id: str


@dataclass(frozen=True)
class HostedSubject:
    subject_id: str
    status: str = "active"


@dataclass(frozen=True)
class HostedProjectMembership:
    subject_id: str
    actor_id: str
    project_id: str
    organization_id: str
    status: str = "active"


@dataclass(frozen=True)
class HostedRoleBinding:
    subject_id: str
    project_id: str
    role: str


@dataclass(frozen=True)
class HostedPermissionGrant:
    role: str
    permission: str


@dataclass(frozen=True)
class ResolvedHostedPrincipal:
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
    required_permission: str = ""
    policy_source: str = HOSTED_PERMISSION_STORE_SOURCE
    policy_version: str = HOSTED_POLICY_VERSION
    policy_fingerprint: str = HOSTED_POLICY_FINGERPRINT
    decision_id: str = ""
    permission_source: str = HOSTED_PERMISSION_STORE_SOURCE
    resolved_at: str = ""


ADMIN_POLICY = ResolvedHostedPrincipal(
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
READONLY_POLICY = ResolvedHostedPrincipal(
    principal_id="gateway-harness-readonly-principal",
    actor_id="gateway-harness-readonly-actor",
    project_id=HARNESS_PROJECT_ID,
    organization_id=HARNESS_ORGANIZATION_ID,
    token_id=HARNESS_TOKEN_ID_READONLY,
    roles=("control-plane-readonly", "dogfood"),
    permissions=(PERMISSION_REGISTRY_VALIDATE, PERMISSION_DISTRIBUTION_READ_CURRENT),
)
NO_MEMBERSHIP_SUBJECT_ID = "gateway-harness-no-membership-principal"
SUSPENDED_PRINCIPAL_ID = "gateway-harness-suspended-principal"
SUSPENDED_ACTOR_ID = "gateway-harness-suspended-actor"
REVOKED_PRINCIPAL_ID = "gateway-harness-revoked-principal"
REVOKED_ACTOR_ID = "gateway-harness-revoked-actor"

PUBLIC_PRINCIPALS = {
    PUBLIC_ADMIN_TOKEN: PublicPrincipal(
        public_principal_id="public-admin",
        external_subject_ref="dogfood/idp/admin",
        subject_id=HARNESS_PRINCIPAL_ID,
        token_id=HARNESS_TOKEN_ID_ADMIN,
    ),
    PUBLIC_READONLY_TOKEN: PublicPrincipal(
        public_principal_id="public-readonly",
        external_subject_ref="dogfood/idp/readonly",
        subject_id=READONLY_POLICY.principal_id,
        token_id=HARNESS_TOKEN_ID_READONLY,
    ),
    PUBLIC_NO_MEMBERSHIP_TOKEN: PublicPrincipal(
        public_principal_id="public-no-membership",
        external_subject_ref="dogfood/idp/no-membership",
        subject_id=NO_MEMBERSHIP_SUBJECT_ID,
        token_id="gateway-harness-token-no-membership",
    ),
    PUBLIC_SUSPENDED_TOKEN: PublicPrincipal(
        public_principal_id="public-suspended",
        external_subject_ref="dogfood/idp/suspended",
        subject_id=SUSPENDED_PRINCIPAL_ID,
        token_id="gateway-harness-token-suspended",
    ),
    PUBLIC_REVOKED_TOKEN: PublicPrincipal(
        public_principal_id="public-revoked",
        external_subject_ref="dogfood/idp/revoked",
        subject_id=REVOKED_PRINCIPAL_ID,
        token_id="gateway-harness-token-revoked",
    ),
}


@dataclass(frozen=True)
class HostedPermissionStore:
    subjects: tuple[HostedSubject, ...]
    memberships: tuple[HostedProjectMembership, ...]
    role_bindings: tuple[HostedRoleBinding, ...]
    permission_grants: tuple[HostedPermissionGrant, ...]
    policy_source: str = HOSTED_PERMISSION_STORE_SOURCE
    policy_version: str = HOSTED_POLICY_VERSION
    policy_fingerprint: str = HOSTED_POLICY_FINGERPRINT
    stale_policy: bool = False

    def with_stale_policy(self) -> "HostedPermissionStore":
        return HostedPermissionStore(
            subjects=self.subjects,
            memberships=self.memberships,
            role_bindings=self.role_bindings,
            permission_grants=self.permission_grants,
            policy_source=self.policy_source,
            policy_version=self.policy_version,
            policy_fingerprint=self.policy_fingerprint,
            stale_policy=True,
        )

    def without_permission(self, role: str, permission: str) -> "HostedPermissionStore":
        grants = tuple(
            grant for grant in self.permission_grants if not (grant.role == role and grant.permission == permission)
        )
        return HostedPermissionStore(
            subjects=self.subjects,
            memberships=self.memberships,
            role_bindings=self.role_bindings,
            permission_grants=grants,
            policy_source=self.policy_source,
            policy_version=f"{self.policy_version}-revoked",
            policy_fingerprint=f"sha256:{hashlib.sha256(repr(grants).encode('utf-8')).hexdigest()[:16]}",
        )

    def subject(self, subject_id: str) -> HostedSubject | None:
        matches = [subject for subject in self.subjects if subject.subject_id == subject_id]
        if len(matches) != 1:
            return None
        return matches[0]

    def membership(self, subject_id: str, project_id: str) -> HostedProjectMembership | None:
        matches = [
            membership
            for membership in self.memberships
            if membership.subject_id == subject_id and membership.project_id == project_id
        ]
        if len(matches) != 1:
            return None
        return matches[0]

    def roles_for(self, subject_id: str, project_id: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                binding.role
                for binding in self.role_bindings
                if binding.subject_id == subject_id and binding.project_id == project_id
            )
        )

    def permissions_for(self, roles: tuple[str, ...]) -> tuple[str, ...]:
        permissions = sorted({grant.permission for grant in self.permission_grants if grant.role in roles})
        return tuple(permissions)


def default_permission_store() -> HostedPermissionStore:
    return HostedPermissionStore(
        subjects=(
            HostedSubject(HARNESS_PRINCIPAL_ID),
            HostedSubject(READONLY_POLICY.principal_id),
            HostedSubject(NO_MEMBERSHIP_SUBJECT_ID),
            HostedSubject(SUSPENDED_PRINCIPAL_ID),
            HostedSubject(REVOKED_PRINCIPAL_ID),
        ),
        memberships=(
            HostedProjectMembership(
                subject_id=HARNESS_PRINCIPAL_ID,
                actor_id=HARNESS_ACTOR_ID,
                project_id=HARNESS_PROJECT_ID,
                organization_id=HARNESS_ORGANIZATION_ID,
            ),
            HostedProjectMembership(
                subject_id=READONLY_POLICY.principal_id,
                actor_id=READONLY_POLICY.actor_id,
                project_id=HARNESS_PROJECT_ID,
                organization_id=HARNESS_ORGANIZATION_ID,
            ),
            HostedProjectMembership(
                subject_id=SUSPENDED_PRINCIPAL_ID,
                actor_id=SUSPENDED_ACTOR_ID,
                project_id=HARNESS_PROJECT_ID,
                organization_id=HARNESS_ORGANIZATION_ID,
                status="suspended",
            ),
            HostedProjectMembership(
                subject_id=REVOKED_PRINCIPAL_ID,
                actor_id=REVOKED_ACTOR_ID,
                project_id=HARNESS_PROJECT_ID,
                organization_id=HARNESS_ORGANIZATION_ID,
            ),
        ),
        role_bindings=(
            HostedRoleBinding(HARNESS_PRINCIPAL_ID, HARNESS_PROJECT_ID, "project_admin"),
            HostedRoleBinding(READONLY_POLICY.principal_id, HARNESS_PROJECT_ID, "project_readonly"),
            HostedRoleBinding(SUSPENDED_PRINCIPAL_ID, HARNESS_PROJECT_ID, "project_admin"),
            HostedRoleBinding(REVOKED_PRINCIPAL_ID, HARNESS_PROJECT_ID, "project_revoked"),
        ),
        permission_grants=(
            HostedPermissionGrant("project_admin", PERMISSION_REGISTRY_VALIDATE),
            HostedPermissionGrant("project_admin", PERMISSION_REGISTRY_IMPORT_REPLACE),
            HostedPermissionGrant("project_admin", PERMISSION_REGISTRY_PROJECT_PARTITION_REPLACE),
            HostedPermissionGrant("project_admin", PERMISSION_SNAPSHOT_EXPORT_ARTIFACT),
            HostedPermissionGrant("project_admin", PERMISSION_DISTRIBUTION_PUBLISH),
            HostedPermissionGrant("project_admin", PERMISSION_DISTRIBUTION_READ_CURRENT),
            HostedPermissionGrant("project_readonly", PERMISSION_REGISTRY_VALIDATE),
            HostedPermissionGrant("project_readonly", PERMISSION_DISTRIBUTION_READ_CURRENT),
            HostedPermissionGrant("project_revoked", PERMISSION_REGISTRY_VALIDATE),
        ),
    )


DEFAULT_PERMISSION_STORE = default_permission_store()


class GatewayPermissionSource(Protocol):
    policy_source: str
    policy_version: str
    policy_fingerprint: str

    def resolve(
        self,
        public_principal: PublicPrincipal,
        endpoint_required_permission: str,
        *,
        project_context: str,
        resolved_at: str,
    ) -> GatewayPermissionDecision:
        ...


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


def execute_postgres(container: str, sql: str) -> None:
    run(
        [
            "podman",
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            "api2agent",
            "-d",
            "api2agent",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input_text=sql,
    )


def create_replacement_registry(path: Path) -> dict:
    data = create_harness_project_registry(path)
    provider = data["providers"][0]
    provider["id"] = "httpbin_public_ip_v1"
    provider["provider_id"] = "httpbin"
    provider["metadata"]["base_url"] = "https://httpbin.org"
    data["credential_metadata"][0]["provider_id"] = "httpbin"
    data["snapshot"]["version"] = "snapshot_hosted_admin_gateway_contract_harness_v1"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def create_harness_project_registry(path: Path) -> dict:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    data["projects"][0]["id"] = HARNESS_PROJECT_ID
    data["projects"][0]["name"] = "Gateway Harness Project"
    data["api_keys"][0]["project_id"] = HARNESS_PROJECT_ID
    data["credential_metadata"][0]["owner_id"] = HARNESS_PROJECT_ID
    data["snapshot"]["version"] = "snapshot_service_api_v1"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def create_project_partition_registry(path: Path) -> dict:
    data = create_harness_project_registry(path)
    data["api_keys"][0]["key_prefix"] = "harness_"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def create_cross_project_partition_registry(path: Path) -> dict:
    data = create_project_partition_registry(path)
    data["projects"].append(
        {
            "id": "other-project",
            "name": "Other Project",
            "status": "active",
            "default_mode": "proxy",
        }
    )
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def hosted_permission_seed_sql() -> str:
    grants = [
        ("project_admin", PERMISSION_REGISTRY_VALIDATE, "active"),
        ("project_admin", PERMISSION_REGISTRY_IMPORT_REPLACE, "active"),
        ("project_admin", PERMISSION_REGISTRY_PROJECT_PARTITION_REPLACE, "active"),
        ("project_admin", PERMISSION_SNAPSHOT_EXPORT_ARTIFACT, "active"),
        ("project_admin", PERMISSION_DISTRIBUTION_PUBLISH, "active"),
        ("project_admin", PERMISSION_DISTRIBUTION_READ_CURRENT, "active"),
        ("project_readonly", PERMISSION_REGISTRY_VALIDATE, "active"),
        ("project_readonly", PERMISSION_DISTRIBUTION_READ_CURRENT, "active"),
        ("project_revoked", PERMISSION_REGISTRY_VALIDATE, "revoked"),
    ]
    grant_values = ",\n".join(
        f"('{role}', '{permission}', 'project', '{status}', '{{}}'::jsonb)" for role, permission, status in grants
    )
    return f"""
INSERT INTO hosted_subjects (id, external_subject_ref, display_name, status)
VALUES
  ('{HARNESS_PRINCIPAL_ID}', 'dogfood/idp/admin', 'Dogfood Admin', 'active'),
  ('{READONLY_POLICY.principal_id}', 'dogfood/idp/readonly', 'Dogfood Readonly', 'active'),
  ('{NO_MEMBERSHIP_SUBJECT_ID}', 'dogfood/idp/no-membership', 'Dogfood No Membership', 'active'),
  ('{SUSPENDED_PRINCIPAL_ID}', 'dogfood/idp/suspended', 'Dogfood Suspended', 'active'),
  ('{REVOKED_PRINCIPAL_ID}', 'dogfood/idp/revoked', 'Dogfood Revoked', 'active');

INSERT INTO hosted_project_memberships (subject_id, actor_id, project_id, organization_id, status)
VALUES
  ('{HARNESS_PRINCIPAL_ID}', '{HARNESS_ACTOR_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'active'),
  ('{READONLY_POLICY.principal_id}', '{READONLY_POLICY.actor_id}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'active'),
  ('{SUSPENDED_PRINCIPAL_ID}', '{SUSPENDED_ACTOR_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'suspended'),
  ('{REVOKED_PRINCIPAL_ID}', '{REVOKED_ACTOR_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'active');

INSERT INTO hosted_roles (id, name, scope_type, public_assignable, status)
VALUES
  ('project_admin', 'Project Admin', 'project', false, 'active'),
  ('project_readonly', 'Project Readonly', 'project', false, 'active'),
  ('project_revoked', 'Project Revoked', 'project', false, 'active'),
  ('dogfood', 'Dogfood Evidence Role', 'project', false, 'active');

INSERT INTO hosted_role_bindings (subject_id, project_id, organization_id, role_id, status, source)
VALUES
  ('{HARNESS_PRINCIPAL_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'project_admin', 'active', 'seed'),
  ('{HARNESS_PRINCIPAL_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'dogfood', 'active', 'seed'),
  ('{READONLY_POLICY.principal_id}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'project_readonly', 'active', 'seed'),
  ('{READONLY_POLICY.principal_id}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'dogfood', 'active', 'seed'),
  ('{SUSPENDED_PRINCIPAL_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'project_admin', 'active', 'seed'),
  ('{REVOKED_PRINCIPAL_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'project_revoked', 'active', 'seed');

INSERT INTO hosted_permission_grants (role_id, permission, scope_type, status, metadata)
VALUES
{grant_values};

INSERT INTO hosted_policy_versions (policy_source, policy_version, policy_fingerprint, status, activated_at)
VALUES ('{HOSTED_PERMISSION_STORE_SOURCE}', '{HOSTED_POLICY_VERSION}', '{HOSTED_POLICY_FINGERPRINT}', 'active', now());
"""


def seed_hosted_permission_store(container: str) -> None:
    execute_postgres(container, hosted_permission_seed_sql())


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


def permission_decision_id(
    *,
    subject_id: str,
    project_id: str,
    required_permission: str,
    policy_version: str,
    resolved_at: str,
) -> str:
    source = "|".join([subject_id, project_id, required_permission, policy_version, resolved_at])
    return f"decision-{hashlib.sha256(source.encode('utf-8')).hexdigest()[:16]}"


def denied_permission_decision(
    *,
    status: int,
    error_type: str,
    deny_reason: str,
    required_permission: str,
    resolved_at: str,
    store: HostedPermissionStore = DEFAULT_PERMISSION_STORE,
    subject_id: str = "",
    actor_id: str = "",
    project_id: str = "",
    organization_id: str = "",
    token_id: str = "",
    roles: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
) -> GatewayPermissionDecision:
    return GatewayPermissionDecision(
        allowed=False,
        status=status,
        error_type=error_type,
        deny_reason=deny_reason,
        subject_id=subject_id,
        actor_id=actor_id,
        project_id=project_id,
        organization_id=organization_id,
        token_id=token_id,
        roles=roles,
        permissions=permissions,
        required_permission=required_permission,
        policy_source=store.policy_source,
        policy_version=store.policy_version,
        policy_fingerprint=store.policy_fingerprint,
        decision_id=permission_decision_id(
            subject_id=subject_id,
            project_id=project_id,
            required_permission=required_permission,
            policy_version=store.policy_version,
            resolved_at=resolved_at,
        ),
        permission_source=store.policy_source,
        resolved_at=resolved_at,
    )


class StaticFixturePermissionSource:
    def __init__(self, store: HostedPermissionStore = DEFAULT_PERMISSION_STORE, *, available: bool = True) -> None:
        self.store = store
        self.available = available

    @property
    def policy_source(self) -> str:
        return self.store.policy_source

    @property
    def policy_version(self) -> str:
        return self.store.policy_version

    @property
    def policy_fingerprint(self) -> str:
        return self.store.policy_fingerprint

    def resolve(
        self,
        public_principal: PublicPrincipal,
        endpoint_required_permission: str,
        *,
        project_context: str,
        resolved_at: str,
    ) -> GatewayPermissionDecision:
        if not self.available:
            return denied_permission_decision(
                status=503,
                error_type="PERMISSION_SOURCE_UNAVAILABLE",
                deny_reason="hosted permission store is unavailable",
                required_permission=endpoint_required_permission,
                resolved_at=resolved_at,
                store=self.store,
            )

        if self.store.stale_policy:
            return denied_permission_decision(
                status=503,
                error_type="PERMISSION_SOURCE_UNAVAILABLE",
                deny_reason="hosted permission policy view is stale or ambiguous",
                required_permission=endpoint_required_permission,
                resolved_at=resolved_at,
                store=self.store,
                subject_id=public_principal.subject_id,
                token_id=public_principal.token_id,
            )

        subject = self.store.subject(public_principal.subject_id)
        if subject is None or subject.status != "active":
            return denied_permission_decision(
                status=403,
                error_type="PUBLIC_AUTHZ_DENIED",
                deny_reason="public principal subject is not active",
                required_permission=endpoint_required_permission,
                resolved_at=resolved_at,
                store=self.store,
                subject_id=public_principal.subject_id,
                token_id=public_principal.token_id,
            )

        membership = self.store.membership(public_principal.subject_id, project_context)
        if membership is None:
            return denied_permission_decision(
                status=403,
                error_type="PUBLIC_AUTHZ_DENIED",
                deny_reason="public principal is missing project membership",
                required_permission=endpoint_required_permission,
                resolved_at=resolved_at,
                store=self.store,
                subject_id=public_principal.subject_id,
                token_id=public_principal.token_id,
            )

        if membership.status != "active":
            return denied_permission_decision(
                status=403,
                error_type="PUBLIC_AUTHZ_DENIED",
                deny_reason="public principal project membership is inactive",
                required_permission=endpoint_required_permission,
                resolved_at=resolved_at,
                store=self.store,
                subject_id=public_principal.subject_id,
                actor_id=membership.actor_id,
                project_id=membership.project_id,
                organization_id=membership.organization_id,
                token_id=public_principal.token_id,
            )

        roles = self.store.roles_for(public_principal.subject_id, membership.project_id)
        permissions = self.store.permissions_for(roles)
        if endpoint_required_permission not in permissions:
            return denied_permission_decision(
                status=403,
                error_type="PUBLIC_AUTHZ_DENIED",
                deny_reason="public principal lacks endpoint permission",
                required_permission=endpoint_required_permission,
                resolved_at=resolved_at,
                store=self.store,
                subject_id=public_principal.subject_id,
                actor_id=membership.actor_id,
                project_id=membership.project_id,
                organization_id=membership.organization_id,
                token_id=public_principal.token_id,
                roles=roles,
                permissions=permissions,
            )

        return GatewayPermissionDecision(
            allowed=True,
            status=200,
            error_type="",
            deny_reason="",
            subject_id=public_principal.subject_id,
            actor_id=membership.actor_id,
            project_id=membership.project_id,
            organization_id=membership.organization_id,
            token_id=public_principal.token_id,
            roles=roles,
            permissions=permissions,
            required_permission=endpoint_required_permission,
            policy_source=self.store.policy_source,
            policy_version=self.store.policy_version,
            policy_fingerprint=self.store.policy_fingerprint,
            decision_id=permission_decision_id(
                subject_id=public_principal.subject_id,
                project_id=membership.project_id,
                required_permission=endpoint_required_permission,
                policy_version=self.store.policy_version,
                resolved_at=resolved_at,
            ),
            permission_source=self.store.policy_source,
            resolved_at=resolved_at,
        )


class HostedReadModelPermissionSource:
    def __init__(
        self,
        *,
        postgres_dsn: str,
        lookup_binary: Path,
        policy_source: str = HOSTED_PERMISSION_STORE_SOURCE,
        policy_version: str = HOSTED_POLICY_VERSION,
        policy_fingerprint: str = HOSTED_POLICY_FINGERPRINT,
    ) -> None:
        self.postgres_dsn = postgres_dsn
        self.lookup_binary = lookup_binary
        self.policy_source = policy_source
        self.policy_version = policy_version
        self.policy_fingerprint = policy_fingerprint

    def resolve(
        self,
        public_principal: PublicPrincipal,
        endpoint_required_permission: str,
        *,
        project_context: str,
        resolved_at: str,
    ) -> GatewayPermissionDecision:
        try:
            result = run(
                [
                    str(self.lookup_binary),
                    "--postgres-dsn",
                    self.postgres_dsn,
                    "--public-principal-id",
                    public_principal.public_principal_id,
                    "--external-subject-ref",
                    public_principal.external_subject_ref,
                    "--project-id",
                    project_context,
                    "--token-id",
                    public_principal.token_id,
                    "--required-permission",
                    endpoint_required_permission,
                    "--resolved-at",
                    resolved_at,
                ],
                cwd=CONTROL_PLANE,
            )
            payload = json.loads(result.stdout)
        except Exception:
            return denied_permission_decision(
                status=503,
                error_type="PERMISSION_SOURCE_UNAVAILABLE",
                deny_reason="hosted permission read model is unavailable",
                required_permission=endpoint_required_permission,
                resolved_at=resolved_at,
                store=HostedPermissionStore(
                    subjects=(),
                    memberships=(),
                    role_bindings=(),
                    permission_grants=(),
                    policy_source=self.policy_source,
                    policy_version=self.policy_version,
                    policy_fingerprint=self.policy_fingerprint,
                ),
            )

        return GatewayPermissionDecision(
            allowed=bool(payload.get("allowed")),
            status=int(payload.get("status", 503)),
            error_type=str(payload.get("error_type", "")),
            deny_reason=str(payload.get("deny_reason", "")),
            subject_id=str(payload.get("subject_id", "")),
            actor_id=str(payload.get("actor_id", "")),
            project_id=str(payload.get("project_id", "")),
            organization_id=str(payload.get("organization_id", "")),
            token_id=str(payload.get("token_id", "")),
            roles=tuple(payload.get("roles") or ()),
            permissions=tuple(payload.get("permissions") or ()),
            required_permission=str(payload.get("required_permission", endpoint_required_permission)),
            policy_source=str(payload.get("policy_source", self.policy_source)),
            policy_version=str(payload.get("policy_version", self.policy_version)),
            policy_fingerprint=str(payload.get("policy_fingerprint", self.policy_fingerprint)),
            decision_id=str(payload.get("decision_id", "")),
            permission_source=str(payload.get("permission_source", payload.get("policy_source", self.policy_source))),
            resolved_at=str(payload.get("resolved_at", resolved_at)),
        )


def resolve_gateway_admin_principal(
    headers: Any,
    endpoint_required_permission: str,
    *,
    permission_source_available: bool = True,
    permission_store: HostedPermissionStore = DEFAULT_PERMISSION_STORE,
    permission_source: GatewayPermissionSource | None = None,
    project_context: str = HARNESS_PROJECT_ID,
    resolved_at: str = "2026-06-01T00:00:00Z",
) -> GatewayPermissionDecision:
    token = bearer_token(headers.get("Authorization", ""))
    if token is None:
        return denied_permission_decision(
            status=401,
            error_type="PUBLIC_AUTH_REQUIRED",
            deny_reason="public bearer authorization is required",
            required_permission=endpoint_required_permission,
            resolved_at=resolved_at,
            store=permission_store,
        )

    public_principal = PUBLIC_PRINCIPALS.get(token)
    if public_principal is None:
        return denied_permission_decision(
            status=401,
            error_type="PUBLIC_AUTH_INVALID",
            deny_reason="public bearer authorization is invalid",
            required_permission=endpoint_required_permission,
            resolved_at=resolved_at,
            store=permission_store,
        )

    if not permission_source_available:
        return denied_permission_decision(
            status=503,
            error_type="PERMISSION_SOURCE_UNAVAILABLE",
            deny_reason="hosted permission store is unavailable",
            required_permission=endpoint_required_permission,
            resolved_at=resolved_at,
            store=permission_store,
        )

    source = permission_source or StaticFixturePermissionSource(
        permission_store,
        available=True,
    )
    return source.resolve(
        public_principal,
        endpoint_required_permission,
        project_context=project_context,
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
            "X-API2Agent-Permission-Source": decision.policy_source,
            "X-API2Agent-Policy-Version": decision.policy_version,
            "X-API2Agent-Policy-Fingerprint": decision.policy_fingerprint,
            "X-API2Agent-Permission-Decision-ID": decision.decision_id,
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
    if readonly["X-API2Agent-Permissions"] != "control_plane.distribution.read_current,control_plane.registry.validate":
        raise RuntimeError(f"expected readonly policy to inject limited permissions, got {readonly}")
    if readonly["X-API2Agent-Policy-Version"] != HOSTED_POLICY_VERSION:
        raise RuntimeError(f"expected hosted policy version evidence, got {readonly}")
    if readonly["X-API2Agent-Permission-Decision-ID"] == "":
        raise RuntimeError(f"expected hosted permission decision id evidence, got {readonly}")
    readonly_import = resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {PUBLIC_READONLY_TOKEN}"},
        PERMISSION_REGISTRY_IMPORT_REPLACE,
    )
    if readonly_import.allowed or readonly_import.error_type != "PUBLIC_AUTHZ_DENIED":
        raise RuntimeError(f"expected readonly import/replace to fail locally, got {readonly_import}")
    no_membership = resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {PUBLIC_NO_MEMBERSHIP_TOKEN}"},
        PERMISSION_REGISTRY_VALIDATE,
    )
    if no_membership.allowed or no_membership.error_type != "PUBLIC_AUTHZ_DENIED":
        raise RuntimeError(f"expected no-membership principal to fail locally, got {no_membership}")
    suspended = resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {PUBLIC_SUSPENDED_TOKEN}"},
        PERMISSION_REGISTRY_VALIDATE,
    )
    if suspended.allowed or suspended.error_type != "PUBLIC_AUTHZ_DENIED":
        raise RuntimeError(f"expected suspended membership to fail locally, got {suspended}")
    revoked = resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {PUBLIC_REVOKED_TOKEN}"},
        PERMISSION_REGISTRY_VALIDATE,
        permission_store=DEFAULT_PERMISSION_STORE.without_permission("project_revoked", PERMISSION_REGISTRY_VALIDATE),
    )
    if revoked.allowed or revoked.error_type != "PUBLIC_AUTHZ_DENIED":
        raise RuntimeError(f"expected revoked permission to fail locally, got {revoked}")
    stale = resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}"},
        PERMISSION_REGISTRY_VALIDATE,
        permission_store=DEFAULT_PERMISSION_STORE.with_stale_policy(),
    )
    if stale.allowed or stale.status != 503 or stale.error_type != "PERMISSION_SOURCE_UNAVAILABLE":
        raise RuntimeError(f"expected stale policy to fail closed, got {stale}")
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
                permission_store=self.server.permission_store,
                permission_source=self.server.permission_source,
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
        self.permission_store = DEFAULT_PERMISSION_STORE
        self.permission_source: GatewayPermissionSource | None = None
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
    forbidden = [
        GATEWAY_SECRET,
        PUBLIC_ADMIN_TOKEN,
        PUBLIC_READONLY_TOKEN,
        PUBLIC_NO_MEMBERSHIP_TOKEN,
        PUBLIC_SUSPENDED_TOKEN,
        PUBLIC_REVOKED_TOKEN,
    ]
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
        seed_registry_path = workdir / "hosted-admin-gateway-contract-seed-registry.json"
        create_harness_project_registry(seed_registry_path)
        seed = run(
            [
                "go",
                "run",
                "./cmd/api2agent-controlplane",
                "seed-postgres",
                "--registry",
                str(seed_registry_path),
                "--postgres-dsn",
                dsn,
            ],
            cwd=CONTROL_PLANE,
        )
        seed_hosted_permission_store(container)

        replacement_path = workdir / "hosted-admin-gateway-contract-replacement-registry.json"
        replacement_registry = create_replacement_registry(replacement_path)
        partition_path = workdir / "hosted-admin-gateway-contract-project-partition-registry.json"
        partition_registry = create_project_partition_registry(partition_path)
        cross_project_partition_path = workdir / "hosted-admin-gateway-contract-cross-project-partition-registry.json"
        cross_project_partition_registry = create_cross_project_partition_registry(cross_project_partition_path)

        binary = workdir / ("api2agent-controlplane-hosted-gateway-contract.exe" if sys.platform == "win32" else "api2agent-controlplane-hosted-gateway-contract")
        run(["go", "build", "-o", str(binary), "./cmd/api2agent-controlplane"], cwd=CONTROL_PLANE)
        lookup_binary = workdir / ("api2agent-hosted-permission-gateway-lookup.exe" if sys.platform == "win32" else "api2agent-hosted-permission-gateway-lookup")
        run(["go", "build", "-o", str(lookup_binary), "./cmd/api2agent-hosted-permission-gateway-lookup"], cwd=CONTROL_PLANE)

        distribution_dir = workdir / "distribution"
        control_plane_base_url = f"http://127.0.0.1:{service_port}"
        server = start_control_plane(binary, dsn, distribution_dir, f"127.0.0.1:{service_port}")
        control_plane_health = wait_for_health(f"{control_plane_base_url}/healthz", server)

        gateway, gateway_thread = start_gateway_harness(gateway_port, control_plane_base_url)
        gateway.permission_source = HostedReadModelPermissionSource(postgres_dsn=dsn, lookup_binary=lookup_binary)
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

        no_membership_status, no_membership_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={"Authorization": f"Bearer {PUBLIC_NO_MEMBERSHIP_TOKEN}"},
            expected_status={403},
        )
        assert_error_type(no_membership_response, "PUBLIC_AUTHZ_DENIED")
        audit_rows_after_no_membership = count_audit_rows(container)
        if audit_rows_after_no_membership != audit_rows_before_missing_auth:
            raise RuntimeError("gateway-local missing membership denial must not create Control Plane audit rows")

        suspended_membership_status, suspended_membership_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={"Authorization": f"Bearer {PUBLIC_SUSPENDED_TOKEN}"},
            expected_status={403},
        )
        assert_error_type(suspended_membership_response, "PUBLIC_AUTHZ_DENIED")
        audit_rows_after_suspended_membership = count_audit_rows(container)
        if audit_rows_after_suspended_membership != audit_rows_before_missing_auth:
            raise RuntimeError("gateway-local suspended membership denial must not create Control Plane audit rows")

        gateway.permission_store = DEFAULT_PERMISSION_STORE.without_permission(
            "project_revoked",
            PERMISSION_REGISTRY_VALIDATE,
        )
        execute_postgres(
            container,
            "UPDATE hosted_permission_grants SET status = 'revoked' WHERE role_id = 'project_revoked' AND permission = 'control_plane.registry.validate';",
        )
        revoked_permission_status, revoked_permission_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={"Authorization": f"Bearer {PUBLIC_REVOKED_TOKEN}"},
            expected_status={403},
        )
        gateway.permission_store = DEFAULT_PERMISSION_STORE
        assert_error_type(revoked_permission_response, "PUBLIC_AUTHZ_DENIED")
        audit_rows_after_revoked_permission = count_audit_rows(container)
        if audit_rows_after_revoked_permission != audit_rows_before_missing_auth:
            raise RuntimeError("gateway-local revoked permission denial must not create Control Plane audit rows")

        gateway.permission_store = DEFAULT_PERMISSION_STORE.with_stale_policy()
        execute_postgres(container, "UPDATE hosted_policy_versions SET status = 'superseded' WHERE status = 'active';")
        stale_policy_status, stale_policy_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={"Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}"},
            expected_status={503},
        )
        gateway.permission_store = DEFAULT_PERMISSION_STORE
        execute_postgres(
            container,
            f"UPDATE hosted_policy_versions SET status = 'active' WHERE policy_source = '{HOSTED_PERMISSION_STORE_SOURCE}' AND policy_version = '{HOSTED_POLICY_VERSION}';",
        )
        assert_error_type(stale_policy_response, "PERMISSION_SOURCE_UNAVAILABLE")
        audit_rows_after_stale_policy = count_audit_rows(container)
        if audit_rows_after_stale_policy != audit_rows_before_missing_auth:
            raise RuntimeError("gateway-local stale policy failure must not create Control Plane audit rows")

        execute_postgres(
            container,
            """
INSERT INTO hosted_policy_versions (policy_source, policy_version, policy_fingerprint, status, activated_at)
VALUES ('hosted-permission-store-secondary', 'hosted-policy-v2', 'sha256:hosted-permission-store-secondary-v2', 'active', now());
""",
        )
        ambiguous_policy_status, ambiguous_policy_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/validate",
            headers={"Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}"},
            expected_status={503},
        )
        assert_error_type(ambiguous_policy_response, "PERMISSION_SOURCE_UNAVAILABLE")
        audit_rows_after_ambiguous_policy = count_audit_rows(container)
        if audit_rows_after_ambiguous_policy != audit_rows_before_missing_auth:
            raise RuntimeError("gateway-local ambiguous policy failure must not create Control Plane audit rows")
        execute_postgres(
            container,
            "UPDATE hosted_policy_versions SET status = 'superseded' WHERE policy_source = 'hosted-permission-store-secondary';",
        )

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

        readonly_partition_status, readonly_partition_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/project-partition/replace",
            headers={
                "Authorization": f"Bearer {PUBLIC_READONLY_TOKEN}",
                "X-Request-ID": "dogfood-gateway-contract-readonly-partition",
                "Idempotency-Key": "dogfood-gateway-contract-readonly-partition-idempotency",
            },
            body={"registry": partition_registry, "source": "dogfood_project_partition_readonly"},
            expected_status={403},
        )
        assert_error_type(readonly_partition_response, "PUBLIC_AUTHZ_DENIED")
        audit_rows_after_readonly_partition_deny = count_audit_rows(container)
        if audit_rows_after_readonly_partition_deny != audit_rows_after_readonly_deny:
            raise RuntimeError("gateway-local readonly partition denial must not create Control Plane audit rows")

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
        if audit_rows_after_insufficient_forward != audit_rows_after_readonly_partition_deny:
            raise RuntimeError("Control Plane authz denial before handler must not create audit rows")

        partition_status, partition_response, partition_response_headers = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/project-partition/replace",
            headers={
                "Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}",
                "X-Request-ID": "dogfood-gateway-contract-partition-1",
                "Idempotency-Key": "dogfood-gateway-contract-partition-idempotency-key",
                "X-API2Agent-Gateway-Authorization": "Bearer caller-supplied-secret",
                "X-API2Agent-Principal-ID": SPOOFED_PRINCIPAL_ID,
                "X-API2Agent-Actor-ID": SPOOFED_ACTOR_ID,
                "X-API2Agent-Project-ID": SPOOFED_PROJECT_ID,
            },
            body={"registry": partition_registry, "source": "dogfood_project_partition_replace"},
            expected_status={201},
        )
        if partition_response.get("partition_project_id") != HARNESS_PROJECT_ID:
            raise RuntimeError(f"expected partition project evidence, got {partition_response}")
        if not partition_response.get("partition_diff_fingerprint"):
            raise RuntimeError(f"expected partition diff fingerprint, got {partition_response}")
        if partition_response.get("partition_counts", {}).get("api_keys_changed") != 1:
            raise RuntimeError(f"expected one api key partition change, got {partition_response}")
        if any(key.lower() == "idempotency-replayed" for key in partition_response_headers):
            raise RuntimeError(f"first partition replace should not be replayed, got {partition_response_headers}")

        partition_replay_status, partition_replay_response, partition_replay_headers = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/project-partition/replace",
            headers={
                "Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}",
                "X-Request-ID": "dogfood-gateway-contract-partition-replay",
                "Idempotency-Key": "dogfood-gateway-contract-partition-idempotency-key",
            },
            body={"registry": partition_registry, "source": "dogfood_project_partition_replace"},
            expected_status={200},
        )
        if partition_replay_response.get("replayed") is not True:
            raise RuntimeError(f"expected partition idempotency replay, got {partition_replay_response}")
        if partition_replay_headers.get("Idempotency-Replayed") != "true":
            raise RuntimeError(f"expected replay header, got {partition_replay_headers}")

        partition_violation_status, partition_violation_response, _ = request_json(
            "POST",
            f"{gateway_base_url}/v1/admin/registry/project-partition/replace",
            headers={
                "Authorization": f"Bearer {PUBLIC_ADMIN_TOKEN}",
                "X-Request-ID": "dogfood-gateway-contract-partition-violation",
                "Idempotency-Key": "dogfood-gateway-contract-partition-violation-idempotency-key",
            },
            body={"registry": cross_project_partition_registry, "source": "dogfood_project_partition_violation"},
            expected_status={403},
        )
        assert_error_type(partition_violation_response, "REGISTRY_PARTITION_VIOLATION")

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
            "hosted_permission_decisions": int(query_postgres_scalar(container, "SELECT count(*) FROM hosted_permission_decisions;")),
        }
        expected_counts = {
            "registry_revisions": 3,
            "admin_audit_events": 5,
            "idempotency_records": 2,
            "providers": 1,
            "hosted_permission_decisions": 0,
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
    metadata->>'partition_project_id' AS partition_project_id,
    metadata->>'partition_diff_fingerprint' AS partition_diff_fingerprint,
    metadata->>'api_keys_changed' AS api_keys_changed,
    metadata::text LIKE '%{SPOOFED_PRINCIPAL_ID}%' OR metadata::text LIKE '%{SPOOFED_ACTOR_ID}%' OR metadata::text LIKE '%{SPOOFED_PROJECT_ID}%' AS metadata_contains_spoofed_identity,
    metadata::text LIKE '%{GATEWAY_SECRET}%' AS metadata_contains_gateway_secret,
    metadata::text LIKE '%{PUBLIC_ADMIN_TOKEN}%' OR metadata::text LIKE '%{PUBLIC_READONLY_TOKEN}%' AS metadata_contains_public_token
  FROM admin_audit_events
) AS t;
""",
        )
        if len(audit_rows) != 5:
            raise RuntimeError(f"expected five audit rows, got {audit_rows}")
        expected_audit_identities = {
            "dogfood-gateway-contract-validate-1": (HARNESS_ACTOR_ID, HARNESS_PRINCIPAL_ID, HARNESS_TOKEN_ID_ADMIN),
            "dogfood-gateway-contract-readonly-validate": (
                READONLY_POLICY.actor_id,
                READONLY_POLICY.principal_id,
                HARNESS_TOKEN_ID_READONLY,
            ),
            "dogfood-gateway-contract-partition-1": (HARNESS_ACTOR_ID, HARNESS_PRINCIPAL_ID, HARNESS_TOKEN_ID_ADMIN),
            "dogfood-gateway-contract-partition-violation": (
                HARNESS_ACTOR_ID,
                HARNESS_PRINCIPAL_ID,
                HARNESS_TOKEN_ID_ADMIN,
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
            if row["request_id"] == "dogfood-gateway-contract-partition-1":
                if row["action"] != "registry.project_partition_replace" or row["partition_project_id"] != HARNESS_PROJECT_ID:
                    raise RuntimeError(f"expected partition audit evidence, got {row}")
                if not row["partition_diff_fingerprint"] or row["api_keys_changed"] != "1":
                    raise RuntimeError(f"expected partition diff/count evidence, got {row}")
            if row["request_id"] == "dogfood-gateway-contract-partition-violation":
                if row["outcome"] != "failure" or row["partition_project_id"] != HARNESS_PROJECT_ID:
                    raise RuntimeError(f"expected partition violation failure audit evidence, got {row}")
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
        if len(idempotency_rows) != 2:
            raise RuntimeError(f"expected two idempotency rows, got {idempotency_rows}")
        idempotency_by_operation = {row["operation"]: row for row in idempotency_rows}
        partition_idempotency_row = idempotency_by_operation.get("registry.project_partition_replace")
        import_idempotency_row = idempotency_by_operation.get("registry.import_replace")
        if partition_idempotency_row is None or import_idempotency_row is None:
            raise RuntimeError(f"expected partition and import idempotency rows, got {idempotency_rows}")
        for idempotency_row in idempotency_rows:
            if idempotency_row["project_id"] != HARNESS_PROJECT_ID or idempotency_row["actor_id"] != HARNESS_ACTOR_ID:
                raise RuntimeError(f"expected harness idempotency scope, got {idempotency_row}")
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
                "permission_source": HOSTED_PERMISSION_STORE_SOURCE,
                "policy_version": HOSTED_POLICY_VERSION,
                "policy_fingerprint": HOSTED_POLICY_FINGERPRINT,
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
                "missing_membership_status": no_membership_status,
                "missing_membership_error_type": no_membership_response.get("error", {}).get("error_type"),
                "suspended_membership_status": suspended_membership_status,
                "suspended_membership_error_type": suspended_membership_response.get("error", {}).get("error_type"),
                "revoked_permission_status": revoked_permission_status,
                "revoked_permission_error_type": revoked_permission_response.get("error", {}).get("error_type"),
                "stale_policy_status": stale_policy_status,
                "stale_policy_error_type": stale_policy_response.get("error", {}).get("error_type"),
                "ambiguous_policy_status": ambiguous_policy_status,
                "ambiguous_policy_error_type": ambiguous_policy_response.get("error", {}).get("error_type"),
                "audit_rows_before_missing_public_auth": audit_rows_before_missing_auth,
                "audit_rows_after_missing_public_auth": audit_rows_after_missing_auth,
                "audit_rows_after_invalid_public_auth": audit_rows_after_invalid_auth,
                "audit_rows_after_permission_source_unavailable": audit_rows_after_unavailable,
                "audit_rows_after_missing_membership": audit_rows_after_no_membership,
                "audit_rows_after_suspended_membership": audit_rows_after_suspended_membership,
                "audit_rows_after_revoked_permission": audit_rows_after_revoked_permission,
                "audit_rows_after_stale_policy": audit_rows_after_stale_policy,
                "audit_rows_after_ambiguous_policy": audit_rows_after_ambiguous_policy,
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
                "readonly_partition_status": readonly_partition_status,
                "readonly_partition_error_type": readonly_partition_response.get("error", {}).get("error_type"),
                "audit_rows_after_readonly_partition_deny": audit_rows_after_readonly_partition_deny,
                "insufficient_forward_status": insufficient_forward_status,
                "insufficient_forward_error_type": insufficient_forward_response.get("error", {}).get("error_type"),
                "audit_rows_after_insufficient_forward": audit_rows_after_insufficient_forward,
                "partition_status": partition_status,
                "partition_response": partition_response,
                "partition_replay_status": partition_replay_status,
                "partition_replay_response": partition_replay_response,
                "partition_violation_status": partition_violation_status,
                "partition_violation_error_type": partition_violation_response.get("error", {}).get("error_type"),
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
                        "required_permission": decision.required_permission,
                        "policy_source": decision.policy_source,
                        "policy_version": decision.policy_version,
                        "policy_fingerprint": decision.policy_fingerprint,
                        "decision_id": decision.decision_id,
                        "permission_source": decision.permission_source,
                        "resolved_at": decision.resolved_at,
                    }
                    for decision in gateway.permission_decisions
                ],
                "audit_counts": counts,
                "audit_rows": audit_rows,
                "idempotency_rows": idempotency_rows,
                "replacement_registry": str(replacement_path),
                "partition_registry": str(partition_path),
                "cross_project_partition_registry": str(cross_project_partition_path),
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
