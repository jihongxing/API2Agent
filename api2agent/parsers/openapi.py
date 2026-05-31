from pathlib import Path
from typing import Any

import yaml

from api2agent.filters import ToolFilter
from api2agent.ir.models import (
    AuthConfig,
    Capability,
    Parameter,
    RequestBody,
    ResponseShape,
    ServerConfig,
    SecurityAlternative,
    SecurityRequirements,
    ServerVariable,
    Tool,
)
from api2agent.safety import classify_method
from api2agent.utils.naming import env_name, snake_name

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def parse_openapi_file(path: Path, name: str | None = None, filters: ToolFilter | None = None) -> Capability:
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    if not isinstance(document, dict):
        raise ValueError(f"OpenAPI document must be an object: {path}")

    return parse_openapi(document, name=name, source=str(path), filters=filters)


def parse_openapi(
    document: dict[str, Any],
    name: str | None = None,
    source: str | None = None,
    filters: ToolFilter | None = None,
) -> Capability:
    info = document.get("info") or {}
    capability_name = snake_name(name or info.get("title") or "api")
    document_servers = _server_configs_from(document.get("servers"), source="document")
    base_url = document_servers[0].resolved_url if document_servers else ""
    schemes = _extract_security_schemes(document, capability_name)
    security_requirements = _security_requirements_for(document.get("security"), schemes)
    auth = _extract_auth(document, capability_name, schemes, security_requirements)
    tools = _extract_tools(document, base_url, document_servers, auth, schemes, filters)

    return Capability(
        name=capability_name,
        version=str(info.get("version") or "0.1.0"),
        base_url=base_url,
        auth=auth,
        security_requirements=security_requirements,
        servers=document_servers,
        tools=tools,
        source=source,
    )


def count_openapi_operations_file(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    if not isinstance(document, dict):
        raise ValueError(f"OpenAPI document must be an object: {path}")

    return count_openapi_operations(document)


def count_openapi_operations(document: dict[str, Any]) -> int:
    count = 0
    paths = document.get("paths") or {}
    if not isinstance(paths, dict):
        return 0

    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method in HTTP_METHODS and isinstance(operation, dict):
                count += 1
    return count


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


def _server_configs_from(
    servers: Any,
    *,
    source: str,
    path: str | None = None,
    operation_id: str | None = None,
) -> list[ServerConfig]:
    if not isinstance(servers, list):
        return []

    configs: list[ServerConfig] = []
    for raw_server in servers:
        if not isinstance(raw_server, dict):
            continue
        raw_url = str(raw_server.get("url") or "")
        variables = _server_variables(raw_server.get("variables") or {})
        resolved_url = _resolve_server_url(raw_url, variables)
        configs.append(
            ServerConfig(
                url=raw_url,
                resolved_url=resolved_url,
                description=raw_server.get("description"),
                variables=variables,
                source=source,
                path=path,
                operation_id=operation_id,
                profile_hints=_server_profile_hints(raw_url, raw_server.get("description"), variables),
                is_relative=_is_relative_server_url(raw_url),
            )
        )
    return configs


def _server_variables(raw_variables: dict[str, Any]) -> dict[str, ServerVariable]:
    variables: dict[str, ServerVariable] = {}
    if not isinstance(raw_variables, dict):
        return variables
    for name, raw_variable in raw_variables.items():
        if not isinstance(raw_variable, dict):
            continue
        variables[str(name)] = ServerVariable(
            default=str(raw_variable["default"]) if raw_variable.get("default") is not None else None,
            enum=[str(item) for item in raw_variable.get("enum") or []],
            description=raw_variable.get("description"),
        )
    return variables


def _resolve_server_url(raw_url: str, variables: dict[str, ServerVariable]) -> str:
    url = raw_url
    for name, variable in variables.items():
        if variable.default is not None:
            url = url.replace("{" + name + "}", variable.default)
    return url


def _server_profile_hints(raw_url: str, description: Any, variables: dict[str, ServerVariable]) -> list[str]:
    text = f"{raw_url} {description or ''}".lower()
    hints: list[str] = []
    if "sandbox" in text:
        hints.append("sandbox")
    if any(marker in text for marker in ["staging", "stage", "test"]):
        hints.append("staging")
    if any(marker in text for marker in ["prod", "production"]) or "api." in text:
        hints.append("production")
    if "admin" in text:
        hints.append("admin")
    if "region" in text or any(name.lower() == "region" for name in variables):
        hints.append("regional")
    if _is_relative_server_url(raw_url):
        hints.append("relative")
    return sorted(set(hints))


def _is_relative_server_url(raw_url: str) -> bool:
    return bool(raw_url) and not raw_url.startswith(("http://", "https://"))


def _extract_security_schemes(document: dict[str, Any], capability_name: str) -> dict[str, AuthConfig]:
    schemes = ((document.get("components") or {}).get("securitySchemes") or {})
    auth_by_scheme: dict[str, AuthConfig] = {}
    for scheme_name, scheme in schemes.items():
        if not isinstance(scheme, dict):
            continue

        scheme_type = scheme.get("type")
        if scheme_type == "http" and str(scheme.get("scheme", "")).lower() == "bearer":
            auth_by_scheme[str(scheme_name)] = AuthConfig(
                type="bearer",
                env=env_name(f"{capability_name}_token"),
                header="Authorization",
                location="authorization",
                name="Authorization",
                scheme_name=str(scheme_name),
                source="openapi",
                description=scheme.get("description"),
            )
            continue

        if scheme_type == "apiKey" and scheme.get("in") in {"header", "query", "cookie"}:
            location = str(scheme.get("in"))
            credential_name = str(scheme.get("name") or ("X-API-Key" if location == "header" else "api_key"))
            auth_by_scheme[str(scheme_name)] = AuthConfig(
                type="api_key",
                env=env_name(f"{capability_name}_api_key"),
                header=credential_name if location == "header" else None,
                location=location,
                name=credential_name,
                scheme_name=str(scheme_name),
                source="openapi",
                description=scheme.get("description"),
            )
            continue

        scopes = _oauth_scopes(scheme)
        auth_by_scheme[str(scheme_name)] = AuthConfig(
            type="unknown",
            env=None,
            header=None,
            location="unknown",
            scheme_name=str(scheme_name),
            scopes=scopes,
            source="openapi",
            unsupported_reason=_unsupported_auth_reason(scheme),
            description=scheme.get("description"),
        )

    return auth_by_scheme


def _extract_auth(
    document: dict[str, Any],
    capability_name: str,
    schemes: dict[str, AuthConfig] | None = None,
    security_requirements: SecurityRequirements | None = None,
) -> AuthConfig:
    schemes = schemes if schemes is not None else _extract_security_schemes(document, capability_name)
    document_auth = _select_auth(security_requirements)
    if document_auth is not None:
        return document_auth

    for auth in schemes.values():
        if auth.type != "unknown":
            return auth
    return AuthConfig(type="none")


def _extract_tools(
    document: dict[str, Any],
    default_base_url: str,
    document_servers: list[ServerConfig],
    capability_auth: AuthConfig,
    schemes: dict[str, AuthConfig],
    filters: ToolFilter | None = None,
) -> list[Tool]:
    tools: list[Tool] = []
    paths = document.get("paths") or {}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        path_parameters = _extract_parameters(path_item.get("parameters") or [], document)
        path_servers = _server_configs_from(path_item.get("servers"), source="path", path=str(path))

        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            if not _matches_operation_filters(path, method, operation, filters):
                continue

            operation = _resolve_refs(document, operation)
            operation_id = operation.get("operationId")
            operation_servers = _server_configs_from(
                operation.get("servers"),
                source="operation",
                path=str(path),
                operation_id=str(operation_id) if operation_id else None,
            )
            selected_servers = operation_servers or path_servers or document_servers
            selected_server = selected_servers[0] if selected_servers else None
            tool_base_url = selected_server.resolved_url if selected_server else None
            operation_parameters = _extract_parameters(operation.get("parameters") or [], document)
            request_body = _extract_request_body(operation.get("requestBody"), document)
            responses = _extract_responses(operation.get("responses") or {}, document)
            tool_name = snake_name(operation_id or f"{method}_{path}")
            description = operation.get("summary") or operation.get("description") or f"{method.upper()} {path}"
            tool_auth = _tool_auth_override(operation, capability_auth, schemes)
            tool_security_requirements = (
                _security_requirements_for(operation.get("security"), schemes)
                if "security" in operation
                else None
            )

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
                    auth=tool_auth,
                    security_requirements=tool_security_requirements,
                    servers=selected_servers,
                    server_source=selected_server.source if selected_server else None,
                )
            )
            if filters is not None and filters.max_tools is not None and len(tools) >= filters.max_tools:
                return tools

    return tools


def _matches_operation_filters(
    path: str,
    method: str,
    operation: dict[str, Any],
    filters: ToolFilter | None,
) -> bool:
    if filters is None or filters.is_empty:
        return True

    tags = {str(tag).lower() for tag in operation.get("tags") or []}
    if filters.include_tags and not any(tag.lower() in tags for tag in filters.include_tags):
        return False

    if filters.include_paths and not any(_path_matches(path, pattern) for pattern in filters.include_paths):
        return False

    if filters.include_operations:
        operation_id = operation.get("operationId")
        tool_name = snake_name(str(operation_id) if operation_id else f"{method}_{path}")
        operation_names = {tool_name}
        if operation_id:
            operation_names.add(str(operation_id))
            operation_names.add(snake_name(str(operation_id)))
        if not any(operation in operation_names or snake_name(operation) in operation_names for operation in filters.include_operations):
            return False

    return True


def _path_matches(path: str, pattern: str) -> bool:
    from fnmatch import fnmatch

    if pattern == path:
        return True
    if any(marker in pattern for marker in "*?[]"):
        return fnmatch(path, pattern)
    return pattern in path


def _tool_auth_override(
    operation: dict[str, Any],
    capability_auth: AuthConfig,
    schemes: dict[str, AuthConfig],
) -> AuthConfig | None:
    if "security" not in operation:
        return None

    operation_auth = _select_auth(_security_requirements_for(operation.get("security"), schemes))
    if operation_auth is None:
        return None
    if operation_auth == capability_auth:
        return None
    return operation_auth


def _security_requirements_for(raw_security: Any, schemes: dict[str, AuthConfig]) -> SecurityRequirements | None:
    if raw_security is None:
        return None
    if raw_security == []:
        return SecurityRequirements(alternatives=[])
    if not isinstance(raw_security, list):
        return None

    alternatives: list[SecurityAlternative] = []
    for requirement in raw_security:
        if not isinstance(requirement, dict):
            continue
        if not requirement:
            alternatives.append(SecurityAlternative(anonymous=True))
            continue

        requirement_schemes: list[AuthConfig] = []
        for scheme_name, raw_scopes in requirement.items():
            scheme_key = str(scheme_name)
            auth = schemes.get(scheme_key) or AuthConfig(
                type="unknown",
                location="unknown",
                scheme_name=scheme_key,
                source="openapi",
                unsupported_reason="security scheme is referenced but not defined",
            )
            scopes = [str(scope) for scope in raw_scopes] if isinstance(raw_scopes, list) else []
            requirement_schemes.append(auth.model_copy(update={"scopes": scopes or auth.scopes}))
        alternatives.append(SecurityAlternative(schemes=requirement_schemes))

    return SecurityRequirements(alternatives=alternatives)


def _select_auth(requirements: SecurityRequirements | None) -> AuthConfig | None:
    if requirements is None:
        return None
    if not requirements.alternatives:
        return AuthConfig(type="none")
    if any(alternative.anonymous for alternative in requirements.alternatives):
        return AuthConfig(type="none")

    for alternative in requirements.alternatives:
        if alternative.schemes and all(_is_supported_auth(auth) for auth in alternative.schemes):
            if len(alternative.schemes) == 1:
                return alternative.schemes[0]
            primary = alternative.schemes[0]
            return primary.model_copy(
                update={
                    "credentials": [
                        scheme.model_dump(mode="json", by_alias=True, exclude_none=True)
                        for scheme in alternative.schemes
                    ]
                }
            )

    return AuthConfig(
        type="unknown",
        location="unknown",
        source="openapi",
        unsupported_reason="no supported executable security requirement alternative",
        credentials=[
            scheme.model_dump(mode="json", by_alias=True, exclude_none=True)
            for alternative in requirements.alternatives
            for scheme in alternative.schemes
        ],
    )


def _is_supported_auth(auth: AuthConfig) -> bool:
    return auth.type in {"bearer", "api_key"} and auth.location in {
        "authorization",
        "header",
        "query",
        "cookie",
    }


def _oauth_scopes(scheme: dict[str, Any]) -> list[str]:
    if scheme.get("type") != "oauth2":
        return []
    scopes: list[str] = []
    flows = scheme.get("flows") or {}
    if not isinstance(flows, dict):
        return scopes
    for flow in flows.values():
        if not isinstance(flow, dict):
            continue
        raw_scopes = flow.get("scopes") or {}
        if isinstance(raw_scopes, dict):
            scopes.extend(str(scope) for scope in raw_scopes)
    return sorted(set(scopes))


def _unsupported_auth_reason(scheme: dict[str, Any]) -> str:
    scheme_type = scheme.get("type")
    if scheme_type in {"oauth2", "openIdConnect"}:
        return "metadata-only OAuth/OpenID scheme"
    return f"unsupported security scheme type: {scheme_type or 'unknown'}"


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
                example=_extract_example_value(raw.get("example")),
                examples=_extract_examples(raw.get("examples")),
            )
        )

    return parameters


def _extract_request_body(raw_body: Any, document: dict[str, Any]) -> RequestBody | None:
    raw_body = _resolve_refs(document, raw_body)
    if not isinstance(raw_body, dict):
        return None

    content = raw_body.get("content") or {}
    content_type, json_content, _content_types = _select_content(content)
    if not content_type or not isinstance(json_content, dict):
        return None

    return RequestBody(
        required=bool(raw_body.get("required")),
        content_type=content_type,
        schema=_resolve_schema(document, json_content.get("schema") or {}),
        example=_extract_example_value(json_content.get("example")),
        examples=_extract_examples(json_content.get("examples")),
    )


def _extract_responses(raw_responses: dict[str, Any], document: dict[str, Any]) -> list[ResponseShape]:
    responses: list[ResponseShape] = []
    for status_code, raw_response in raw_responses.items():
        raw_response = _resolve_refs(document, raw_response)
        if not isinstance(raw_response, dict):
            continue

        content = raw_response.get("content") or {}
        content_type, selected_content, content_types = _select_content(content)
        schema: dict[str, Any] = {}
        example: Any | None = None
        examples: list[Any] = []
        if isinstance(selected_content, dict):
            schema = _resolve_schema(document, selected_content.get("schema") or {})
            example = _extract_example_value(selected_content.get("example"))
            examples = _extract_examples(selected_content.get("examples"))

        responses.append(
            ResponseShape(
                status_code=str(status_code),
                description=raw_response.get("description"),
                content_type=content_type,
                content_types=content_types,
                schema=schema,
                example=example,
                examples=examples,
            )
        )

    return responses


def _select_content(content: Any) -> tuple[str | None, dict[str, Any] | None, list[str]]:
    if not isinstance(content, dict) or not content:
        return None, None, []

    content_types = [str(key) for key in content]
    if isinstance(content.get("application/json"), dict):
        return "application/json", content["application/json"], content_types

    for content_type, candidate in content.items():
        if isinstance(candidate, dict):
            return str(content_type), candidate, content_types
    return None, None, content_types


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


def _extract_example_value(raw_example: Any) -> Any | None:
    return raw_example if raw_example is not None else None


def _extract_examples(raw_examples: Any) -> list[Any]:
    if raw_examples is None:
        return []
    if isinstance(raw_examples, list):
        return [item for item in raw_examples if item is not None]
    if isinstance(raw_examples, dict):
        examples: list[Any] = []
        for raw in raw_examples.values():
            if isinstance(raw, dict) and "value" in raw:
                examples.append(raw["value"])
            elif raw is not None:
                examples.append(raw)
        return examples
    return [raw_examples]


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
