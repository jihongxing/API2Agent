import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

from api2agent.ir.models import AuthConfig, Capability, Parameter, RequestBody, Tool
from api2agent.safety import classify_method
from api2agent.utils.naming import env_name, snake_name


def parse_postman_file(path: Path, name: str | None = None) -> Capability:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    if not isinstance(document, dict):
        raise ValueError(f"Postman collection must be an object: {path}")

    return parse_postman_collection(document, name=name, source=str(path))


def parse_postman_collection(
    collection: dict[str, Any],
    name: str | None = None,
    source: str | None = None,
) -> Capability:
    info = collection.get("info") or {}
    capability_name = snake_name(name or info.get("name") or "postman_collection")
    variables = _collection_variables(collection.get("variable") or [])
    base_url = _base_url_from_variables(variables)
    collection_auth = _auth_from_postman(collection.get("auth"), capability_name)
    tools = _extract_tools(collection.get("item") or [], capability_name, collection_auth, variables)
    if not base_url and tools:
        base_url = tools[0].base_url or ""

    return Capability(
        name=capability_name,
        version=str(info.get("version") or "0.1.0"),
        base_url=base_url,
        auth=collection_auth,
        tools=tools,
        source=source,
    )


def count_postman_requests_file(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"Postman collection must be an object: {path}")
    return count_postman_requests(document)


def count_postman_requests(collection: dict[str, Any]) -> int:
    return sum(1 for _ in _iter_request_items(collection.get("item") or []))


def _extract_tools(
    items: list[Any],
    capability_name: str,
    collection_auth: AuthConfig,
    variables: dict[str, str],
) -> list[Tool]:
    tools: list[Tool] = []
    seen_names: set[str] = set()
    for item, folder_names in _iter_request_items(items):
        request = item.get("request") or {}
        if not isinstance(request, dict):
            continue
        method = str(request.get("method") or "GET").upper()
        url_parts = _url_parts(request.get("url"), variables)
        if not url_parts["path"]:
            continue
        item_name = str(item.get("name") or "")
        tool_name = _unique_tool_name(_tool_name(method, item_name, url_parts["path"], folder_names), seen_names)
        request_has_auth = "auth" in request
        auth = _auth_from_postman(request.get("auth"), capability_name)
        tool_auth = auth if request_has_auth else None
        parameters = _parameters_from_url_parts(url_parts) + _parameters_from_headers(request.get("header") or [])
        request_body = _request_body(request.get("body"))
        tools.append(
            Tool(
                name=tool_name,
                method=method,
                path=url_parts["path"],
                base_url=url_parts["base_url"],
                description=item_name or f"{method} {url_parts['path']}",
                tags=folder_names,
                parameters=parameters,
                request_body=request_body,
                safety=classify_method(method),
                auth=tool_auth,
            )
        )
    return tools


def _iter_request_items(items: list[Any], folders: list[str] | None = None):
    folders = folders or []
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("request"), dict):
            yield item, folders
            continue
        child_items = item.get("item")
        if isinstance(child_items, list):
            folder_name = str(item.get("name") or "").strip()
            next_folders = folders + ([folder_name] if folder_name else [])
            yield from _iter_request_items(child_items, next_folders)


def _url_parts(raw_url: Any, variables: dict[str, str]) -> dict[str, Any]:
    if isinstance(raw_url, str):
        resolved_url = _replace_variables(raw_url, variables)
        parsed = urlparse(resolved_url)
        return {
            "base_url": f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else "",
            "path": _postman_path(parsed.path or "/"),
            "query": parse_qsl(parsed.query, keep_blank_values=True),
        }

    if not isinstance(raw_url, dict):
        return {"base_url": "", "path": "", "query": []}

    raw = _replace_variables(str(raw_url.get("raw") or ""), variables)
    if raw:
        parsed = urlparse(raw)
        base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    else:
        base_url = ""
    host = raw_url.get("host") or []
    if not base_url and isinstance(host, list):
        host_value = ".".join(_replace_variables(str(part), variables).strip("/") for part in host)
        protocol = str(raw_url.get("protocol") or "https")
        if host_value and not host_value.startswith("{{"):
            base_url = f"{protocol}://{host_value}"

    path = raw_url.get("path") or []
    if isinstance(path, str):
        normalized_path = path
    elif isinstance(path, list):
        normalized_path = "/" + "/".join(str(part).strip("/") for part in path if str(part).strip("/"))
    else:
        normalized_path = urlparse(raw).path if raw else ""

    query = []
    for item in raw_url.get("query") or []:
        if not isinstance(item, dict) or item.get("disabled"):
            continue
        key = item.get("key")
        if key:
            query.append((str(key), item.get("value", "")))
    if not query and raw:
        query = parse_qsl(urlparse(raw).query, keep_blank_values=True)

    return {"base_url": base_url, "path": _postman_path(normalized_path or "/"), "query": query}


def _postman_path(path: str) -> str:
    parts = []
    for part in path.strip("/").split("/"):
        if not part:
            continue
        if part.startswith(":") and len(part) > 1:
            parts.append("{" + part[1:] + "}")
        else:
            parts.append(part)
    return "/" + "/".join(parts) if parts else "/"


def _parameters_from_url_parts(url_parts: dict[str, Any]) -> list[Parameter]:
    parameters = []
    for part in url_parts["path"].split("/"):
        if part.startswith("{") and part.endswith("}"):
            parameters.append(Parameter(name=part.strip("{}"), location="path", required=True, schema={"type": "string"}))
    for key, value in url_parts["query"]:
        parameters.append(Parameter(name=str(key), location="query", required=False, schema=_infer_schema(value, True)))
    return parameters


def _parameters_from_headers(headers: list[Any]) -> list[Parameter]:
    parameters = []
    for header in headers:
        if not isinstance(header, dict) or header.get("disabled"):
            continue
        name = str(header.get("key") or "").strip()
        value = header.get("value", "")
        if not name or name.lower() in {"authorization", "content-type"}:
            continue
        parameters.append(Parameter(name=name, location="header", required=False, schema=_infer_schema(value, True)))
    return parameters


def _request_body(body: Any) -> RequestBody | None:
    if not isinstance(body, dict):
        return None
    mode = body.get("mode")
    if mode == "raw":
        raw = body.get("raw")
        parsed = _parse_json_body(raw)
        return RequestBody(required=True, content_type=_raw_content_type(body), schema=_infer_schema(parsed), example=parsed)
    if mode == "urlencoded":
        data = {str(item.get("key")): item.get("value", "") for item in body.get("urlencoded") or [] if isinstance(item, dict) and item.get("key")}
        return RequestBody(required=True, content_type="application/x-www-form-urlencoded", schema=_infer_schema(data), example=data)
    if mode == "formdata":
        data = {str(item.get("key")): item.get("value", "") for item in body.get("formdata") or [] if isinstance(item, dict) and item.get("key")}
        return RequestBody(required=True, content_type="multipart/form-data", schema=_infer_schema(data), example=data)
    return None


def _raw_content_type(body: dict[str, Any]) -> str:
    options = body.get("options") or {}
    raw = options.get("raw") or {}
    language = str(raw.get("language") or "").lower()
    return "application/json" if language == "json" else "text/plain"


def _parse_json_body(raw: Any) -> Any:
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _auth_from_postman(auth: Any, capability_name: str) -> AuthConfig:
    if not isinstance(auth, dict):
        return AuthConfig(type="none")
    auth_type = auth.get("type")
    if auth_type == "bearer":
        return AuthConfig(
            type="bearer",
            env=env_name(f"{capability_name}_token"),
            header="Authorization",
            location="authorization",
            name="Authorization",
            source="manual",
        )
    if auth_type == "apikey":
        values = _auth_values(auth.get("apikey") or [])
        key_name = values.get("key") or "X-API-Key"
        location = values.get("in") or "header"
        return AuthConfig(
            type="api_key",
            env=env_name(f"{capability_name}_api_key"),
            header=key_name if location == "header" else None,
            location=location if location in {"header", "query"} else "header",
            name=key_name,
            source="manual",
        )
    if auth_type in {"noauth", None}:
        return AuthConfig(type="none")
    return AuthConfig(type="unknown", source="manual", unsupported_reason=f"Unsupported Postman auth type: {auth_type}")


def _auth_values(items: list[Any]) -> dict[str, str]:
    values = {}
    for item in items:
        if isinstance(item, dict) and item.get("key"):
            values[str(item["key"])] = str(item.get("value") or "")
    return values


def _collection_variables(items: list[Any]) -> dict[str, str]:
    variables = {}
    for item in items:
        if isinstance(item, dict) and item.get("key") and item.get("value") is not None:
            variables[str(item["key"])] = str(item["value"])
    return variables


def _base_url_from_variables(variables: dict[str, str]) -> str:
    for key in ["baseUrl", "base_url", "url"]:
        value = variables.get(key)
        if value and value.startswith(("http://", "https://")):
            return value
    return ""


def _replace_variables(value: str, variables: dict[str, str]) -> str:
    for key, replacement in variables.items():
        value = value.replace("{{" + key + "}}", replacement)
    return value


def _tool_name(method: str, item_name: str, path: str, folders: list[str]) -> str:
    if item_name:
        return snake_name(item_name)
    folder_prefix = "_".join(folders)
    return snake_name(f"{method}_{folder_prefix}_{path}" if folder_prefix else f"{method}_{path}")


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
        return {
            "type": "object",
            "properties": {key: _infer_schema(item) for key, item in value.items()},
        }
    if isinstance(value, list):
        item_schema = _infer_schema(value[0]) if value else {}
        return {"type": "array", "items": item_schema}
    if isinstance(value, bool):
        schema = {"type": "boolean"}
    elif isinstance(value, int):
        schema = {"type": "integer"}
    elif isinstance(value, float):
        schema = {"type": "number"}
    else:
        schema = {"type": "string"}
    if include_default:
        schema["default"] = value
    return schema
