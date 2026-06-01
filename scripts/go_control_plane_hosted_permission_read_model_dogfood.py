from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE = REPO_ROOT / "services" / "control-plane"
SCHEMA = CONTROL_PLANE / "schema" / "postgres" / "001_persistent_registry_store.sql"
REGISTRY = CONTROL_PLANE / "testdata" / "registry" / "network.public_ip.get.json"

HARNESS_PROJECT_ID = "gateway-harness-project"
HARNESS_PRINCIPAL_ID = "gateway-harness-principal"
HARNESS_ACTOR_ID = "gateway-harness-actor"
HARNESS_ORGANIZATION_ID = "gateway-harness-org"
READONLY_PRINCIPAL_ID = "gateway-harness-readonly-principal"
READONLY_ACTOR_ID = "gateway-harness-readonly-actor"
NO_MEMBERSHIP_SUBJECT_ID = "gateway-harness-no-membership-principal"
SUSPENDED_PRINCIPAL_ID = "gateway-harness-suspended-principal"
SUSPENDED_ACTOR_ID = "gateway-harness-suspended-actor"
REVOKED_PRINCIPAL_ID = "gateway-harness-revoked-principal"
REVOKED_ACTOR_ID = "gateway-harness-revoked-actor"
HOSTED_PERMISSION_STORE_SOURCE = "hosted-permission-store-fixture"
HOSTED_POLICY_VERSION = "hosted-policy-v1"
HOSTED_POLICY_FINGERPRINT = "sha256:hosted-permission-store-fixture-v1"

PERMISSION_REGISTRY_VALIDATE = "control_plane.registry.validate"
PERMISSION_REGISTRY_IMPORT_REPLACE = "control_plane.registry.import_replace"
PERMISSION_REGISTRY_PROJECT_PARTITION_REPLACE = "control_plane.registry.project_partition_replace"
PERMISSION_SNAPSHOT_EXPORT_ARTIFACT = "control_plane.snapshot.export_artifact"
PERMISSION_DISTRIBUTION_PUBLISH = "control_plane.distribution.publish"
PERMISSION_DISTRIBUTION_READ_CURRENT = "control_plane.distribution.read_current"


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


def psql(container: str, sql: str) -> str:
    result = run(
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
            "-t",
            "-A",
        ],
        input_text=sql,
    )
    return result.stdout.strip()


def create_harness_project_registry(path: Path) -> dict:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    data["projects"][0]["id"] = HARNESS_PROJECT_ID
    data["projects"][0]["name"] = "Hosted Permission Store Dogfood Project"
    data["api_keys"][0]["project_id"] = HARNESS_PROJECT_ID
    data["credential_metadata"][0]["owner_id"] = HARNESS_PROJECT_ID
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
  ('{READONLY_PRINCIPAL_ID}', 'dogfood/idp/readonly', 'Dogfood Readonly', 'active'),
  ('{NO_MEMBERSHIP_SUBJECT_ID}', 'dogfood/idp/no-membership', 'Dogfood No Membership', 'active'),
  ('{SUSPENDED_PRINCIPAL_ID}', 'dogfood/idp/suspended', 'Dogfood Suspended', 'active'),
  ('{REVOKED_PRINCIPAL_ID}', 'dogfood/idp/revoked', 'Dogfood Revoked', 'active');

INSERT INTO hosted_project_memberships (subject_id, actor_id, project_id, organization_id, status)
VALUES
  ('{HARNESS_PRINCIPAL_ID}', '{HARNESS_ACTOR_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'active'),
  ('{READONLY_PRINCIPAL_ID}', '{READONLY_ACTOR_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'active'),
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
  ('{READONLY_PRINCIPAL_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'project_readonly', 'active', 'seed'),
  ('{READONLY_PRINCIPAL_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'dogfood', 'active', 'seed'),
  ('{SUSPENDED_PRINCIPAL_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'project_admin', 'active', 'seed'),
  ('{REVOKED_PRINCIPAL_ID}', '{HARNESS_PROJECT_ID}', '{HARNESS_ORGANIZATION_ID}', 'project_revoked', 'active', 'seed');

INSERT INTO hosted_permission_grants (role_id, permission, scope_type, status, metadata)
VALUES
{grant_values};

INSERT INTO hosted_policy_versions (policy_source, policy_version, policy_fingerprint, status, activated_at)
VALUES ('{HOSTED_PERMISSION_STORE_SOURCE}', '{HOSTED_POLICY_VERSION}', '{HOSTED_POLICY_FINGERPRINT}', 'active', now());
"""


def query_counts(container: str) -> dict[str, int]:
    raw = psql(
        container,
        """
SELECT json_build_object(
  'projects', (SELECT COUNT(*) FROM projects),
  'hosted_subjects', (SELECT COUNT(*) FROM hosted_subjects),
  'hosted_project_memberships', (SELECT COUNT(*) FROM hosted_project_memberships),
  'hosted_roles', (SELECT COUNT(*) FROM hosted_roles),
  'hosted_role_bindings', (SELECT COUNT(*) FROM hosted_role_bindings),
  'hosted_permission_grants', (SELECT COUNT(*) FROM hosted_permission_grants),
  'hosted_policy_versions', (SELECT COUNT(*) FROM hosted_policy_versions),
  'hosted_permission_decisions', (SELECT COUNT(*) FROM hosted_permission_decisions)
)::text;
""",
    )
    return json.loads(raw)


def assert_report(report: dict) -> None:
    if report.get("status") != "passed":
        raise RuntimeError(f"dogfood did not pass: {report}")
    if report.get("decision_rows_persisted") != 0:
        raise RuntimeError(f"read model unexpectedly persisted decision rows: {report}")
    if not report.get("secret_safe_evidence"):
        raise RuntimeError(f"dogfood evidence was not secret safe: {report}")
    cases = report.get("cases", {})
    expected = {
        "admin_allowed": (True, 200, ""),
        "readonly_missing_permission": (False, 403, "PUBLIC_AUTHZ_DENIED"),
        "missing_membership": (False, 403, "PUBLIC_AUTHZ_DENIED"),
        "suspended_membership": (False, 403, "PUBLIC_AUTHZ_DENIED"),
        "revoked_grant": (False, 403, "PUBLIC_AUTHZ_DENIED"),
        "no_active_policy": (False, 503, "PERMISSION_SOURCE_UNAVAILABLE"),
        "ambiguous_active_policy": (False, 503, "PERMISSION_SOURCE_UNAVAILABLE"),
    }
    for name, (allowed, status, error_type) in expected.items():
        case = cases.get(name)
        if case is None:
            raise RuntimeError(f"missing dogfood case {name}: {report}")
        if case.get("allowed") != allowed or case.get("status") != status or case.get("error_type") != error_type:
            raise RuntimeError(f"unexpected case result for {name}: {case}")
        if not str(case.get("decision_id", "")).startswith("decision-"):
            raise RuntimeError(f"missing decision id for {name}: {case}")
    if PERMISSION_REGISTRY_IMPORT_REPLACE not in cases["admin_allowed"].get("permissions", []):
        raise RuntimeError(f"admin allowed case missing permission evidence: {cases['admin_allowed']}")
    if PERMISSION_REGISTRY_IMPORT_REPLACE in cases["readonly_missing_permission"].get("permissions", []):
        raise RuntimeError(f"readonly denied case carried missing permission: {cases['readonly_missing_permission']}")


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

    container = "api2agent-pg-hosted-permission-read-model-dogfood"
    pg_port = find_free_port()
    dsn = f"postgres://api2agent:api2agent@127.0.0.1:{pg_port}/api2agent?sslmode=disable"
    report: dict = {
        "dogfood": "go_control_plane_hosted_permission_store_read_model_live_postgres",
        "status": "started",
        "container": container,
        "dsn": f"postgres://api2agent:REDACTED@127.0.0.1:{pg_port}/api2agent?sslmode=disable",
        "public_tokens_redacted": ["REDACTED"],
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
        seed_registry_path = workdir / "hosted-permission-read-model-registry.json"
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
        psql(container, hosted_permission_seed_sql())
        counts_before = query_counts(container)

        dogfood = run(
            [
                "go",
                "run",
                "./cmd/api2agent-hosted-permission-read-model-dogfood",
                "--postgres-dsn",
                dsn,
            ],
            cwd=CONTROL_PLANE,
        )
        dogfood_report = json.loads(dogfood.stdout)
        assert_report(dogfood_report)
        counts_after = query_counts(container)
        if counts_after["hosted_permission_decisions"] != 0:
            raise RuntimeError(f"hosted_permission_decisions should remain empty: {counts_after}")

        report.update(
            {
                "status": "passed",
                "seed_stdout": seed.stdout.strip(),
                "counts_before": counts_before,
                "counts_after": counts_after,
                "read_model": dogfood_report,
            }
        )
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    finally:
        if not args.keep_container:
            subprocess.run(["podman", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
