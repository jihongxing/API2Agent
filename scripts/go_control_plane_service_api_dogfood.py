from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ADMIN_TOKEN = "local-control-plane-secret"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dogfood Go Control Plane service API skeleton.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".dogfood/go-control-plane-service-api/report.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-control-plane-service-"))
    try:
        cp_dir = Path("services/control-plane")
        exe_name = "api2agent-controlplane.exe" if os.name == "nt" else "api2agent-controlplane"
        cp_exe = tmp / exe_name
        subprocess.run(["go", "build", "-o", str(cp_exe), "./cmd/api2agent-controlplane"], cwd=cp_dir, check=True)
        report = run_scenario(tmp=tmp, cp_dir=cp_dir, cp_exe=cp_exe)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_scenario(*, tmp: Path, cp_dir: Path, cp_exe: Path) -> dict:
    scenario_dir = tmp / "control-plane-service-api"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    registry_path = write_registry(scenario_dir / "registry.json")
    artifact_dir = scenario_dir / "artifact-cli"
    distribution_dir = scenario_dir / "distribution"
    http_artifact_dir = scenario_dir / "artifact-http"

    subprocess.run(
        [str(cp_exe), "export-artifact", "--registry", str(registry_path), "--output-dir", str(artifact_dir)],
        cwd=cp_dir,
        check=True,
    )
    subprocess.run(
        [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir), "--distribution-dir", str(distribution_dir)],
        cwd=cp_dir,
        check=True,
    )

    port = free_port()
    proc = subprocess.Popen(
        [
            str(cp_exe),
            "serve",
            "--registry",
            str(registry_path),
            "--admin-token",
            ADMIN_TOKEN,
            "--distribution-dir",
            str(distribution_dir),
            "--addr",
            f"127.0.0.1:{port}",
        ],
        cwd=cp_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        wait_for_health(port)
        health = get_json(f"http://127.0.0.1:{port}/healthz")
        unauth_validate = post_json_allow_error(f"http://127.0.0.1:{port}/v1/admin/registry/validate", {}, token=None)
        validation = post_json(f"http://127.0.0.1:{port}/v1/admin/registry/validate", {}, token=ADMIN_TOKEN)
        exported = post_json(
            f"http://127.0.0.1:{port}/v1/admin/snapshots/export-artifact",
            {"output_dir": str(http_artifact_dir)},
            token=ADMIN_TOKEN,
        )
        current = get_json(f"http://127.0.0.1:{port}/v1/admin/distribution/current", token=ADMIN_TOKEN)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    checks = {
        "health_is_public_and_ok": health.get("status") == "ok"
        and health.get("service") == "api2agent-control-plane",
        "unauthorized_admin_rejected": unauth_validate.get("status_code") == 401
        and unauth_validate.get("error", {}).get("error_type") == "AUTH_ERROR",
        "registry_validation_passed": validation.get("valid") is True
        and validation.get("registry_fingerprint", "").startswith("sha256:"),
        "artifact_export_created_manifest": (http_artifact_dir / "manifest.json").exists()
        and exported.get("manifest", {}).get("snapshot_version") == "snapshot_control_plane_service_api_v1",
        "artifact_export_created_snapshot": (http_artifact_dir / "snapshot.json").exists(),
        "distribution_current_reported": current.get("pointer", {}).get("snapshot_version")
        == "snapshot_control_plane_service_api_v1",
    }
    return {
        "dogfood": "go_control_plane_service_api",
        "registry_path": str(registry_path),
        "distribution_dir": str(distribution_dir),
        "health": health,
        "unauth_validate": unauth_validate,
        "validation": validation,
        "exported": exported,
        "current": current,
        "checks": checks,
        "passed": all(checks.values()),
    }


def write_registry(path: Path) -> Path:
    registry = {
        "projects": [
            {"id": "local", "name": "Local", "status": "active", "default_mode": "proxy"},
        ],
        "api_keys": [
            {"id": "key_local_dev", "project_id": "local", "key_prefix": "a2a_local", "status": "active"},
        ],
        "capabilities": [
            {"id": "network.public_ip.get", "version": "1.0.0", "name": "Get public IP"},
        ],
        "providers": [
            {
                "id": "ipify_public_ip_v1",
                "capability_id": "network.public_ip.get",
                "capability_version": "1.0.0",
                "provider_id": "ipify",
                "provider_version": "1.0.0",
                "mapping_version": "1.0.0",
                "tool_id": "get_public_ip",
                "regions": ["global"],
                "geo_affinity": "global",
                "estimated_cost": 0,
                "status": "active",
                "metadata": {"base_url": "https://api.ipify.org"},
            },
        ],
        "routing_policy": {"strategy": "first", "routing_mode": "deterministic"},
        "snapshot": {
            "version": "snapshot_control_plane_service_api_v1",
            "fetched_at": "2026-05-30T00:00:00Z",
            "ttl": "24h",
            "source": "pull",
        },
    }
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return path


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(port: int) -> None:
    deadline = time.time() + 10
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            health = get_json(f"http://127.0.0.1:{port}/healthz")
            if health.get("status") == "ok":
                return
        except (ConnectionError, HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"control plane service did not become healthy: {last_error}")


def get_json(url: str, *, token: str | None = None) -> dict:
    request = Request(url, method="GET")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict, *, token: str | None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json_allow_error(url: str, payload: dict, *, token: str | None) -> dict:
    try:
        return post_json(url, payload, token=token)
    except HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8"))
        body["status_code"] = exc.code
        return body


if __name__ == "__main__":
    raise SystemExit(main())
