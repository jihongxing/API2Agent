from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from pathlib import Path
from urllib.request import Request, urlopen


FIXED_IP = "203.0.113.250"


def make_ip_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps({"ip": FIXED_IP}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Dogfood Go Control Plane minimum snapshot export and Go Data Plane consumption.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".dogfood/go-control-plane-minimum/report.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-control-plane-"))
    try:
        cp_dir = Path("services/control-plane")
        dp_dir = Path("services/data-plane")
        cp_exe_name = "api2agent-controlplane.exe" if os.name == "nt" else "api2agent-controlplane"
        dp_exe_name = "api2agent-dataplane.exe" if os.name == "nt" else "api2agent-dataplane"
        snapshot_check_exe_name = "api2agent-snapshot-check.exe" if os.name == "nt" else "api2agent-snapshot-check"
        cp_exe = tmp / cp_exe_name
        dp_exe = tmp / dp_exe_name
        snapshot_check_exe = tmp / snapshot_check_exe_name
        subprocess.run(["go", "build", "-o", str(cp_exe), "./cmd/api2agent-controlplane"], cwd=cp_dir, check=True)
        subprocess.run(["go", "build", "-o", str(dp_exe), "./cmd/api2agent-dataplane"], cwd=dp_dir, check=True)
        subprocess.run(["go", "build", "-o", str(snapshot_check_exe), "./cmd/api2agent-snapshot-check"], cwd=dp_dir, check=True)

        report = run_scenario(tmp=tmp, cp_exe=cp_exe, dp_exe=dp_exe, snapshot_check_exe=snapshot_check_exe, dp_dir=dp_dir)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_scenario(*, tmp: Path, cp_exe: Path, dp_exe: Path, snapshot_check_exe: Path, dp_dir: Path) -> dict:
    provider_server = ThreadingHTTPServer(("127.0.0.1", 0), make_ip_handler())
    thread = threading.Thread(target=provider_server.serve_forever, daemon=True)
    thread.start()
    try:
        scenario_dir = tmp / "control-plane-minimum"
        scenario_dir.mkdir(parents=True, exist_ok=True)
        registry = write_registry(
            scenario_dir / "registry.json",
            f"http://127.0.0.1:{provider_server.server_port}",
            "snapshot_control_plane_public_ip_v1",
        )
        invalid_registry = write_invalid_registry(scenario_dir / "invalid-registry.json", f"http://127.0.0.1:{provider_server.server_port}")
        artifact_dir = scenario_dir / "artifact"
        distribution_dir = scenario_dir / "distribution"
        subprocess.run(
            [str(cp_exe), "export-artifact", "--registry", str(registry), "--output-dir", str(artifact_dir)],
            cwd=dp_dir.parent,
            check=True,
        )
        subprocess.run(
            [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir), "--distribution-dir", str(distribution_dir)],
            cwd=dp_dir.parent,
            check=True,
        )
        snapshot = artifact_dir / "snapshot.json"
        manifest = read_json(artifact_dir / "manifest.json")
        current_pointer = read_json(distribution_dir / "current.json")
        snapshot_check = subprocess.run(
            [str(snapshot_check_exe), "--snapshot", str(distribution_dir)],
            cwd=dp_dir,
            check=False,
            capture_output=True,
            text=True,
        )
        snapshot_check_report = parse_json_report(snapshot_check)
        invalid_export = subprocess.run(
            [str(cp_exe), "export-artifact", "--registry", str(invalid_registry), "--output-dir", str(scenario_dir / "invalid-artifact")],
            cwd=dp_dir.parent,
            check=False,
            capture_output=True,
            text=True,
        )
        event_dir = scenario_dir / "events"
        port = free_port()
        env = os.environ.copy()
        env["API2AGENT_DATAPLANE_ADDR"] = f"127.0.0.1:{port}"
        env["API2AGENT_EVENT_DIR"] = str(event_dir)
        env["API2AGENT_SNAPSHOT"] = str(distribution_dir)
        env["API2AGENT_SNAPSHOT_RELOAD_POLICY"] = "manual"
        proc = subprocess.Popen([str(dp_exe)], cwd=dp_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            wait_for_port(port)
            health_before_reload = get_json(f"http://127.0.0.1:{port}/healthz")
            (distribution_dir / "current.json").write_text(
                json.dumps(
                    {
                        "distribution_version": "api2agent.snapshot_distribution.v0",
                        "snapshot_version": "snapshot_broken_missing_file",
                        "snapshot_file": "artifacts/snapshot_broken_missing_file/snapshot.json",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            failed_reload = post_json_allow_error(f"http://127.0.0.1:{port}/v1/admin/reload-snapshot", {})
            health_after_failed_reload = get_json(f"http://127.0.0.1:{port}/healthz")
            registry_v2 = write_registry(
                scenario_dir / "registry-v2.json",
                f"http://127.0.0.1:{provider_server.server_port}",
                "snapshot_control_plane_public_ip_v2",
            )
            artifact_dir_v2 = scenario_dir / "artifact-v2"
            subprocess.run(
                [str(cp_exe), "export-artifact", "--registry", str(registry_v2), "--output-dir", str(artifact_dir_v2)],
                cwd=dp_dir.parent,
                check=True,
            )
            subprocess.run(
                [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir_v2), "--distribution-dir", str(distribution_dir)],
                cwd=dp_dir.parent,
                check=True,
            )
            current_pointer_after_reload = read_json(distribution_dir / "current.json")
            reload_response = post_json(f"http://127.0.0.1:{port}/v1/admin/reload-snapshot", {})
            health = get_json(f"http://127.0.0.1:{port}/healthz")
            registry_v3 = write_registry(
                scenario_dir / "registry-v3.json",
                f"http://127.0.0.1:{provider_server.server_port}",
                "snapshot_control_plane_public_ip_v3",
            )
            artifact_dir_v3 = scenario_dir / "artifact-v3-incompatible"
            subprocess.run(
                [str(cp_exe), "export-artifact", "--registry", str(registry_v3), "--output-dir", str(artifact_dir_v3)],
                cwd=dp_dir.parent,
                check=True,
            )
            subprocess.run(
                [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir_v3), "--distribution-dir", str(distribution_dir)],
                cwd=dp_dir.parent,
                check=True,
            )
            force_snapshot_schema_version(
                distribution_dir
                / "artifacts"
                / "snapshot_control_plane_public_ip_v3"
                / "snapshot.json",
                "api2agent.protocol.v9",
            )
            refresh_distribution_snapshot_digest(distribution_dir, "snapshot_control_plane_public_ip_v3")
            incompatible_reload = post_json_allow_error(f"http://127.0.0.1:{port}/v1/admin/reload-snapshot", {})
            health_after_incompatible_reload = get_json(f"http://127.0.0.1:{port}/healthz")
            registry_v4 = write_registry(
                scenario_dir / "registry-v4.json",
                f"http://127.0.0.1:{provider_server.server_port}",
                "snapshot_control_plane_public_ip_v4",
            )
            artifact_dir_v4 = scenario_dir / "artifact-v4-strict-metadata"
            subprocess.run(
                [str(cp_exe), "export-artifact", "--registry", str(registry_v4), "--output-dir", str(artifact_dir_v4)],
                cwd=dp_dir.parent,
                check=True,
            )
            subprocess.run(
                [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir_v4), "--distribution-dir", str(distribution_dir)],
                cwd=dp_dir.parent,
                check=True,
            )
            remove_snapshot_metadata_key(
                distribution_dir
                / "artifacts"
                / "snapshot_control_plane_public_ip_v4"
                / "snapshot.json",
                "registry_fingerprint",
            )
            refresh_distribution_snapshot_digest(distribution_dir, "snapshot_control_plane_public_ip_v4")
            manifest_consistency_reload = post_json_allow_error(f"http://127.0.0.1:{port}/v1/admin/reload-snapshot", {})
            health_after_manifest_consistency_reload = get_json(f"http://127.0.0.1:{port}/healthz")
            registry_v5 = write_registry(
                scenario_dir / "registry-v5.json",
                f"http://127.0.0.1:{provider_server.server_port}",
                "snapshot_control_plane_public_ip_v5",
            )
            artifact_dir_v5 = scenario_dir / "artifact-v5-manifest-mismatch"
            subprocess.run(
                [str(cp_exe), "export-artifact", "--registry", str(registry_v5), "--output-dir", str(artifact_dir_v5)],
                cwd=dp_dir.parent,
                check=True,
            )
            force_manifest_registry_fingerprint(artifact_dir_v5 / "manifest.json", "sha256:manifest-mismatch")
            manifest_mismatch_publish = subprocess.run(
                [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir_v5), "--distribution-dir", str(distribution_dir)],
                cwd=dp_dir.parent,
                check=False,
                capture_output=True,
                text=True,
            )
            current_pointer_after_manifest_mismatch_publish = read_json(distribution_dir / "current.json")
            registry_v6 = write_registry(
                scenario_dir / "registry-v6.json",
                f"http://127.0.0.1:{provider_server.server_port}",
                "snapshot_control_plane_public_ip_v6",
            )
            artifact_dir_v6 = scenario_dir / "artifact-v6-content-digest"
            subprocess.run(
                [str(cp_exe), "export-artifact", "--registry", str(registry_v6), "--output-dir", str(artifact_dir_v6)],
                cwd=dp_dir.parent,
                check=True,
            )
            subprocess.run(
                [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir_v6), "--distribution-dir", str(distribution_dir)],
                cwd=dp_dir.parent,
                check=True,
            )
            append_file_whitespace(
                distribution_dir
                / "artifacts"
                / "snapshot_control_plane_public_ip_v6"
                / "snapshot.json"
            )
            content_digest_reload = post_json_allow_error(f"http://127.0.0.1:{port}/v1/admin/reload-snapshot", {})
            health_after_content_digest_reload = get_json(f"http://127.0.0.1:{port}/healthz")
            registry_v7 = write_registry(
                scenario_dir / "registry-v7.json",
                f"http://127.0.0.1:{provider_server.server_port}",
                "snapshot_control_plane_public_ip_v7",
            )
            artifact_dir_v7 = scenario_dir / "artifact-v7-content-digest-mismatch"
            subprocess.run(
                [str(cp_exe), "export-artifact", "--registry", str(registry_v7), "--output-dir", str(artifact_dir_v7)],
                cwd=dp_dir.parent,
                check=True,
            )
            append_file_whitespace(artifact_dir_v7 / "snapshot.json")
            content_digest_publish = subprocess.run(
                [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir_v7), "--distribution-dir", str(distribution_dir)],
                cwd=dp_dir.parent,
                check=False,
                capture_output=True,
                text=True,
            )
            current_pointer_after_content_digest_publish = read_json(distribution_dir / "current.json")
            registry_v8 = write_registry(
                scenario_dir / "registry-v8.json",
                f"http://127.0.0.1:{provider_server.server_port}",
                "snapshot_control_plane_public_ip_v8",
            )
            artifact_dir_v8 = scenario_dir / "artifact-v8-unsafe-manifest-path"
            subprocess.run(
                [str(cp_exe), "export-artifact", "--registry", str(registry_v8), "--output-dir", str(artifact_dir_v8)],
                cwd=dp_dir.parent,
                check=True,
            )
            force_manifest_snapshot_file(artifact_dir_v8 / "manifest.json", "../snapshot.json")
            unsafe_manifest_path_publish = subprocess.run(
                [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir_v8), "--distribution-dir", str(distribution_dir)],
                cwd=dp_dir.parent,
                check=False,
                capture_output=True,
                text=True,
            )
            current_pointer_after_unsafe_manifest_path_publish = read_json(distribution_dir / "current.json")
            registry_v9 = write_registry(
                scenario_dir / "registry-v9.json",
                f"http://127.0.0.1:{provider_server.server_port}",
                "snapshot_control_plane_public_ip_v9",
            )
            artifact_dir_v9 = scenario_dir / "artifact-v9-unsafe-pointer-path"
            subprocess.run(
                [str(cp_exe), "export-artifact", "--registry", str(registry_v9), "--output-dir", str(artifact_dir_v9)],
                cwd=dp_dir.parent,
                check=True,
            )
            subprocess.run(
                [str(cp_exe), "publish-artifact", "--artifact-dir", str(artifact_dir_v9), "--distribution-dir", str(distribution_dir)],
                cwd=dp_dir.parent,
                check=True,
            )
            force_current_snapshot_file(distribution_dir / "current.json", "../outside.json")
            unsafe_pointer_path_reload = post_json_allow_error(f"http://127.0.0.1:{port}/v1/admin/reload-snapshot", {})
            health_after_unsafe_pointer_path_reload = get_json(f"http://127.0.0.1:{port}/healthz")
            response = post_json(
                f"http://127.0.0.1:{port}/v1/execute",
                {
                    "project_id": "local",
                    "capability_id": "network.public_ip.get",
                    "capability_version": "0.1-migrated",
                    "input": {},
                    "execution_mode": "proxy",
                    "timeout_budget_ms": 5000,
                },
            )
        except Exception as exc:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            raise RuntimeError(
                "go data plane dogfood process failed; "
                f"stdout={stdout.decode('utf-8', errors='replace')} "
                f"stderr={stderr.decode('utf-8', errors='replace')}"
            ) from exc
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        events = read_jsonl(event_dir / "events.jsonl")
        reload_events = [event["record"] for event in events if event["event_type"] == "snapshot_reload_event"]
        usage = next((event["record"] for event in events if event["event_type"] == "usage_event"), {})
        routing_decision = next((event["record"] for event in events if event["event_type"] == "routing_decision"), {})
        checks = {
            "control_plane_export_success": snapshot.exists(),
            "artifact_manifest_exists": (artifact_dir / "manifest.json").exists(),
            "manifest_references_snapshot": manifest.get("snapshot_file") == "snapshot.json",
            "manifest_fingerprint_matches_snapshot_check": manifest.get("registry_fingerprint")
            == snapshot_check_report.get("registry_fingerprint"),
            "manifest_validation_valid": (manifest.get("validation") or {}).get("valid") is True,
            "distribution_current_exists": (distribution_dir / "current.json").exists(),
            "distribution_current_points_to_snapshot": current_pointer.get("snapshot_file")
            == "artifacts/snapshot_control_plane_public_ip_v1/snapshot.json",
            "distribution_current_fingerprint_matches_manifest": current_pointer.get("registry_fingerprint")
            == manifest.get("registry_fingerprint"),
            "distribution_artifact_snapshot_exists": (
                distribution_dir / "artifacts" / "snapshot_control_plane_public_ip_v1" / "snapshot.json"
            ).exists(),
            "health_before_reload_snapshot_version_matches": health_before_reload.get("snapshot_version")
            == "snapshot_control_plane_public_ip_v1",
            "failed_reload_rejected": failed_reload.get("status_code") == 503
            and failed_reload.get("reloaded") is False,
            "failed_reload_kept_previous_snapshot": failed_reload.get("kept_snapshot_version")
            == "snapshot_control_plane_public_ip_v1",
            "health_after_failed_reload_still_v1": health_after_failed_reload.get("snapshot_version")
            == "snapshot_control_plane_public_ip_v1",
            "failed_reload_audit_event_recorded": len(reload_events) >= 1
            and reload_events[0].get("outcome") == "failure"
            and reload_events[0].get("kept_snapshot_version") == "snapshot_control_plane_public_ip_v1",
            "reload_response_success": reload_response.get("reloaded") is True,
            "reload_previous_snapshot_version_matches": reload_response.get("previous_snapshot_version")
            == "snapshot_control_plane_public_ip_v1",
            "reload_snapshot_version_matches": reload_response.get("snapshot_version")
            == "snapshot_control_plane_public_ip_v2",
            "successful_reload_audit_event_recorded": len(reload_events) >= 2
            and reload_events[1].get("outcome") == "success"
            and reload_events[1].get("target_snapshot_version") == "snapshot_control_plane_public_ip_v2",
            "incompatible_reload_rejected": incompatible_reload.get("status_code") == 503
            and incompatible_reload.get("reloaded") is False,
            "incompatible_reload_kept_v2": incompatible_reload.get("kept_snapshot_version")
            == "snapshot_control_plane_public_ip_v2",
            "incompatible_reload_audit_event_recorded": len(reload_events) >= 3
            and reload_events[2].get("outcome") == "failure"
            and reload_events[2].get("kept_snapshot_version") == "snapshot_control_plane_public_ip_v2",
            "health_after_incompatible_reload_still_v2": health_after_incompatible_reload.get("snapshot_version")
            == "snapshot_control_plane_public_ip_v2",
            "manifest_consistency_reload_rejected": manifest_consistency_reload.get("status_code") == 503
            and manifest_consistency_reload.get("reloaded") is False,
            "manifest_consistency_reload_kept_v2": manifest_consistency_reload.get("kept_snapshot_version")
            == "snapshot_control_plane_public_ip_v2",
            "manifest_consistency_reload_audit_event_recorded": len(reload_events) >= 4
            and reload_events[3].get("outcome") == "failure"
            and reload_events[3].get("kept_snapshot_version") == "snapshot_control_plane_public_ip_v2",
            "health_after_manifest_consistency_reload_still_v2": health_after_manifest_consistency_reload.get("snapshot_version")
            == "snapshot_control_plane_public_ip_v2",
            "manifest_mismatch_publish_rejected": manifest_mismatch_publish.returncode != 0
            and "manifest registry_fingerprint" in manifest_mismatch_publish.stderr,
            "manifest_mismatch_publish_did_not_advance_current": current_pointer_after_manifest_mismatch_publish.get(
                "snapshot_version"
            )
            == "snapshot_control_plane_public_ip_v4",
            "content_digest_reload_rejected": content_digest_reload.get("status_code") == 503
            and content_digest_reload.get("reloaded") is False,
            "content_digest_reload_kept_v2": content_digest_reload.get("kept_snapshot_version")
            == "snapshot_control_plane_public_ip_v2",
            "content_digest_reload_audit_event_recorded": len(reload_events) >= 5
            and reload_events[4].get("outcome") == "failure"
            and reload_events[4].get("kept_snapshot_version") == "snapshot_control_plane_public_ip_v2",
            "health_after_content_digest_reload_still_v2": health_after_content_digest_reload.get("snapshot_version")
            == "snapshot_control_plane_public_ip_v2",
            "content_digest_publish_rejected": content_digest_publish.returncode != 0
            and "manifest snapshot_digest" in content_digest_publish.stderr,
            "content_digest_publish_did_not_advance_current": current_pointer_after_content_digest_publish.get(
                "snapshot_version"
            )
            == "snapshot_control_plane_public_ip_v6",
            "unsafe_manifest_path_publish_rejected": unsafe_manifest_path_publish.returncode != 0
            and "manifest snapshot_file" in unsafe_manifest_path_publish.stderr
            and "not safe" in unsafe_manifest_path_publish.stderr,
            "unsafe_manifest_path_publish_did_not_advance_current": current_pointer_after_unsafe_manifest_path_publish.get(
                "snapshot_version"
            )
            == "snapshot_control_plane_public_ip_v6",
            "unsafe_pointer_path_reload_rejected": unsafe_pointer_path_reload.get("status_code") == 503
            and unsafe_pointer_path_reload.get("reloaded") is False,
            "unsafe_pointer_path_reload_kept_v2": unsafe_pointer_path_reload.get("kept_snapshot_version")
            == "snapshot_control_plane_public_ip_v2",
            "unsafe_pointer_path_reload_audit_event_recorded": len(reload_events) >= 6
            and reload_events[5].get("outcome") == "failure"
            and reload_events[5].get("kept_snapshot_version") == "snapshot_control_plane_public_ip_v2",
            "health_after_unsafe_pointer_path_reload_still_v2": health_after_unsafe_pointer_path_reload.get(
                "snapshot_version"
            )
            == "snapshot_control_plane_public_ip_v2",
            "distribution_current_after_reload_points_to_v2": current_pointer_after_reload.get("snapshot_file")
            == "artifacts/snapshot_control_plane_public_ip_v2/snapshot.json",
            "distribution_v2_artifact_snapshot_exists": (
                distribution_dir / "artifacts" / "snapshot_control_plane_public_ip_v2" / "snapshot.json"
            ).exists(),
            "snapshot_check_passed": snapshot_check.returncode == 0
            and snapshot_check_report.get("passed") is True,
            "snapshot_check_has_registry_fingerprint": isinstance(snapshot_check_report.get("registry_fingerprint"), str)
            and snapshot_check_report.get("registry_fingerprint", "").startswith("sha256:"),
            "snapshot_check_has_explicit_version_policy": snapshot_check_report.get("snapshot_version_policy")
            == "explicit",
            "snapshot_check_schema_version_matches": snapshot_check_report.get("schema_version")
            == "api2agent.protocol.v0.2",
            "invalid_registry_rejected": invalid_export.returncode != 0
            and "references unknown project" in invalid_export.stderr,
            "health_snapshot_version_matches": health.get("snapshot_version") == "snapshot_control_plane_public_ip_v2",
            "response_success": response.get("success") is True,
            "response_ip_matches_provider": (response.get("output") or {}).get("ip") == FIXED_IP,
            "usage_has_attempt_id": (usage.get("request_metadata") or {}).get("attempt_id") == usage.get("id"),
            "routing_snapshot_version_matches": routing_decision.get("snapshot_version") == "snapshot_control_plane_public_ip_v2",
            "event_order_is_graph": [event["event_type"] for event in events] == [
                "snapshot_reload_event",
                "snapshot_reload_event",
                "snapshot_reload_event",
                "snapshot_reload_event",
                "snapshot_reload_event",
                "snapshot_reload_event",
                "request_context",
                "routing_decision",
                "usage_event",
                "decision_log",
            ],
        }
        return {
            "dogfood": "go_control_plane_minimum",
            "registry_path": str(registry),
            "invalid_registry_path": str(invalid_registry),
            "invalid_registry_exit_code": invalid_export.returncode,
            "invalid_registry_error": invalid_export.stderr.strip(),
            "artifact_dir": str(artifact_dir),
            "manifest": manifest,
            "distribution_dir": str(distribution_dir),
            "current_pointer": current_pointer,
            "current_pointer_after_reload": current_pointer_after_reload,
            "health_before_reload": health_before_reload,
            "failed_reload": failed_reload,
            "health_after_failed_reload": health_after_failed_reload,
            "reload_response": reload_response,
            "incompatible_reload": incompatible_reload,
            "health_after_incompatible_reload": health_after_incompatible_reload,
            "manifest_consistency_reload": manifest_consistency_reload,
            "health_after_manifest_consistency_reload": health_after_manifest_consistency_reload,
            "manifest_mismatch_publish_exit_code": manifest_mismatch_publish.returncode,
            "manifest_mismatch_publish_error": manifest_mismatch_publish.stderr.strip(),
            "current_pointer_after_manifest_mismatch_publish": current_pointer_after_manifest_mismatch_publish,
            "content_digest_reload": content_digest_reload,
            "health_after_content_digest_reload": health_after_content_digest_reload,
            "content_digest_publish_exit_code": content_digest_publish.returncode,
            "content_digest_publish_error": content_digest_publish.stderr.strip(),
            "current_pointer_after_content_digest_publish": current_pointer_after_content_digest_publish,
            "unsafe_manifest_path_publish_exit_code": unsafe_manifest_path_publish.returncode,
            "unsafe_manifest_path_publish_error": unsafe_manifest_path_publish.stderr.strip(),
            "current_pointer_after_unsafe_manifest_path_publish": current_pointer_after_unsafe_manifest_path_publish,
            "unsafe_pointer_path_reload": unsafe_pointer_path_reload,
            "health_after_unsafe_pointer_path_reload": health_after_unsafe_pointer_path_reload,
            "snapshot_check": snapshot_check_report,
            "snapshot_path": str(snapshot),
            "health": health,
            "response": response,
            "event_types": [event["event_type"] for event in events],
            "event_sequence_ids": [event["event_sequence_id"] for event in events],
            "routing_decision": routing_decision,
            "usage_event": usage,
            "checks": checks,
            "passed": all(checks.values()),
        }
    finally:
        provider_server.shutdown()
        provider_server.server_close()


def write_registry(path: Path, base_url: str, snapshot_version: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "projects": [
                    {
                        "id": "local",
                        "name": "Local Dogfood Project",
                        "status": "active",
                        "default_mode": "proxy",
                    }
                ],
                "api_keys": [
                    {
                        "id": "key_local_dev",
                        "project_id": "local",
                        "key_prefix": "local_",
                        "status": "active",
                    }
                ],
                "capabilities": [
                    {
                        "id": "network.public_ip.get",
                        "version": "0.1-migrated",
                        "name": "Public IP Lookup",
                    }
                ],
                "providers": [
                    {
                        "id": "ipify_public_ip_v1",
                        "capability_id": "network.public_ip.get",
                        "capability_version": "0.1-migrated",
                        "provider_id": "ipify",
                        "provider_version": "1.0.0",
                        "mapping_version": "1.0.0",
                        "tool_id": "get_public_ip",
                        "regions": ["global"],
                        "geo_affinity": "global",
                        "estimated_cost": 0,
                        "metadata": {"base_url": base_url},
                        "status": "active",
                    }
                ],
                "routing_policy": {
                    "strategy": "first",
                    "routing_mode": "deterministic",
                    "routing_seed": "control-plane-public-ip-v1",
                },
                "snapshot": {
                    "version": snapshot_version,
                    "fetched_at": "2026-05-30T00:00:00Z",
                    "ttl": "24h",
                    "source": "pull",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_invalid_registry(path: Path, base_url: str) -> Path:
    write_registry(path, base_url, "snapshot_control_plane_public_ip_v1")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["api_keys"][0]["project_id"] = "missing_project"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def force_snapshot_schema_version(path: Path, schema_version: str) -> None:
    data = read_json(path)
    metadata = data.setdefault("metadata", {})
    metadata["schema_version"] = schema_version
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def remove_snapshot_metadata_key(path: Path, key: str) -> None:
    data = read_json(path)
    metadata = data.setdefault("metadata", {})
    metadata.pop(key, None)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def force_manifest_registry_fingerprint(path: Path, registry_fingerprint: str) -> None:
    data = read_json(path)
    data["registry_fingerprint"] = registry_fingerprint
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def force_manifest_snapshot_file(path: Path, snapshot_file: str) -> None:
    data = read_json(path)
    data["snapshot_file"] = snapshot_file
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def force_current_snapshot_file(path: Path, snapshot_file: str) -> None:
    data = read_json(path)
    data["snapshot_file"] = snapshot_file
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def refresh_distribution_snapshot_digest(distribution_dir: Path, snapshot_version: str) -> None:
    snapshot_path = distribution_dir / "artifacts" / snapshot_version / "snapshot.json"
    digest = sha256_file(snapshot_path)
    manifest_path = distribution_dir / "artifacts" / snapshot_version / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["snapshot_digest"] = digest
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    current_path = distribution_dir / "current.json"
    current = read_json(current_path)
    if current.get("snapshot_version") == snapshot_version:
        current["snapshot_digest"] = digest
        current_path.write_text(json.dumps(current, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def append_file_whitespace(path: Path) -> None:
    data = path.read_bytes()
    path.write_bytes(data + b"\n")


def parse_json_report(completed: subprocess.CompletedProcess[str]) -> dict:
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        report = {
            "passed": False,
            "error": completed.stderr or completed.stdout or "invalid json report",
        }
    report["exit_code"] = completed.returncode
    return report


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json_allow_error(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
            body["status_code"] = response.status
            return body
    except HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8"))
        body["status_code"] = exc.code
        return body


def get_json(url: str) -> dict:
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_port(port: int) -> None:
    import socket
    import time

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Go data plane did not listen on port {port}")


if __name__ == "__main__":
    raise SystemExit(main())
