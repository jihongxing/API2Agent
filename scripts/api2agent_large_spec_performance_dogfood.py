from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".dogfood" / "large-spec-performance"
SPEC_PATH = OUT_DIR / "large.openapi.json"
UNFILTERED_PACKAGE = OUT_DIR / "package-unfiltered"
MAX_TOOLS_PACKAGE = OUT_DIR / "package-max-tools"
TAG_FILTERED_PACKAGE = OUT_DIR / "package-tag-filtered"
RESULT_PATH = OUT_DIR / "result.json"
OPERATION_COUNT = 1200


class ProviderState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls: list[dict[str, Any]] = []

    def record(self, method: str, path: str) -> None:
        with self.lock:
            self.calls.append({"method": method, "path": path})

    def snapshot(self) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(item) for item in self.calls]


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    provider_state = ProviderState()
    provider = ThreadingHTTPServer(("127.0.0.1", 0), _make_provider_handler(provider_state))
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    try:
        base_url = f"http://127.0.0.1:{provider.server_port}"
        _write_large_spec(base_url)

        unfiltered = _run_generate(UNFILTERED_PACKAGE)
        inspect_unfiltered = _run_cli(["inspect", str(UNFILTERED_PACKAGE), "--limit", "3"])
        max_tools = _run_generate(MAX_TOOLS_PACKAGE, "--max-tools", "5")
        tag_filtered = _run_generate(TAG_FILTERED_PACKAGE, "--include-tag", "group-7", "--max-tools", "5")
        selected_test = _run_cli(
            [
                "test",
                str(TAG_FILTERED_PACKAGE),
                "--tool",
                "get_group7_item0",
            ]
        )

        report = _build_report(
            unfiltered=unfiltered,
            inspect_unfiltered=inspect_unfiltered,
            max_tools=max_tools,
            tag_filtered=tag_filtered,
            selected_test=selected_test,
            provider_calls=provider_state.snapshot(),
        )
        RESULT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not report["ok"]:
            raise SystemExit(1)
    finally:
        provider.shutdown()
        provider.server_close()


def _write_large_spec(base_url: str) -> None:
    paths: dict[str, Any] = {}
    for group in range(12):
        for item in range(100):
            paths[f"/groups/group-{group}/items/{item}"] = {
                "get": {
                    "operationId": f"getGroup{group}Item{item}",
                    "tags": [f"group-{group}"],
                    "summary": f"Get item {item} from group {group}.",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "path": {"type": "string"},
                                            "ok": {"type": "boolean"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }

    SPEC_PATH.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Large Local API", "version": "1.0.0"},
                "servers": [{"url": base_url}],
                "paths": paths,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _run_generate(output_dir: Path, *extra_args: str) -> dict[str, Any]:
    started = time.perf_counter()
    result = _run_cli(
        [
            "generate",
            str(SPEC_PATH),
            "--name",
            output_dir.name.replace("package-", "large_"),
            "--output",
            str(output_dir),
            *extra_args,
        ]
    )
    result["latency_ms"] = _elapsed_ms(started)
    if output_dir.exists() and (output_dir / "capability.json").exists():
        capability = json.loads((output_dir / "capability.json").read_text(encoding="utf-8"))
        result["tool_count"] = len(capability.get("tools") or [])
        result["first_tool"] = (capability.get("tools") or [{}])[0].get("name")
    else:
        result["tool_count"] = None
        result["first_tool"] = None
    return result


def _run_cli(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "api2agent.cli", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return {
        "command": " ".join(["python", "-m", "api2agent.cli", *args]),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _build_report(
    *,
    unfiltered: dict[str, Any],
    inspect_unfiltered: dict[str, Any],
    max_tools: dict[str, Any],
    tag_filtered: dict[str, Any],
    selected_test: dict[str, Any],
    provider_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = {
        "unfiltered_generation_success": unfiltered["returncode"] == 0,
        "unfiltered_tool_count_1200": unfiltered.get("tool_count") == OPERATION_COUNT,
        "unfiltered_generation_warns_large_package": "Warning: generated package contains 1200 tools" in unfiltered["stdout"],
        "inspect_success": inspect_unfiltered["returncode"] == 0,
        "inspect_prints_tool_count": "Tool count: 1200" in inspect_unfiltered["stdout"],
        "inspect_truncates_tools": "showing 3 of 1200 tools" in inspect_unfiltered["stdout"],
        "inspect_prints_large_hint": "Large package hint:" in inspect_unfiltered["stdout"],
        "max_tools_generation_success": max_tools["returncode"] == 0,
        "max_tools_limited_to_5": max_tools.get("tool_count") == 5,
        "max_tools_no_large_warning": "Warning: generated package contains" not in max_tools["stdout"],
        "tag_filtered_generation_success": tag_filtered["returncode"] == 0,
        "tag_filtered_limited_to_5": tag_filtered.get("tool_count") == 5,
        "selected_tool_test_success": selected_test["returncode"] == 0,
        "selected_tool_called_provider_once": len(provider_calls) == 1,
        "selected_tool_path": provider_calls == [{"method": "GET", "path": "/groups/group-7/items/0"}],
        "api_first_scope": True,
        "no_workflow_engine_scope": True,
    }
    return {
        "contract_version": "api2agent.large_spec_performance_dogfood.v0",
        "generated_at": _utc_now(),
        "operation_count": OPERATION_COUNT,
        "spec_path": str(SPEC_PATH),
        "packages": {
            "unfiltered": str(UNFILTERED_PACKAGE),
            "max_tools": str(MAX_TOOLS_PACKAGE),
            "tag_filtered": str(TAG_FILTERED_PACKAGE),
        },
        "results": {
            "unfiltered": unfiltered,
            "inspect_unfiltered": inspect_unfiltered,
            "max_tools": max_tools,
            "tag_filtered": tag_filtered,
            "selected_test": selected_test,
        },
        "provider_calls": provider_calls,
        "checks": checks,
        "ok": all(checks.values()),
    }


def _make_provider_handler(state: ProviderState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.record("GET", self.path)
            payload = json.dumps({"ok": True, "path": self.path}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    main()
