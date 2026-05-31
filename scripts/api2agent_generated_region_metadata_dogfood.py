from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api2agent.cli import app


OUT_DIR = ROOT / ".dogfood" / "generated-region-metadata"
PACKAGE_DIR = OUT_DIR / "package"
RESULT_PATH = OUT_DIR / "result.json"


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "generate",
            "--curl",
            "curl https://api.example.com/items",
            "--name",
            "example_items",
            "--provider-region",
            "us-east",
            "--output",
            str(PACKAGE_DIR),
        ],
    )
    if result.exit_code != 0:
        raise SystemExit(result.output)

    capability = json.loads((PACKAGE_DIR / "capability.json").read_text(encoding="utf-8"))
    payload = _capture_proxy_payload("get_items")
    report = {
        "contract_version": "api2agent.generated_region_metadata_dogfood.v0",
        "generated_at": _utc_now(),
        "package_dir": str(PACKAGE_DIR),
        "checks": {
            "capability_provider_region": capability.get("provider_region") == "us-east",
            "capability_provider_regions": capability.get("provider_regions") == ["us-east"],
            "proxy_payload_provider_region": payload.get("provider_region") == "us-east",
            "api_first_scope": True,
        },
        "capability": {
            "name": capability.get("name"),
            "provider_region": capability.get("provider_region"),
            "provider_regions": capability.get("provider_regions"),
            "tool_names": [tool.get("name") for tool in capability.get("tools", [])],
        },
        "proxy_payload": {
            "provider_id": payload.get("provider_id"),
            "provider_region": payload.get("provider_region"),
            "tool_id": payload.get("tool_id"),
            "request": {
                "method": (payload.get("request") or {}).get("method"),
                "url": (payload.get("request") or {}).get("url"),
            },
        },
    }
    report["ok"] = all(report["checks"].values())
    RESULT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(1)


def _capture_proxy_payload(tool_name: str) -> dict[str, Any]:
    module = _load_runner_module(PACKAGE_DIR)
    captured: dict[str, Any] = {}
    old_env = os.environ.copy()
    old_post = module.httpx.post
    try:
        os.environ.update(
            {
                "API2AGENT_PROXY_URL": "http://127.0.0.1:8765",
                "API2AGENT_PROJECT_ID": "local",
                "API2AGENT_PROVIDER_ID": "example_items",
            }
        )

        def fake_post(url: str, **kwargs):
            captured["url"] = url
            captured["payload"] = kwargs["json"]
            return _FakeResponse(200, {"ok": True, "proxied": True, "usage_event_id": "evt_region"})

        module.httpx.post = fake_post
        result = module.execute_tool(tool_name, {})
        if not result.get("ok"):
            raise RuntimeError(f"runner proxy execution failed: {result}")
        return captured["payload"]
    finally:
        module.httpx.post = old_post
        os.environ.clear()
        os.environ.update(old_env)


def _load_runner_module(package_dir: Path):
    module_name = f"api2agent_region_runner_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, package_dir / "runner.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load runner module from {package_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self._body = body
        self.is_success = 200 <= status_code < 300
        self.text = json.dumps(body, ensure_ascii=False)

    def json(self) -> Any:
        return self._body


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    main()
