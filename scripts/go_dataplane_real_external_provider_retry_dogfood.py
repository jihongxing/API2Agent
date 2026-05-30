from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


HTTPBIN_500_URL = "https://httpbin.org/status/500"
HTTPBIN_IP_URL = "https://httpbin.org/ip"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dogfood Go Data Plane real external provider retry/failover.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".dogfood/go-dataplane-real-external-retry/report.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-real-external-retry-"))
    try:
        snapshot = write_snapshot(tmp / "snapshot.json")
        go_dir = Path("services/data-plane")
        exe_name = "api2agent-dataplane.exe" if os.name == "nt" else "api2agent-dataplane"
        exe_path = tmp / exe_name
        subprocess.run(["go", "build", "-o", str(exe_path), "./cmd/api2agent-dataplane"], cwd=go_dir, check=True)

        event_dir = tmp / "events"
        port = free_port()
        env = os.environ.copy()
        env["API2AGENT_DATAPLANE_ADDR"] = f"127.0.0.1:{port}"
        env["API2AGENT_EVENT_DIR"] = str(event_dir)
        env["API2AGENT_SNAPSHOT"] = str(snapshot)
        proc = subprocess.Popen([str(exe_path)], cwd=go_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            wait_for_port(port)
            response = post_json(
                f"http://127.0.0.1:{port}/v1/execute",
                {
                    "project_id": "local",
                    "capability_id": "network.public_ip.get",
                    "capability_version": "0.1-migrated",
                    "input": {},
                    "execution_mode": "proxy",
                    "timeout_budget_ms": 15000,
                },
            )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        events = read_jsonl(event_dir / "events.jsonl")
        report = build_report(response, events)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


def write_snapshot(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "snapshot_version": "snapshot_go_real_external_retry_v1",
                "snapshot_fetched_at": "2026-05-30T00:00:00Z",
                "snapshot_ttl": "24h",
                "snapshot_source": "pull",
                "capabilities": [
                    {
                        "id": "network.public_ip.get",
                        "version": "0.1-migrated",
                        "name": "Public IP Lookup",
                    }
                ],
                "providers": [
                    provider(
                        "httpbin_real_500_v1",
                        "httpbin",
                        HTTPBIN_500_URL,
                        "get_status_500",
                        0.003,
                    ),
                    provider(
                        "httpbin_ip_real_v1",
                        "httpbin",
                        HTTPBIN_IP_URL,
                        "get_public_ip",
                        0.002,
                    ),
                ],
                "routing_policy": {
                    "strategy": "first",
                    "routing_mode": "deterministic",
                    "routing_seed": "go-real-external-retry-v1",
                    "failover_policy": {
                        "enabled": True,
                        "max_attempts": 2,
                        "retry_on_error_types": ["PROVIDER_ERROR", "TIMEOUT"],
                        "retry_on_status_codes": [500, 502, 503, 504],
                        "attempt_timeout_policy": "fixed",
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def provider(candidate_id: str, provider_id: str, base_url: str, tool_id: str, estimated_cost: float) -> dict:
    return {
        "id": candidate_id,
        "capability_id": "network.public_ip.get",
        "capability_version": "0.1-migrated",
        "provider_id": provider_id,
        "provider_version": "1.0.0",
        "mapping_version": "1.0.0",
        "tool_id": tool_id,
        "regions": ["global"],
        "geo_affinity": "global",
        "estimated_cost": estimated_cost,
        "metadata": {"base_url": base_url},
    }


def build_report(response: dict, events: list[dict]) -> dict:
    routing_decision = next((event["record"] for event in events if event["event_type"] == "routing_decision"), {})
    usage_events = [event["record"] for event in events if event["event_type"] == "usage_event"]
    decision_log = next((event["record"] for event in events if event["event_type"] == "decision_log"), {})
    final_output = response.get("output") or {}
    ranked_provider_ids = routing_decision.get("ranked_provider_ids") or []
    attempts = [
        {
            "id": usage.get("id"),
            "candidate_id": ranked_provider_ids[index] if index < len(ranked_provider_ids) else None,
            "provider_id": usage.get("provider_id"),
            "provider_version": usage.get("provider_version"),
            "status_code": usage.get("status_code"),
            "success": usage.get("success"),
            "error_type": ((usage.get("error") or {}).get("error_type")),
            "attempt_index": (usage.get("request_metadata") or {}).get("attempt_index"),
        }
        for index, usage in enumerate(usage_events)
    ]
    checks = {
        "response_success": response.get("success") is True,
        "normalized_output_has_ip": isinstance(final_output.get("ip"), str) and bool(final_output.get("ip").strip()),
        "two_usage_events": len(usage_events) == 2,
        "first_attempt_failed": attempts[0]["success"] is False if len(attempts) > 0 else False,
        "first_attempt_provider_error": attempts[0]["error_type"] == "PROVIDER_ERROR" if len(attempts) > 0 else False,
        "second_attempt_succeeded": attempts[1]["success"] is True if len(attempts) > 1 else False,
        "decision_log_success": decision_log.get("outcome") == "success",
        "decision_log_references_both_attempts": len(decision_log.get("usage_event_ids") or []) == 2,
        "selected_fallback_provider": decision_log.get("selected_provider_id") == "httpbin_ip_real_v1",
        "event_order_is_graph": [event["event_type"] for event in events] == [
            "request_context",
            "routing_decision",
            "usage_event",
            "usage_event",
            "decision_log",
        ],
    }
    return {
        "dogfood": "go_dataplane_real_external_provider_retry",
        "capability_id": "network.public_ip.get",
        "providers": [
            {"id": "httpbin_real_500_v1", "provider_id": "httpbin", "base_url": HTTPBIN_500_URL},
            {"id": "httpbin_ip_real_v1", "provider_id": "httpbin", "base_url": HTTPBIN_IP_URL},
        ],
        "response": response,
        "final_output": final_output,
        "event_types": [event["event_type"] for event in events],
        "event_sequence_ids": [event["event_sequence_id"] for event in events],
        "attempts": attempts,
        "routing_decision": {
            "id": routing_decision.get("id"),
            "ranked_provider_ids": ranked_provider_ids,
            "selected_provider_id": routing_decision.get("selected_provider_id"),
            "failover_policy": routing_decision.get("failover_policy"),
        },
        "decision_log": {
            "id": decision_log.get("id"),
            "outcome": decision_log.get("outcome"),
            "selected_provider_id": decision_log.get("selected_provider_id"),
            "usage_event_ids": decision_log.get("usage_event_ids"),
            "routing_context": decision_log.get("routing_context"),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return json.loads(exc.read().decode("utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
