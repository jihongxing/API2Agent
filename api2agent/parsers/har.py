import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

from api2agent.ir.models import AuthConfig, Capability, Parameter, RequestBody, ResponseShape, Tool
from api2agent.safety import classify_method
from api2agent.utils.naming import env_name, snake_name


BROWSER_HEADER_NAMES = {
    "accept",
    "accept-encoding",
    "accept-language",
    "cache-control",
    "connection",
    "cookie",
    "host",
    "origin",
    "referer",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "sec-fetch-dest",
    "sec-fetch-mode",
    "sec-fetch-site",
    "upgrade-insecure-requests",
    "user-agent",
}


def parse_har_file(path: Path, name: str | None = None) -> Capability:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    if not isinstance(document, dict):
        raise ValueError(f"HAR file must be an object: {path}")

    return parse_har(document, name=name, source=str(path))


def parse_har(
    document: dict[str, Any],
    name: str | None = None,
    source: str | None = None,
) -> Capability:
    entries = _entries(document)
    if not entries:
        raise ValueError("HAR file must include log.entries.")

    parsed_entries = [_entry_tool_data(entry) for entry in entries]
    parsed_entries = [entry for entry in parsed_entries if entry is not None]
    if not parsed_entries:
        raise ValueError("HAR file must include at least one http(s) request entry.")

    first = parsed_entries[0]
    capability_name = snake_name(name or _capability_name_from_host(first["host"]) or "har_capture")
    capability_auth = _first_auth(parsed_entries, capability_name)
    seen_names: set[str] = set()
    tools = [
        _tool_from_entry(entry, capability_name, capability_auth, seen_names)
        for entry in parsed_entries
    ]

    return Capability(
        name=capability_name,
        base_url=first["base_url"],
        auth=capability_auth,
        tools=tools,
        source=source,
    )


def count_har_entries_file(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"HAR file must be an object: {path}")
    return len(_entries(document))


def _entries(document: dict[str, Any]) -> list[Any]:
    log = document.get("log") or {}
    if not isinstance(log, dict):
        return []
    entries = log.get("entries") or []
    return entries if isinstance(entries, list) else []


def _entry_tool_data(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    request = entry.get("request") or {}
    if not isinstance(request, dict):
        return None

    raw_url = str(request.get("url") or "")
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    method = str(request.get("method") or "GET").upper()
    headers = _headers(request.get("headers") or [])
    response = entry.get("response") if isinstance(entry.get("response"), dict) else {}
    return {
        "method": method,
        "base_url": f"{parsed.scheme}://{parsed.netloc}",
        "host": parsed.netloc,
        "path": parsed.path or "/",
        "query": _query_items(request, parsed.query),
        "headers": headers,
        "body": _request_body(request.get("postData"), headers),
        "response": _response_shape(response),
    }


def _tool_from_entry(
    entry: dict[str, Any],
    capability_name: str,
    capability_auth: AuthConfig,
    seen_names: set[str],
) -> Tool:
    auth = _auth_from_headers(entry["headers"], capability_name)
    tool_auth = auth if auth.type != "none" and auth != capability_auth else None
    return Tool(
        name=_unique_tool_name(_tool_name(entry["method"], entry["path"], capability_name), seen_names),
        method=entry["method"],
        path=entry["path"],
        base_url=entry["base_url"],
        description=f"{entry['method']} {entry['path']} captured from HAR",
        tags=["har", _host_tag(entry["host"])],
        parameters=_parameters_from_query(entry["query"]) + _parameters_from_headers(entry["headers"]),
        request_body=entry["body"],
        responses=[entry["response"]] if entry["response"] is not None else [],
        safety=classify_method(entry["method"]),
        auth=tool_auth,
    )


def _headers(raw_headers: list[Any]) -> list[tuple[str, str]]:
    headers = []
    for header in raw_headers:
        if not isinstance(header, dict):
            continue
        name = str(header.get("name") or "").strip()
        if not name:
            continue
        headers.append((name, str(header.get("value") or "")))
    return headers


def _query_items(request: dict[str, Any], fallback_query: str) -> list[tuple[str, Any]]:
    query_items = []
    for item in request.get("queryString") or []:
        if isinstance(item, dict) and item.get("name"):
            query_items.append((str(item["name"]), item.get("value", "")))
    if query_items:
        return query_items
    return [(key, value) for key, value in parse_qsl(fallback_query, keep_blank_values=True)]


def _parameters_from_query(query_items: list[tuple[str, Any]]) -> list[Parameter]:
    return [
        Parameter(name=str(key), location="query", required=False, schema=_infer_schema(value, include_default=True))
        for key, value in query_items
    ]


def _parameters_from_headers(headers: list[tuple[str, str]]) -> list[Parameter]:
    parameters = []
    for name, value in headers:
        normalized = name.lower()
        if normalized in BROWSER_HEADER_NAMES or normalized == "content-type" or _is_auth_header(name, value):
            continue
        parameters.append(Parameter(name=name, location="header", required=False, schema=_infer_schema(value, True)))
    return parameters


def _request_body(post_data: Any, headers: list[tuple[str, str]]) -> RequestBody | None:
    if not isinstance(post_data, dict):
        return None

    content_type = str(post_data.get("mimeType") or _content_type(headers) or "application/json").split(";", 1)[0]
    if isinstance(post_data.get("params"), list) and content_type == "application/x-www-form-urlencoded":
        data = {
            str(item.get("name")): item.get("value", "")
            for item in post_data["params"]
            if isinstance(item, dict) and item.get("name")
        }
    else:
        data = _parse_body(post_data.get("text"))

    return RequestBody(required=True, content_type=content_type, schema=_infer_schema(data), example=data)


def _response_shape(response: Any) -> ResponseShape | None:
    if not isinstance(response, dict):
        return None
    content = response.get("content") if isinstance(response.get("content"), dict) else {}
    mime_type = str(content.get("mimeType") or "application/json").split(";", 1)[0]
    parsed_body = _parse_body(content.get("text"))
    schema = _infer_schema(parsed_body) if parsed_body is not None and parsed_body != "" else {}
    return ResponseShape(
        status_code=str(response.get("status") or "default"),
        description=str(response.get("statusText") or "HAR response"),
        content_type=mime_type,
        content_types=[mime_type],
        schema=schema,
        example=parsed_body,
    )


def _first_auth(entries: list[dict[str, Any]], capability_name: str) -> AuthConfig:
    for entry in entries:
        auth = _auth_from_headers(entry["headers"], capability_name)
        if auth.type != "none":
            return auth
    return AuthConfig(type="none")


def _auth_from_headers(headers: list[tuple[str, str]], capability_name: str) -> AuthConfig:
    for name, value in headers:
        if name.lower() == "authorization" and value.lower().startswith("bearer "):
            return AuthConfig(
                type="bearer",
                env=env_name(f"{capability_name}_token"),
                header="Authorization",
                location="authorization",
                name="Authorization",
                source="manual",
            )
        if name.lower() in {"x-api-key", "api-key"}:
            return AuthConfig(
                type="api_key",
                env=env_name(f"{capability_name}_api_key"),
                header=name,
                location="header",
                name=name,
                source="manual",
            )
    return AuthConfig(type="none")


def _is_auth_header(name: str, value: str) -> bool:
    normalized = name.lower()
    return normalized in {"authorization", "x-api-key", "api-key"} or (
        normalized == "authorization" and value.lower().startswith("bearer ")
    )


def _content_type(headers: list[tuple[str, str]]) -> str | None:
    for name, value in headers:
        if name.lower() == "content-type":
            return value
    return None


def _parse_body(raw_body: Any) -> Any:
    if raw_body is None:
        return None
    if not isinstance(raw_body, str):
        return raw_body
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body


def _infer_schema(value: object, include_default: bool = False) -> dict:
    if isinstance(value, dict):
        schema = {
            "type": "object",
            "properties": {key: _infer_schema(item) for key, item in value.items()},
        }
    elif isinstance(value, list):
        item_schema = _infer_schema(value[0]) if value else {}
        schema = {"type": "array", "items": item_schema}
    elif isinstance(value, bool):
        schema = {"type": "boolean"}
    elif isinstance(value, int):
        schema = {"type": "integer"}
    elif isinstance(value, float):
        schema = {"type": "number"}
    elif value is None:
        schema = {}
    else:
        schema = {"type": "string"}
    if include_default:
        schema["default"] = value
    return schema


def _tool_name(method: str, path: str, capability_name: str) -> str:
    normalized_path = path.strip("/")
    if not normalized_path:
        return snake_name(f"{method}_{capability_name}")
    return snake_name(f"{method}_{path}")


def _unique_tool_name(name: str, seen: set[str]) -> str:
    base = name
    index = 2
    while name in seen:
        name = f"{base}_{index}"
        index += 1
    seen.add(name)
    return name


def _host_tag(host: str) -> str:
    return snake_name(_capability_name_from_host(host))


def _capability_name_from_host(host: str) -> str:
    labels = [label for label in host.split(".") if label]
    if not labels:
        return "har_capture"
    if labels[0].lower() in {"api", "www"} and len(labels) > 1:
        return f"{labels[1]}_{labels[0]}"
    return labels[0]
