from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".dogfood" / "curl-naming-residual-review"
RESULT_PATH = OUT_DIR / "result.json"


@dataclass(frozen=True)
class NamingCase:
    case_id: str
    curl: str
    expected_capability: str
    expected_tool: str
    name: str | None = None
    expected_auth_env: str | None = None


CASES = [
    NamingCase(
        case_id="generic_api_subdomain_bearer",
        curl="curl https://api.github.com/rate_limit -H 'Authorization: Bearer token'",
        expected_capability="github_api",
        expected_tool="get_rate_limit",
        expected_auth_env="GITHUB_API_TOKEN",
    ),
    NamingCase(
        case_id="root_path_inferred_host_intent",
        curl="curl https://api.ipify.org?format=json",
        expected_capability="ipify_api",
        expected_tool="get_ipify_api",
    ),
    NamingCase(
        case_id="explicit_name_still_wins",
        curl="curl https://api.ipify.org?format=json",
        name="ipify_public_ip",
        expected_capability="ipify_public_ip",
        expected_tool="get_ipify_public_ip",
    ),
    NamingCase(
        case_id="non_root_path_stays_path_based",
        curl="curl https://api.example.com/items?format=json",
        expected_capability="example_api",
        expected_tool="get_items",
    ),
]


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    results = [_run_case(case) for case in CASES]
    checks = {
        "all_cases_generated": all(item["generation"]["returncode"] == 0 for item in results),
        "capability_names_match": all(item["actual"]["capability"] == item["expected"]["capability"] for item in results),
        "tool_names_match": all(item["actual"]["tool"] == item["expected"]["tool"] for item in results),
        "auth_envs_match": all(item["actual"]["auth_env"] == item["expected"]["auth_env"] for item in results),
        "explicit_name_still_wins": _case_ok(results, "explicit_name_still_wins"),
        "non_root_path_stays_path_based": _case_ok(results, "non_root_path_stays_path_based"),
        "api_first_scope": True,
        "no_workflow_engine_scope": True,
    }
    report = {
        "contract_version": "api2agent.curl_naming_residual_review.v0",
        "generated_at": _utc_now(),
        "output_dir": str(OUT_DIR),
        "cases": results,
        "checks": checks,
        "ok": all(checks.values()),
    }
    RESULT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(1)


def _run_case(case: NamingCase) -> dict[str, Any]:
    package_dir = OUT_DIR / case.case_id / "package"
    command = [
        sys.executable,
        "-m",
        "api2agent.cli",
        "generate",
        "--curl",
        case.curl,
        "--output",
        str(package_dir),
    ]
    if case.name:
        command.extend(["--name", case.name])
    completed = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    capability: dict[str, Any] = {}
    if (package_dir / "capability.json").exists():
        capability = json.loads((package_dir / "capability.json").read_text(encoding="utf-8"))

    tool = (capability.get("tools") or [{}])[0]
    auth = capability.get("auth") or {}
    return {
        "case_id": case.case_id,
        "generation": {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
        "expected": {
            "capability": case.expected_capability,
            "tool": case.expected_tool,
            "auth_env": case.expected_auth_env,
        },
        "actual": {
            "capability": capability.get("name"),
            "tool": tool.get("name"),
            "auth_env": auth.get("env"),
        },
    }


def _case_ok(results: list[dict[str, Any]], case_id: str) -> bool:
    item = next(result for result in results if result["case_id"] == case_id)
    return item["actual"] == item["expected"]


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    main()
