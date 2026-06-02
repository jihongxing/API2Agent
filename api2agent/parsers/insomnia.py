import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

from api2agent.ir.models import AuthConfig, Capability, Parameter, RequestBody, Tool
from api2agent.safety import classify_method
from api2agent.utils.naming import env_name, snake_name


def parse_insomnia_file(path: Path, name: str | None = None) -> Capability:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    if not isinstance(document, dict):
        raise ValueError(f"Insomnia export must be an object: {path}")

    return parse_insomnia_export(document, name=name, source=str(path))


def parse_insomnia_export(
    document: dict[str, Any],
    name: str | None = None,
    source: str | None = None,
) -> Capability:
    resources = document.get("resources") or []
    if not isinstance(resources, list) or not resources:
        raise ValueError("Insomnia export must include resources.")

    workspace = _first_resource(resources, "workspace")
    capability_name = snake_name(name or (workspace or {}).get("name") or "insomnia_collection")
    variables = _environment_variables(resources)
    requests = [resource for resource in resources if isinstance(resource, dict) and resource.get("_type") == "request"]
    if not requests:
        raise ValueError("Insomnia export must include at least one request resource.")

    collection_auth = _first_auth(requests, capability_name)
    folders = _folder_names(resources)
    seen_names: set[str] = set()
    tools = [
        _tool_from_request(request, capability_name, collection_auth, variables, folders, seen_names)
        for request in requests
    ]
    tools = [tool for tool in tools if tool is not None]
    if not tools:
        raise ValueError("Insomnia export must include at least one http(s) request.")

    return Capability(
        name=capability_name,
        version=str(document.get("__export_format") or document.get("_type") or "0.1.0"),
        base_url=tools[0].base_url or "",
        auth=collection_auth,
        tools=tools,
        source=source,
    )


def count_insomnia_requests_file(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"Insomnia export must be an object: {path}")
    resources = document.get("resources") or []
    return sum(1 for resource in resources if isinstance(resource, dict) and resource.get("_type") == "request")


def _tool_from_request(
    request: dict[str, Any],
    capability_name: str,
    collection_auth: AuthConfig,
    variables: dict[str, Any],
    folders: dict[str, str],
    seen_names: set[str],
) -> Tool | None:
    raw_url = _replace_variables(str(request.get("url") or ""), variables)
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    method = str(request.get("method") or "GET").upper()
    path = _template_path(parsed.path or "/")
    auth = _auth_from_insomnia(request.get("authentication"), capability_name)
    tool_auth = auth if auth.type != "none" and auth != collection_auth else None
    folder = folders.get(str(request.get("parentId") or ""))
    tags = [folder] if folder else []

    return Tool(
        name=_unique_tool_name(snake_name(request.get("name") or f"{method}_{path}"), seen_names),
        method=method,
        path=path,
        base_url=f"{parsed.scheme}://{parsed.netloc}",
        description=str(request.get("description") or request.get("name") or f"{method} {path}"),
        tags=tags,
        parameters=_parameters_from_path(path) + _parameters_from_query(parsed.query) + _parameters_from_headers(request.get("headers") or []),
        request_body=_request_body(request.get("body")),
        safety=classify_method(method),
        auth=tool_auth,
    )


def _environment_variables(resources: list[Any]) -> dict[str, Any]:
    variables: dict[str, Any] = {}
    for resource in resources:
        if not isinstance(resource, dict) or resource.get("_type") != "environment":
            continue
        data = resource.get("data") or {}
        if isinstance(data, dict):
            variables.update(data)
    return variables


def _folder_names(resources: list[Any]) -> dict[str, str]:
    return {
        str(resource.get("_id")): str(resource.get("name"))
        for resource in resources
        if isinstance(resource, dict) and resource.get("_type") == "request_group" and resource.get("_id") and resource.get("name")
    }


def _first_resource(resources: list[Any], resource_type: str) -> dict[str, Any] | None:
    for resource in resources:
        if isinstance(resource, dict) and resource.get("_type") == resource_type:
            return resource
    return None


def _first_auth(requests: list[dict[str, Any]], capability_name: str) -> AuthConfig:
    for request in requests:
        auth = _auth_from_insomnia(request.get("authentication"), capability_name)
        if auth.type != "none":
            return auth
    return AuthConfig(type="none")


def _auth_from_insomnia(auth: Any, capability_name: str) -> AuthConfig:
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
    if auth_type in {"apikey", "apiKey"}:
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
    if auth_type in {"none", "noauth", None}:
        return AuthConfig(type="none")
    return AuthConfig(type="unknown", source="manual", unsupported_reason=f"Unsupported Insomnia auth type: {auth_type}")


def _parameters_from_path(path: str) -> list[Parameter]:
    return [
        Parameter(name=part.strip("{}"), location="path", required=True, schema={"type": "string"})
        for part in path.split("/")
        if part.startswith("{") and part.endswith("}")
    ]


def _parameters_from_query(query: str) -> list[Parameter]:
    return [
        Parameter(name=key, location="query", required=False, schema=_infer_schema(value, include_default=True))
        for key, value in parse_qsl(query, keep_blank_values=True)
    ]


def _parameters_from_headers(headers: list[Any]) -> list[Parameter]:
    parameters = []
    for header in headers:
        if not isinstance(header, dict) or header.get("disabled"):
            continue
        name = str(header.get("name") or "").strip()
        value = header.get("value", "")
        if not name or name.lower() in {"authorization", "content-type"}:
            continue
        parameters.append(Parameter(name=name, location="header", required=False, schema=_infer_schema(value, True)))
    return parameters


def _request_body(body: Any) -> RequestBody | None:
    if not isinstance(body, dict):
        return None
    mime_type = str(body.get("mimeType") or "application/json").split(";", 1)[0]
    parsed = _parse_body(body.get("text"))
    return RequestBody(required=True, content_type=mime_type, schema=_infer_schema(parsed), example=parsed)


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
    def replacement(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key.startswith("_."):
            key = key[2:].strip()
        return str(variables.get(key) or match.group(0))

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replacement, value)


def _template_path(path: str) -> str:
    return re.sub(r"\{\{\s*_?\.?([^}]+?)\s*\}\}", lambda match: "{" + snake_name(match.group(1).strip()) + "}", path)


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
