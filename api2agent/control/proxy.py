from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import httpx
from pydantic import ValidationError

from api2agent.control.models import ProxyRequest, UsageEvent
from api2agent.control.storage import UsageStore

Forwarder = Callable[[str, str, dict[str, Any]], httpx.Response]


def execute_proxy_call(
    payload: dict[str, Any],
    store: UsageStore,
    quota: int | None = None,
    forwarder: Forwarder | None = None,
) -> tuple[int, dict[str, Any]]:
    try:
        proxy_request = ProxyRequest.model_validate(payload)
    except ValidationError as exc:
        return 400, {"ok": False, "error": {"type": "invalid_proxy_request", "details": exc.errors()}}

    request = proxy_request.request
    method = str(request.get("method") or "GET").upper()
    url = str(request.get("url") or "")
    path = urlparse(url).path or url

    if quota is not None and store.count(proxy_request.project_id) >= quota:
        event = UsageEvent(
            routing_decision_id=proxy_request.routing_decision_id,
            execution_mode="proxy",
            project_id=proxy_request.project_id,
            capability_id=proxy_request.capability_id,
            provider_id=proxy_request.provider_id,
            tool_id=proxy_request.tool_id,
            method=method,
            path=path,
            status_code=429,
            success=False,
            latency_ms=0.0,
            estimated_cost=0.0,
            error_type="quota_exceeded",
        )
        store.record(event)
        return 429, {
            "ok": False,
            "proxied": True,
            "usage_event_id": event.id,
            "error": {"type": "quota_exceeded", "message": "Project quota exceeded."},
        }

    forwarder = forwarder or _forward_request
    start = perf_counter()
    try:
        response = forwarder(
            method,
            url,
            {
                "headers": request.get("headers") or {},
                "params": request.get("params") or {},
                "json": request.get("json"),
                "timeout": request.get("timeout") or 20,
            },
        )
        latency_ms = (perf_counter() - start) * 1000
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text

        event = UsageEvent(
            routing_decision_id=proxy_request.routing_decision_id,
            execution_mode="proxy",
            project_id=proxy_request.project_id,
            capability_id=proxy_request.capability_id,
            provider_id=proxy_request.provider_id,
            tool_id=proxy_request.tool_id,
            method=method,
            path=path,
            status_code=response.status_code,
            success=response.is_success,
            latency_ms=latency_ms,
            estimated_cost=proxy_request.estimated_cost,
            error_type=None if response.is_success else "http_status",
        )
        store.record(event)
        result = {
            "ok": response.is_success,
            "proxied": True,
            "usage_event_id": event.id,
            "status_code": response.status_code,
            "body": body,
        }
        if not response.is_success:
            result["error"] = {"type": "http_status", "message": f"HTTP {response.status_code}"}
        return 200 if response.is_success else response.status_code, result
    except httpx.HTTPError as exc:
        latency_ms = (perf_counter() - start) * 1000
        event = UsageEvent(
            routing_decision_id=proxy_request.routing_decision_id,
            execution_mode="proxy",
            project_id=proxy_request.project_id,
            capability_id=proxy_request.capability_id,
            provider_id=proxy_request.provider_id,
            tool_id=proxy_request.tool_id,
            method=method,
            path=path,
            success=False,
            latency_ms=latency_ms,
            estimated_cost=0.0,
            error_type="http_error",
        )
        store.record(event)
        return 502, {
            "ok": False,
            "proxied": True,
            "usage_event_id": event.id,
            "error": {"type": "http_error", "message": str(exc)},
        }


def run_proxy_server(
    host: str,
    port: int,
    db_path: Path,
    api_key: str | None = None,
    quota: int | None = None,
) -> None:
    store = UsageStore(db_path)
    handler = _make_handler(store=store, api_key=api_key, quota=quota)
    server = ThreadingHTTPServer((host, port), handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _forward_request(method: str, url: str, options: dict[str, Any]) -> httpx.Response:
    return httpx.request(method, url, **options)


def _make_handler(store: UsageStore, api_key: str | None, quota: int | None):
    class ProxyHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path != "/v1/proxy/call":
                self._send_json(404, {"ok": False, "error": {"type": "not_found"}})
                return

            if not self._authorized():
                self._send_json(401, {"ok": False, "error": {"type": "unauthorized"}})
                return

            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": {"type": "invalid_json"}})
                return

            status, result = execute_proxy_call(payload, store=store, quota=quota)
            self._send_json(status, result)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/v1/usage":
                self._send_json(404, {"ok": False, "error": {"type": "not_found"}})
                return

            if not self._authorized():
                self._send_json(401, {"ok": False, "error": {"type": "unauthorized"}})
                return

            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [None])[0]
            summary = store.summarize(project_id)
            self._send_json(200, summary.model_dump(mode="json"))

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _authorized(self) -> bool:
            if not api_key:
                return True
            return self.headers.get("Authorization") == f"Bearer {api_key}"

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ProxyHandler
