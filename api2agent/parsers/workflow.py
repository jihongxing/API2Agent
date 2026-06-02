import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

from api2agent.ir.models import AuthConfig, Capability, Parameter, RequestBody, ResponseShape, Tool
from api2agent.safety import classify_method
from api2agent.utils.naming import env_name, snake_name


def parse_workflow_file(path: Path, name: str | None = None) -> Capability:
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    if not isinstance(manifest, dict):
        raise ValueError(f"Workflow manifest must be an object: {path}")

    return parse_workflow_manifest(manifest, name=name, source=str(path))


def parse_workflow_manifest(
    manifest: dict[str, Any],
    name: str | None = None,
    source: str | None = None,
) -> Capability:
    endpoint = manifest.get("endpoint") or {}
    if not isinstance(endpoint, dict):
        raise ValueError("Workflow manifest endpoint must be an object.")

    raw_url = str(endpoint.get("url") or manifest.get("url") or "")
    if not raw_url.startswith(("http://", "https://")):
        raise ValueError("Workflow manifest endpoint.url must be an http(s) URL.")

    parsed = urlparse(raw_url)
    method = str(endpoint.get("method") or manifest.get("method") or "POST").upper()
    capability_name = snake_name(name or manifest.get("name") or _capability_name_from_host(parsed.netloc))
    tool_name = snake_name(endpoint.get("name") or manifest.get("tool_name") or manifest.get("name") or f"{method}_{parsed.path}")
    auth = _auth_from_manifest(manifest.get("auth"), capability_name)
    input_schema = manifest.get("input_schema") or manifest.get("schema") or {}
    example = manifest.get("example")
    request_body = None
    if method not in {"GET", "HEAD"}:
        request_body = RequestBody(
            required=True,
            content_type=str(endpoint.get("content_type") or "application/json"),
            schema=input_schema if isinstance(input_schema, dict) else {},
            example=example,
        )

    response_schema = manifest.get("output_schema")
    responses = []
    if isinstance(response_schema, dict):
        responses.append(
            ResponseShape(
                status_code=str(manifest.get("success_status") or "200"),
                description="Workflow endpoint success response.",
                content_type="application/json",
                content_types=["application/json"],
                schema=response_schema,
            )
        )

    tool = Tool(
        name=tool_name,
        method=method,
        path=parsed.path or "/",
        base_url=f"{parsed.scheme}://{parsed.netloc}",
        description=str(manifest.get("description") or f"{method} workflow endpoint"),
        tags=["workflow"],
        parameters=_parameters_from_query(parsed.query),
        request_body=request_body,
        responses=responses,
        safety=classify_method(method),
    )

    return Capability(
        name=capability_name,
        version=str(manifest.get("version") or "0.1.0"),
        base_url=f"{parsed.scheme}://{parsed.netloc}",
        auth=auth,
        tools=[tool],
        source=source,
    )


def _parameters_from_query(query: str) -> list[Parameter]:
    parameters = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        parameters.append(Parameter(name=key, location="query", required=False, schema=_infer_schema(value, True)))
    return parameters


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
    return AuthConfig(type="unknown", source="manual", unsupported_reason=f"Unsupported workflow auth type: {auth_type}")


def _capability_name_from_host(host: str) -> str:
    labels = [label for label in host.split(".") if label]
    if not labels:
        return "workflow_endpoint"
    if labels[0].lower() in {"hooks", "webhook", "api"} and len(labels) > 1:
        return f"{labels[1]}_workflow"
    return f"{labels[0]}_workflow"


def _infer_schema(value: object, include_default: bool = False) -> dict:
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
