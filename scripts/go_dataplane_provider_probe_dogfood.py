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


PROBES = [
    {
        "candidate_id": "httpbin_ip_probe_v1",
        "provider_id": "httpbin",
        "base_url": "https://httpbin.org/ip",
    },
    {
        "candidate_id": "ipify_probe_v1",
        "provider_id": "ipify",
        "base_url": "https://api.ipify.org",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Dogfood provider availability from the Go Data Plane runtime.")
    parser.add_argument("--output", type=Path, default=Path(".dogfood/go-dataplane-provider-probe/report.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="api2agent-go-provider-probe-"))
    try:
        go_dir = Path("services/data-plane")
        exe_name = "api2agent-dataplane.exe" if os.name == "nt" else "api2agent-dataplane"
        exe_path = tmp / exe_name
        subprocess.run(["go", "build", "-o", str(exe_path), "./cmd/api2agent-dataplane"], cwd=go_dir, check=True)

        results = []
        for probe in PROBES:
            event_dir = tmp / f"events-{probe['candidate_id']}"
            snapshot = write_snapshot(tmp / f"{probe['candidate_id']}.json", probe)
            result = run_probe(exe_path, go_dir, snapshot, event_dir, probe)
            results.append(result)

        reachable = [result for result in results if result["reachable"]]
        report = {
            "dogfood": "go_dataplane_provider_probe",
            "probe_count": len(results),
            "reachable_count": len(reachable),
            "results": results,
            "checks": {
                "at_least_one_provider_reachable": len(reachable) >= 1,
                "all_results_from_go_runtime": all(result.get("runtime") == "go_data_plane" for result in results),
                "all_results_have_events": all(result.get("event_count", 0) >= 4 for result in results),
            },
        }
        report["passed"] = all(report["checks"].values())
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


def write_snapshot(path: Path, probe: dict) -> Path:
    path.write_text(
        json.dumps(
            {
                "snapshot_version": f"snapshot_go_provider_probe_{probe['candidate_id']}",
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
                    {
                        "id": probe["candidate_id"],
                        "capability_id": "network.public_ip.get",
                        "capability_version": "0.1-migrated",
                        "provider_id": probe["provider_id"],
                        "provider_version": "1.0.0",
                        "mapping_version": "1.0.0",
                        "tool_id": "get_public_ip",
                        "regions": ["global"],
                        "geo_affinity": "global",
                        "estimated_cost": 0,
                        "metadata": {"base_url": probe["base_url"]},
                    }
                ],
                "routing_policy": {
                    "strategy": "first",
                    "routing_mode": "deterministic",
                    "routing_seed": f"go-provider-probe-{probe['candidate_id']}",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def run_probe(exe_path: Path, go_dir: Path, snapshot: Path, event_dir: Path, probe: dict) -> dict:
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
                "timeout_budget_ms": 12000,
            },
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    events = read_jsonl(event_dir / "events.jsonl")
    usage = next((event["record"] for event in events if event["event_type"] == "usage_event"), {})
    error = usage.get("error") or response.get("error") or {}
    return {
        "runtime": "go_data_plane",
        "candidate_id": probe["candidate_id"],
        "provider_id": probe["provider_id"],
        "base_url": probe["base_url"],
        "reachable": response.get("success") is True,
        "status_code": usage.get("status_code"),
        "latency_ms": (usage.get("latency") or {}).get("latency_ms"),
        "error_type": error.get("error_type"),
        "error_message": error.get("message"),
        "event_count": len(events),
    }


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=35) as response:
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
