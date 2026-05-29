from pathlib import Path
from typing import Any

import yaml

from api2agent.ir.models import AuthConfig, Capability, Parameter, RequestBody, ResponseShape, Tool
from api2agent.safety import classify_method
from api2agent.utils.naming import env_name, snake_name

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def parse_openapi_file(path: Path, name: str | None = None) -> Capability:
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    if not isinstance(document, dict):
        raise ValueError(f"OpenAPI document must be an object: {path}")

    return parse_openapi(document, name=name, source=str(path))


def parse_openapi(document: dict[str, Any], name: str | None = None, source: str | None = None) -> Capability:
    info = document.get("info") or {}
    capability_name = snake_name(name or info.get("title") or "api")
    base_url = _first_server_url(document)
    auth = _extract_auth(document, capability_name)
    tools = _extract_tools(document, base_url)

    return Capability(
        name=capability_name,
        version=str(info.get("version") or "0.1.0"),
        base_url=base_url,
        auth=auth,
        tools=tools,
        source=source,
    )


def _first_server_url(document: dict[str, Any]) -> str:
    return _first_server_url_from(document.get("servers") or "") or ""


def _first_server_url_from(servers: Any) -> str | None:
    if not isinstance(servers, list) or not servers:
        return None

    first = servers[0]
    if not isinstance(first, dict):
        return None

    url = str(first.get("url") or "")
    variables = first.get("variables") or {}
    if not isinstance(variables, dict):
        return url

    for name, raw_variable in variables.items():
        if not isinstance(raw_variable, dict):
            continue
        default = raw_variable.get("default")
        if default is not None:
            url = url.replace("{" + str(name) + "}", str(default))

    return url


def _extract_auth(document: dict[str, Any], capability_name: str) -> AuthConfig:
    schemes = ((document.get("components") or {}).get("securitySchemes") or {})
    for scheme in schemes.values():
        if not isinstance(scheme, dict):
            continue

        scheme_type = scheme.get("type")
        if scheme_type == "http" and str(scheme.get("scheme", "")).lower() == "bearer":
            return AuthConfig(
                type="bearer",
                env=env_name(f"{capability_name}_token"),
                header="Authorization",
                description=scheme.get("description"),
            )

        if scheme_type == "apiKey" and scheme.get("in") == "header":
            header_name = str(scheme.get("name") or "X-API-Key")
            return AuthConfig(
                type="api_key",
                env=env_name(f"{capability_name}_api_key"),
                header=header_name,
                description=scheme.get("description"),
            )

    return AuthConfig(type="none")


def _extract_tools(document: dict[str, Any], default_base_url: str) -> list[Tool]:
    tools: list[Tool] = []
    paths = document.get("paths") or {}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        path_parameters = _extract_parameters(path_item.get("parameters") or [], document)
        path_base_url = _first_server_url_from(path_item.get("servers"))

        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            operation = _resolve_refs(document, operation)
            operation_base_url = _first_server_url_from(operation.get("servers"))
            tool_base_url = operation_base_url or path_base_url
            operation_parameters = _extract_parameters(operation.get("parameters") or [], document)
            request_body = _extract_request_body(operation.get("requestBody"), document)
            responses = _extract_responses(operation.get("responses") or {}, document)
            operation_id = operation.get("operationId")
            tool_name = snake_name(operation_id or f"{method}_{path}")
            description = operation.get("summary") or operation.get("description") or f"{method.upper()} {path}"

            tools.append(
                Tool(
                    name=tool_name,
                    operation_id=str(operation_id) if operation_id else None,
                    method=method.upper(),
                    path=path,
                    base_url=tool_base_url if tool_base_url and tool_base_url != default_base_url else None,
                    description=str(description),
                    tags=[str(tag) for tag in operation.get("tags") or []],
                    parameters=path_parameters + operation_parameters,
                    request_body=request_body,
                    responses=responses,
                    safety=classify_method(method),
                )
            )

    return tools


def _extract_parameters(raw_parameters: list[Any], document: dict[str, Any]) -> list[Parameter]:
    parameters: list[Parameter] = []
    for raw in raw_parameters:
        raw = _resolve_refs(document, raw)
        if not isinstance(raw, dict):
            continue

        location = raw.get("in")
        if location not in {"path", "query", "header"}:
            continue

        parameters.append(
            Parameter(
                name=str(raw.get("name")),
                location=location,
                required=bool(raw.get("required")),
                schema=_resolve_schema(document, raw.get("schema") or {}),
                description=raw.get("description"),
            )
        )

    return parameters


def _extract_request_body(raw_body: Any, document: dict[str, Any]) -> RequestBody | None:
    raw_body = _resolve_refs(document, raw_body)
    if not isinstance(raw_body, dict):
        return None

    content = raw_body.get("content") or {}
    json_content = content.get("application/json")
    if not isinstance(json_content, dict):
        for _, candidate in content.items():
            if isinstance(candidate, dict):
                json_content = candidate
                break
    if not isinstance(json_content, dict):
        return None

    return RequestBody(
        required=bool(raw_body.get("required")),
        content_type="application/json" if "application/json" in content else next(iter(content.keys()), "application/json"),
        schema=_resolve_schema(document, json_content.get("schema") or {}),
    )


def _extract_responses(raw_responses: dict[str, Any], document: dict[str, Any]) -> list[ResponseShape]:
    responses: list[ResponseShape] = []
    for status_code, raw_response in raw_responses.items():
        raw_response = _resolve_refs(document, raw_response)
        if not isinstance(raw_response, dict):
            continue

        schema: dict[str, Any] = {}
        content = raw_response.get("content") or {}
        json_content = content.get("application/json")
        if isinstance(json_content, dict):
            schema = _resolve_schema(document, json_content.get("schema") or {})

        responses.append(
            ResponseShape(
                status_code=str(status_code),
                description=raw_response.get("description"),
                schema=schema,
            )
        )

    return responses


def _resolve_refs(document: dict[str, Any], value: Any, seen: frozenset[str] = frozenset()) -> Any:
    if isinstance(value, list):
        return [_resolve_refs(document, item, seen) for item in value]

    if not isinstance(value, dict):
        return value

    ref = value.get("$ref")
    if isinstance(ref, str):
        if ref in seen:
            return value
        resolved = _lookup_local_ref(document, ref)
        if resolved is None:
            return value

        merged = _resolve_refs(document, resolved, seen | {ref})
        if isinstance(merged, dict):
            siblings = {key: item for key, item in value.items() if key != "$ref"}
            if siblings:
                return {**merged, **_resolve_refs(document, siblings, seen | {ref})}
        return merged

    return {key: _resolve_refs(document, item, seen) for key, item in value.items()}


def _resolve_schema(document: dict[str, Any], raw_schema: Any) -> dict[str, Any]:
    resolved = _resolve_refs(document, raw_schema)
    normalized = _normalize_schema(resolved)
    return normalized if isinstance(normalized, dict) else {}


def _normalize_schema(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_normalize_schema(item) for item in schema]

    if not isinstance(schema, dict):
        return schema

    normalized = {key: _normalize_schema(value) for key, value in schema.items()}
    all_of = normalized.get("allOf")
    if isinstance(all_of, list):
        return _merge_all_of(normalized, all_of)

    return normalized


def _merge_all_of(schema: dict[str, Any], all_of: list[Any]) -> dict[str, Any]:
    result = {key: value for key, value in schema.items() if key != "allOf"}
    properties = dict(result.get("properties") or {})
    required = list(result.get("required") or [])
    can_merge_as_object = bool(properties) or result.get("type") == "object"

    for part in all_of:
        if not isinstance(part, dict):
            continue

        part_properties = part.get("properties")
        part_required = part.get("required")
        is_object_part = part.get("type") == "object" or isinstance(part_properties, dict)

        if is_object_part:
            can_merge_as_object = True
            properties.update(part_properties or {})
            for item in part_required or []:
                if item not in required:
                    required.append(item)

            for key, value in part.items():
                if key not in {"type", "properties", "required"} and key not in result:
                    result[key] = value
        else:
            result.setdefault("allOf", []).append(part)

    if can_merge_as_object:
        result["type"] = "object"
        result["properties"] = properties
        if required:
            result["required"] = required

    return result


def _lookup_local_ref(document: dict[str, Any], ref: str) -> Any | None:
    if not ref.startswith("#/"):
        return None

    current: Any = document
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
