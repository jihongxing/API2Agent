from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from api2agent.ir.models import AuthConfig, Capability, RequestBody, ResponseShape, Tool
from api2agent.safety import classify_method
from api2agent.utils.naming import env_name, snake_name


def parse_asyncapi_file(path: Path, name: str | None = None) -> Capability:
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    if not isinstance(document, dict):
        raise ValueError(f"AsyncAPI document must be an object: {path}")

    return parse_asyncapi(document, name=name, source=str(path))


def parse_asyncapi(document: dict[str, Any], name: str | None = None, source: str | None = None) -> Capability:
    info = document.get("info") or {}
    capability_name = snake_name(name or info.get("title") or "asyncapi_webhook")
    servers = _servers(document)
    base_url = _first_http_server_url(servers)
    auth = _auth_from_security(document, capability_name)
    tools = _tools_from_channels(document, base_url)

    if not tools:
        raise ValueError("AsyncAPI document must include at least one callable HTTP channel operation.")

    return Capability(
        name=capability_name,
        version=str(info.get("version") or "0.1.0"),
        base_url=base_url,
        auth=auth,
        tools=tools,
        source=source,
    )


def count_asyncapi_http_operations_file(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"AsyncAPI document must be an object: {path}")
    return len(_tools_from_channels(document, _first_http_server_url(_servers(document))))


def _tools_from_channels(document: dict[str, Any], default_base_url: str) -> list[Tool]:
    channels = document.get("channels") or {}
    if not isinstance(channels, dict):
        return []

    tools: list[Tool] = []
    seen: set[str] = set()
    for channel_name, raw_channel in channels.items():
        if not isinstance(raw_channel, dict):
            continue
        path = _channel_path(str(raw_channel.get("address") or channel_name))
        for action in ["publish", "send"]:
            operation = raw_channel.get(action)
            if not isinstance(operation, dict):
                continue
            method = _http_method(operation, raw_channel)
            if method is None:
                continue
            message = _message(operation.get("message"))
            schema = _payload_schema(message)
            tool_name = _unique_tool_name(snake_name(operation.get("operationId") or f"{method}_{path}"), seen)
            tools.append(
                Tool(
                    name=tool_name,
                    operation_id=str(operation.get("operationId") or tool_name),
                    method=method,
                    path=path,
                    base_url=_operation_base_url(operation, raw_channel, default_base_url),
                    description=str(operation.get("summary") or operation.get("description") or f"{method} webhook {path}"),
                    tags=["asyncapi", action],
                    request_body=RequestBody(
                        required=True,
                        content_type=_content_type(operation, message),
                        schema=schema,
                        example=_payload_example(message),
                    ),
                    responses=[
                        ResponseShape(
                            status_code=str(_success_status(operation)),
                            description="AsyncAPI HTTP operation response.",
                            content_type="application/json",
                            content_types=["application/json"],
                            schema={},
                        )
                    ],
                    safety=classify_method(method),
                )
            )
    return tools


def _servers(document: dict[str, Any]) -> dict[str, Any]:
    servers = document.get("servers") or {}
    return servers if isinstance(servers, dict) else {}


def _first_http_server_url(servers: dict[str, Any]) -> str:
    for server in servers.values():
        if not isinstance(server, dict):
            continue
        protocol = str(server.get("protocol") or "").lower()
        url = _resolve_server_url(server)
        if protocol in {"http", "https"} and url:
            return url
        if url.startswith(("http://", "https://")):
            return url
    return ""


def _resolve_server_url(server: dict[str, Any]) -> str:
    raw_url = str(server.get("url") or server.get("host") or "")
    protocol = str(server.get("protocol") or "").lower()
    variables = server.get("variables") or {}
    if isinstance(variables, dict):
        for name, variable in variables.items():
            if isinstance(variable, dict) and variable.get("default") is not None:
                raw_url = raw_url.replace("{" + str(name) + "}", str(variable["default"]))
    if raw_url and not raw_url.startswith(("http://", "https://")) and protocol in {"http", "https"}:
        raw_url = f"{protocol}://{raw_url}"
    return raw_url.rstrip("/")


def _operation_base_url(operation: dict[str, Any], channel: dict[str, Any], default_base_url: str) -> str:
    for holder in [operation, channel]:
        servers = holder.get("servers") if isinstance(holder, dict) else None
        if isinstance(servers, list) and servers:
            server = servers[0]
            if isinstance(server, dict):
                url = _resolve_server_url(server)
                if url:
                    return url
    return default_base_url


def _http_method(operation: dict[str, Any], channel: dict[str, Any]) -> str | None:
    for holder in [operation, channel]:
        bindings = holder.get("bindings") if isinstance(holder, dict) else None
        http = bindings.get("http") if isinstance(bindings, dict) else None
        if isinstance(http, dict):
            method = http.get("method") or http.get("type")
            if method:
                return str(method).upper()
    if _operation_base_url(operation, channel, ""):
        return "POST"
    return None


def _message(raw_message: Any) -> dict[str, Any]:
    if isinstance(raw_message, dict):
        if "oneOf" in raw_message and isinstance(raw_message["oneOf"], list) and raw_message["oneOf"]:
            first = raw_message["oneOf"][0]
            return first if isinstance(first, dict) else {}
        return raw_message
    return {}


def _payload_schema(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload")
    return payload if isinstance(payload, dict) else {"type": "object"}


def _payload_example(message: dict[str, Any]) -> Any:
    for key in ["example", "examples"]:
        value = message.get(key)
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict) and "payload" in first:
                return first["payload"]
            return first
        if isinstance(value, dict) and "payload" in value:
            return value["payload"]
        if value is not None and key == "example":
            return value
    return None


def _content_type(operation: dict[str, Any], message: dict[str, Any]) -> str:
    for value in [
        operation.get("contentType"),
        message.get("contentType"),
    ]:
        if value:
            return str(value)
    return "application/json"


def _success_status(operation: dict[str, Any]) -> str:
    bindings = operation.get("bindings") or {}
    http = bindings.get("http") if isinstance(bindings, dict) else {}
    if isinstance(http, dict) and http.get("successStatusCode"):
        return str(http["successStatusCode"])
    return "200"


def _channel_path(address: str) -> str:
    if address.startswith(("http://", "https://")):
        parsed = urlparse(address)
        return parsed.path or "/"
    return "/" + address.strip("/")


def _auth_from_security(document: dict[str, Any], capability_name: str) -> AuthConfig:
    schemes = document.get("components", {}).get("securitySchemes", {}) if isinstance(document.get("components"), dict) else {}
    if not isinstance(schemes, dict):
        return AuthConfig(type="none")
    for scheme_name, scheme in schemes.items():
        if not isinstance(scheme, dict):
            continue
        scheme_type = str(scheme.get("type") or "").lower()
        if scheme_type == "http" and str(scheme.get("scheme") or "").lower() == "bearer":
            return AuthConfig(
                type="bearer",
                env=env_name(f"{capability_name}_token"),
                header="Authorization",
                location="authorization",
                name="Authorization",
                scheme_name=str(scheme_name),
                source="manual",
            )
        if scheme_type == "apikey":
            location = str(scheme.get("in") or "header")
            key_name = str(scheme.get("name") or "X-API-Key")
            return AuthConfig(
                type="api_key",
                env=env_name(f"{capability_name}_api_key"),
                header=key_name if location == "header" else None,
                location=location if location in {"header", "query"} else "header",
                name=key_name,
                scheme_name=str(scheme_name),
                source="manual",
            )
    return AuthConfig(type="none")


def _unique_tool_name(name: str, seen: set[str]) -> str:
    base = name
    index = 2
    while name in seen:
        name = f"{base}_{index}"
        index += 1
    seen.add(name)
    return name
