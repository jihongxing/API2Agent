import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

from api2agent.ir.models import AuthConfig, Capability, Parameter, RequestBody, Tool
from api2agent.safety import classify_method
from api2agent.utils.naming import env_name, snake_name


def parse_bruno_file(path: Path, name: str | None = None) -> Capability:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    if not isinstance(document, dict):
        raise ValueError(f"Bruno collection export must be an object: {path}")

    return parse_bruno_collection(document, name=name, source=str(path))


def parse_bruno_collection(
    collection: dict[str, Any],
    name: str | None = None,
    source: str | None = None,
) -> Capability:
    capability_name = snake_name(name or collection.get("name") or collection.get("collection", {}).get("name") or "bruno_collection")
    variables = _variables(collection)
    items = collection.get("items") or collection.get("requests") or collection.get("children") or []
    if not isinstance(items, list) or not items:
        raise ValueError("Bruno collection export must include items or requests.")

    requests = list(_iter_requests(items))
    if not requests:
        raise ValueError("Bruno collection export must include at least one request.")

    collection_auth = _first_auth(requests, capability_name)
    seen_names: set[str] = set()
    tools = [
        _tool_from_item(item, folder_names, capability_name, collection_auth, variables, seen_names)
        for item, folder_names in requests
    ]
    tools = [tool for tool in tools if tool is not None]
    if not tools:
        raise ValueError("Bruno collection export must include at least one http(s) request.")

    return Capability(
        name=capability_name,
        version=str(collection.get("version") or "0.1.0"),
        base_url=tools[0].base_url or "",
        auth=collection_auth,
        tools=tools,
        source=source,
    )


def count_bruno_requests_file(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"Bruno collection export must be an object: {path}")
    items = document.get("items") or document.get("requests") or document.get("children") or []
    return sum(1 for _ in _iter_requests(items if isinstance(items, list) else []))


def _iter_requests(items: list[Any], folders: list[str] | None = None):
    folders = folders or []
    for item in items:
        if not isinstance(item, dict):
            continue
        request = item.get("request") or item
        if isinstance(request, dict) and (request.get("url") or request.get("method")):
            yield item, folders
            continue
        child_items = item.get("items") or item.get("children") or []
        if isinstance(child_items, list):
            folder_name = str(item.get("name") or "").strip()
            yield from _iter_requests(child_items, folders + ([folder_name] if folder_name else []))


def _tool_from_item(
    item: dict[str, Any],
    folders: list[str],
    capability_name: str,
    collection_auth: AuthConfig,
    variables: dict[str, Any],
    seen_names: set[str],
) -> Tool | None:
    request = item.get("request") if isinstance(item.get("request"), dict) else item
    raw_url = _replace_variables(str(request.get("url") or ""), variables)
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    method = str(request.get("method") or "GET").upper()
    path = parsed.path or "/"
    auth = _auth_from_bruno(request.get("auth") or item.get("auth"), capability_name)
    tool_auth = auth if auth.type != "none" and auth != collection_auth else None
    item_name = str(item.get("name") or request.get("name") or "")

    return Tool(
        name=_unique_tool_name(snake_name(item_name or f"{method}_{path}"), seen_names),
        method=method,
        path=path,
        base_url=f"{parsed.scheme}://{parsed.netloc}",
        description=item_name or f"{method} {path}",
        tags=folders,
        parameters=_parameters_from_query(parsed.query, request.get("params") or request.get("query")) + _parameters_from_headers(request.get("headers") or []),
        request_body=_request_body(request.get("body")),
        safety=classify_method(method),
        auth=tool_auth,
    )


def _variables(collection: dict[str, Any]) -> dict[str, Any]:
    variables: dict[str, Any] = {}
    for source in [collection.get("variables"), collection.get("vars"), collection.get("environment")]:
        if isinstance(source, dict):
            variables.update(source)
            continue
        if isinstance(source, list):
            for item in source:
                if isinstance(item, dict) and item.get("name"):
                    variables[str(item["name"])] = item.get("value", "")
                elif isinstance(item, dict) and item.get("key"):
                    variables[str(item["key"])] = item.get("value", "")
    return variables


def _first_auth(requests: list[tuple[dict[str, Any], list[str]]], capability_name: str) -> AuthConfig:
    for item, _folders in requests:
        request = item.get("request") if isinstance(item.get("request"), dict) else item
        auth = _auth_from_bruno(request.get("auth") or item.get("auth"), capability_name)
        if auth.type != "none":
            return auth
    return AuthConfig(type="none")


def _auth_from_bruno(auth: Any, capability_name: str) -> AuthConfig:
    if not isinstance(auth, dict):
        return AuthConfig(type="none")
    auth_type = str(auth.get("type") or "").lower()
    if auth_type == "bearer":
        return AuthConfig(
            type="bearer",
            env=env_name(f"{capability_name}_token"),
            header="Authorization",
            location="authorization",
            name="Authorization",
            source="manual",
        )
    if auth_type in {"apikey", "api_key", "api-key"}:
        key_name = str(auth.get("key") or auth.get("name") or "X-API-Key")
        location = str(auth.get("in") or auth.get("location") or "header")
        return AuthConfig(
            type="api_key",
            env=env_name(f"{capability_name}_api_key"),
            header=key_name if location == "header" else None,
            location=location if location in {"header", "query"} else "header",
            name=key_name,
            source="manual",
        )
    if auth_type in {"", "none", "noauth"}:
        return AuthConfig(type="none")
    return AuthConfig(type="unknown", source="manual", unsupported_reason=f"Unsupported Bruno auth type: {auth_type}")


def _parameters_from_query(raw_query: str, query_items: Any) -> list[Parameter]:
    items: list[tuple[str, Any]] = []
    if isinstance(query_items, list):
        for item in query_items:
            if isinstance(item, dict) and item.get("name") and not item.get("disabled"):
                items.append((str(item["name"]), item.get("value", "")))
            elif isinstance(item, dict) and item.get("key") and not item.get("disabled"):
                items.append((str(item["key"]), item.get("value", "")))
    elif isinstance(query_items, dict):
        items.extend((str(key), value) for key, value in query_items.items())
    if not items:
        items = [(key, value) for key, value in parse_qsl(raw_query, keep_blank_values=True)]
    return [Parameter(name=key, location="query", required=False, schema=_infer_schema(value, True)) for key, value in items]


def _parameters_from_headers(headers: Any) -> list[Parameter]:
    parameters = []
    for name, value in _header_items(headers):
        if not name or name.lower() in {"authorization", "content-type"}:
            continue
        parameters.append(Parameter(name=name, location="header", required=False, schema=_infer_schema(value, True)))
    return parameters


def _header_items(headers: Any) -> list[tuple[str, Any]]:
    if isinstance(headers, dict):
        return [(str(key), value) for key, value in headers.items()]
    if isinstance(headers, list):
        items = []
        for header in headers:
            if isinstance(header, dict) and not header.get("disabled"):
                name = header.get("name") or header.get("key")
                if name:
                    items.append((str(name), header.get("value", "")))
        return items
    return []


def _request_body(body: Any) -> RequestBody | None:
    if body is None:
        return None
    content_type = "application/json"
    raw = body
    if isinstance(body, dict):
        content_type = str(body.get("mimeType") or body.get("contentType") or body.get("mode") or "application/json")
        raw = body.get("text") if "text" in body else body.get("json") if "json" in body else body.get("data")
    parsed = _parse_body(raw)
    return RequestBody(required=True, content_type=content_type.split(";", 1)[0], schema=_infer_schema(parsed), example=parsed)


def _parse_body(raw_body: Any) -> Any:
    if raw_body is None:
        return None
    if not isinstance(raw_body, str):
        return raw_body
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body


def _replace_variables(value: str, variables: dict[str, Any]) -> str:
    for key, replacement in variables.items():
        value = value.replace("{{" + key + "}}", str(replacement))
    return value


def _unique_tool_name(name: str, seen: set[str]) -> str:
    base = name
    index = 2
    while name in seen:
        name = f"{base}_{index}"
        index += 1
    seen.add(name)
    return name


def _infer_schema(value: object, include_default: bool = False) -> dict:
    if isinstance(value, dict):
        schema = {"type": "object", "properties": {key: _infer_schema(item) for key, item in value.items()}}
    elif isinstance(value, list):
        schema = {"type": "array", "items": _infer_schema(value[0]) if value else {}}
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
