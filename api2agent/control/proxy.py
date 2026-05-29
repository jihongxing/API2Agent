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
from api2agent.credentials.config import load_credential_config
from api2agent.credentials.models import (
    CredentialDefinition,
    CredentialInjectionPatch,
    CredentialResolutionRequest,
    ResolvedCredential,
)
from api2agent.credentials.resolver import LocalCredentialResolver

Forwarder = Callable[[str, str, dict[str, Any]], httpx.Response]


def execute_proxy_call(
    payload: dict[str, Any],
    store: UsageStore,
    quota: int | None = None,
    forwarder: Forwarder | None = None,
    credential_resolver: LocalCredentialResolver | None = None,
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
            request_metadata=_safe_request_metadata(
                method,
                url,
                request,
                credential_metadata=_safe_credential_metadata(proxy_request.credential),
            ),
            credential_reference=_credential_reference(request, proxy_request.credential),
            provider_runtime_reference="proxy:http",
        )
        store.record(event)
        return 429, {
            "ok": False,
            "proxied": True,
            "usage_event_id": event.id,
            "error": {"type": "quota_exceeded", "message": "Project quota exceeded."},
        }

    resolved_credential = _resolve_proxy_credential(
        proxy_request,
        credential_resolver=credential_resolver or LocalCredentialResolver(),
    )
    if not resolved_credential.resolved:
        event = UsageEvent(
            routing_decision_id=proxy_request.routing_decision_id,
            execution_mode="proxy",
            project_id=proxy_request.project_id,
            capability_id=proxy_request.capability_id,
            provider_id=proxy_request.provider_id,
            tool_id=proxy_request.tool_id,
            method=method,
            path=path,
            status_code=401,
            success=False,
            latency_ms=0.0,
            estimated_cost=0.0,
            error_type=resolved_credential.error_type or "credential_resolution_failed",
            request_metadata=_safe_request_metadata(
                method,
                url,
                request,
                credential_metadata=_safe_credential_metadata(
                    proxy_request.credential,
                    resolved_credential=resolved_credential,
                ),
            ),
            credential_reference=resolved_credential.credential_reference,
            provider_runtime_reference="proxy:http",
        )
        store.record(event)
        return 401, {
            "ok": False,
            "proxied": True,
            "usage_event_id": event.id,
            "error": {
                "type": resolved_credential.error_type or "credential_resolution_failed",
                "message": resolved_credential.error_message or "Proxy credential resolution failed.",
            },
        }

    forwarder = forwarder or _forward_request
    start = perf_counter()
    try:
        forward_options = {
            "headers": dict(request.get("headers") or {}),
            "params": dict(request.get("params") or {}),
            "json": dict(request["json"]) if isinstance(request.get("json"), dict) else request.get("json"),
            "timeout": request.get("timeout") or 20,
        }
        _apply_credential_injection(forward_options, resolved_credential.injection_patch)
        response = forwarder(
            method,
            url,
            forward_options,
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
            request_metadata=_safe_request_metadata(
                method,
                url,
                request,
                credential_metadata=_safe_credential_metadata(
                    proxy_request.credential,
                    resolved_credential=resolved_credential,
                ),
            ),
            credential_reference=_credential_reference(
                request,
                proxy_request.credential,
                resolved_credential=resolved_credential,
            ),
            provider_runtime_reference="proxy:http",
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
            request_metadata=_safe_request_metadata(
                method,
                url,
                request,
                credential_metadata=_safe_credential_metadata(
                    proxy_request.credential,
                    resolved_credential=resolved_credential,
                ),
            ),
            credential_reference=_credential_reference(
                request,
                proxy_request.credential,
                resolved_credential=resolved_credential,
            ),
            provider_runtime_reference="proxy:http",
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
    credential_config: Path | None = None,
) -> None:
    store = UsageStore(db_path)
    credentials = load_credential_config(credential_config) if credential_config else []
    credential_resolver = LocalCredentialResolver(credentials)
    handler = _make_handler(
        store=store,
        api_key=api_key,
        quota=quota,
        credential_resolver=credential_resolver,
    )
    server = ThreadingHTTPServer((host, port), handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _forward_request(method: str, url: str, options: dict[str, Any]) -> httpx.Response:
    return httpx.request(method, url, **options)


def _safe_request_metadata(
    method: str,
    url: str,
    request: dict[str, Any],
    credential_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "method": method,
        "url": url,
        "params": request.get("params") or {},
        "json": request.get("json"),
        "headers": _redact_headers(request.get("headers") or {}),
    }
    if credential_metadata is not None:
        metadata["credential"] = credential_metadata
    return metadata


def _redact_headers(headers: dict[str, Any]) -> dict[str, Any]:
    sensitive = {"authorization", "x-api-key", "api-key", "cookie", "set-cookie"}
    return {
        key: "[REDACTED]" if str(key).lower() in sensitive else value
        for key, value in headers.items()
    }


def _resolve_proxy_credential(
    proxy_request: ProxyRequest,
    credential_resolver: LocalCredentialResolver,
) -> ResolvedCredential:
    if not proxy_request.credential:
        resolved = credential_resolver.resolve(
            CredentialResolutionRequest(
                project_id=proxy_request.project_id,
                capability_id=proxy_request.capability_id,
                provider_id=proxy_request.provider_id,
                tool_id=proxy_request.tool_id,
                auth_type="none",
                injection_mode="none",
            )
        )
        request_credential_reference = _credential_reference(proxy_request.request)
        if resolved.credential_reference == "none" and request_credential_reference:
            return ResolvedCredential(
                resolved=True,
                credential_reference=request_credential_reference,
                redacted_metadata={"source": "request_headers"},
            )
        return resolved

    try:
        credential = CredentialDefinition.model_validate(proxy_request.credential)
    except ValidationError as exc:
        return ResolvedCredential(
            resolved=False,
            credential_reference="invalid",
            error_type="invalid_credential",
            error_message=f"Invalid proxy credential: {exc}",
            redacted_metadata=_safe_credential_metadata(proxy_request.credential) or {},
        )

    request = CredentialResolutionRequest(
        project_id=proxy_request.project_id,
        capability_id=proxy_request.capability_id,
        provider_id=proxy_request.provider_id,
        tool_id=proxy_request.tool_id,
        auth_type=credential.auth_type,
        injection_mode=credential.injection_mode,
        injection_name=credential.injection_name,
        credential=credential,
    )
    return credential_resolver.resolve(request)


def _apply_credential_injection(options: dict[str, Any], patch: CredentialInjectionPatch) -> None:
    if patch.headers:
        options.setdefault("headers", {}).update(patch.headers)
    if patch.query:
        options.setdefault("params", {}).update(patch.query)
    if patch.body:
        existing = options.get("json")
        if isinstance(existing, dict):
            existing.update(patch.body)
        else:
            options["json"] = dict(patch.body)


def _safe_credential_metadata(
    credential: dict[str, Any] | None,
    resolved_credential: ResolvedCredential | None = None,
) -> dict[str, Any] | None:
    if resolved_credential is not None and resolved_credential.redacted_metadata:
        return dict(resolved_credential.redacted_metadata)
    if credential is None:
        return None
    return {key: value for key, value in credential.items() if key != "secret_value"}


def _credential_reference(
    request: dict[str, Any],
    credential: dict[str, Any] | None = None,
    resolved_credential: ResolvedCredential | None = None,
) -> str | None:
    if resolved_credential is not None:
        return resolved_credential.credential_reference
    if credential is not None:
        safe_metadata = _safe_credential_metadata(credential) or {}
        if safe_metadata.get("source") == "env":
            return f"env:{safe_metadata.get('secret_ref')}"
        if safe_metadata.get("source") in {"config", "inline"}:
            return f"{safe_metadata.get('source')}:{safe_metadata.get('credential_id')}"
    headers = request.get("headers") or {}
    for key in headers:
        if str(key).lower() in {"authorization", "x-api-key", "api-key"}:
            return f"header:{key}"
    return None


def _make_handler(
    store: UsageStore,
    api_key: str | None,
    quota: int | None,
    credential_resolver: LocalCredentialResolver | None = None,
):
    credential_resolver = credential_resolver or LocalCredentialResolver()

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

            status, result = execute_proxy_call(
                payload,
                store=store,
                quota=quota,
                credential_resolver=credential_resolver,
            )
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
