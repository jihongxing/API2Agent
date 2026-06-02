import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from api2agent.ir.models import AuthConfig, Capability, RequestBody, ResponseShape, Tool
from api2agent.utils.naming import env_name, snake_name


def parse_graphql_file(path: Path, name: str | None = None) -> Capability:
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    if not isinstance(manifest, dict):
        raise ValueError(f"GraphQL manifest must be an object: {path}")

    return parse_graphql_manifest(manifest, name=name, source=str(path))


def parse_graphql_manifest(
    manifest: dict[str, Any],
    name: str | None = None,
    source: str | None = None,
) -> Capability:
    endpoint = manifest.get("endpoint") or {}
    if not isinstance(endpoint, dict):
        raise ValueError("GraphQL manifest endpoint must be an object.")

    raw_url = str(endpoint.get("url") or manifest.get("url") or "")
    if not raw_url.startswith(("http://", "https://")):
        raise ValueError("GraphQL manifest endpoint.url must be an http(s) URL.")

    parsed = urlparse(raw_url)
    capability_name = snake_name(name or manifest.get("name") or _capability_name_from_host(parsed.netloc))
    operations = manifest.get("operations") or []
    if not isinstance(operations, list) or not operations:
        raise ValueError("GraphQL manifest must include at least one operation.")

    tools = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("GraphQL manifest operations must be objects.")
        tools.append(_tool_from_operation(operation, endpoint, parsed.path or "/"))

    return Capability(
        name=capability_name,
        version=str(manifest.get("version") or "0.1.0"),
        base_url=f"{parsed.scheme}://{parsed.netloc}",
        auth=_auth_from_manifest(manifest.get("auth"), capability_name),
        tools=tools,
        source=source,
    )


def _tool_from_operation(operation: dict[str, Any], endpoint: dict[str, Any], path: str) -> Tool:
    query = str(operation.get("query") or "")
    if not query.strip():
        raise ValueError("GraphQL operation query must be a non-empty string.")
    operation_name = operation.get("operation_name") or operation.get("operationName")
    operation_kind = str(operation.get("type") or _operation_kind(query) or "query").lower()
    variables_schema = operation.get("variables_schema") or operation.get("input_schema") or {"type": "object"}
    if not isinstance(variables_schema, dict):
        variables_schema = {"type": "object"}
    schema = dict(variables_schema)
    schema["x-api2agent-graphql"] = {
        "query": query,
        "operationName": operation_name,
    }

    response_schema = operation.get("response_schema") or operation.get("output_schema")
    responses = []
    if isinstance(response_schema, dict):
        responses.append(
            ResponseShape(
                status_code="200",
                description="GraphQL operation response.",
                content_type="application/json",
                content_types=["application/json"],
                schema=response_schema,
            )
        )

    return Tool(
        name=snake_name(operation.get("name") or operation_name or _operation_tool_name(query)),
        method=str(endpoint.get("method") or "POST").upper(),
        path=path,
        description=str(operation.get("description") or f"GraphQL {operation_kind} operation"),
        tags=["graphql", operation_kind],
        request_body=RequestBody(
            required=True,
            content_type="application/json",
            schema=schema,
            example=operation.get("example"),
        ),
        responses=responses,
        safety="read" if operation_kind == "query" else "write",
    )


def _operation_kind(query: str) -> str | None:
    stripped = query.strip()
    if not stripped:
        return None
    first = stripped.split(None, 1)[0].lower()
    return first if first in {"query", "mutation", "subscription"} else "query"


def _operation_tool_name(query: str) -> str:
    stripped = query.strip()
    parts = stripped.replace("{", " ").split()
    if len(parts) >= 2 and parts[0].lower() in {"query", "mutation", "subscription"}:
        return parts[1].split("(", 1)[0]
    return "graphql_operation"


def _auth_from_manifest(auth: Any, capability_name: str) -> AuthConfig:
    if not isinstance(auth, dict):
        return AuthConfig(type="none")
    auth_type = auth.get("type")
    if auth_type == "bearer":
        return AuthConfig(
            type="bearer",
            env=str(auth.get("env") or env_name(f"{capability_name}_token")),
            header="Authorization",
            location="authorization",
            name="Authorization",
            source="manual",
        )
    if auth_type == "api_key":
        location = str(auth.get("location") or "header")
        key_name = str(auth.get("name") or ("X-API-Key" if location == "header" else "api_key"))
        return AuthConfig(
            type="api_key",
            env=str(auth.get("env") or env_name(f"{capability_name}_api_key")),
            header=key_name if location == "header" else None,
            location=location if location in {"header", "query"} else "header",
            name=key_name,
            source="manual",
        )
    if auth_type in {"none", None}:
        return AuthConfig(type="none")
    return AuthConfig(type="unknown", source="manual", unsupported_reason=f"Unsupported GraphQL auth type: {auth_type}")


def _capability_name_from_host(host: str) -> str:
    labels = [label for label in host.split(".") if label]
    if not labels:
        return "graphql_api"
    if labels[0].lower() in {"api", "graphql"} and len(labels) > 1:
        return f"{labels[1]}_graphql"
    return f"{labels[0]}_graphql"
