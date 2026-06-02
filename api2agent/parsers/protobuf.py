import re
from pathlib import Path
from typing import Any

from api2agent.ir.models import AuthConfig, Capability, RequestBody, ResponseShape, SafetyLevel, Tool
from api2agent.utils.naming import snake_name


SCALAR_TYPES = {
    "double": {"type": "number"},
    "float": {"type": "number"},
    "int32": {"type": "integer"},
    "int64": {"type": "integer"},
    "uint32": {"type": "integer"},
    "uint64": {"type": "integer"},
    "sint32": {"type": "integer"},
    "sint64": {"type": "integer"},
    "fixed32": {"type": "integer"},
    "fixed64": {"type": "integer"},
    "sfixed32": {"type": "integer"},
    "sfixed64": {"type": "integer"},
    "bool": {"type": "boolean"},
    "string": {"type": "string"},
    "bytes": {"type": "string", "format": "byte"},
}


def parse_proto_file(path: Path, name: str | None = None) -> Capability:
    source = path.read_text(encoding="utf-8")
    return parse_proto(source, name=name, source_path=str(path))


def parse_proto(source: str, name: str | None = None, source_path: str | None = None) -> Capability:
    cleaned = _strip_comments(source)
    package = _first_match(r"\bpackage\s+([\w.]+)\s*;", cleaned) or ""
    messages = _messages(cleaned)
    services = _services(cleaned)
    if not services:
        raise ValueError("Proto file must include at least one service.")

    capability_name = snake_name(name or package or services[0]["name"] or "grpc_service")
    tools = []
    for service in services:
        for rpc in service["rpcs"]:
            if rpc["client_streaming"] or rpc["server_streaming"]:
                continue
            tools.append(_tool_from_rpc(package, service["name"], rpc, messages))
    if not tools:
        raise ValueError("Proto file must include at least one unary RPC.")

    return Capability(
        name=capability_name,
        base_url="grpc://localhost:50051",
        auth=AuthConfig(type="none"),
        tools=tools,
        source=source_path,
    )


def count_proto_unary_rpcs_file(path: Path) -> int:
    cleaned = _strip_comments(path.read_text(encoding="utf-8"))
    return sum(
        1
        for service in _services(cleaned)
        for rpc in service["rpcs"]
        if not rpc["client_streaming"] and not rpc["server_streaming"]
    )


def _tool_from_rpc(package: str, service_name: str, rpc: dict[str, Any], messages: dict[str, dict[str, Any]]) -> Tool:
    full_service = f"{package}.{service_name}" if package else service_name
    request_schema = _message_schema(rpc["request"], messages)
    request_schema["x-api2agent-grpc"] = {
        "package": package,
        "service": service_name,
        "method": rpc["name"],
        "requestType": rpc["request"],
        "responseType": rpc["response"],
    }
    response_schema = _message_schema(rpc["response"], messages)
    return Tool(
        name=snake_name(f"{service_name}_{rpc['name']}"),
        operation_id=f"{full_service}.{rpc['name']}",
        method="POST",
        path=f"/{full_service}/{rpc['name']}",
        base_url="grpc://localhost:50051",
        description=f"gRPC unary RPC {full_service}.{rpc['name']}",
        tags=["grpc", service_name],
        request_body=RequestBody(required=True, content_type="application/json", schema=request_schema),
        responses=[
            ResponseShape(
                status_code="OK",
                description="gRPC unary response message.",
                content_type="application/json",
                content_types=["application/json"],
                schema=response_schema,
            )
        ],
        safety=SafetyLevel.UNKNOWN,
    )


def _message_schema(message_name: str, messages: dict[str, dict[str, Any]], seen: set[str] | None = None) -> dict[str, Any]:
    seen = seen or set()
    message = messages.get(message_name)
    if not message or message_name in seen:
        return {"type": "object"}
    seen.add(message_name)
    properties = {}
    for field in message["fields"]:
        properties[field["name"]] = _field_schema(field, messages, seen.copy())
    return {"type": "object", "properties": properties}


def _field_schema(field: dict[str, str], messages: dict[str, dict[str, Any]], seen: set[str]) -> dict[str, Any]:
    field_type = field["type"]
    if field_type in SCALAR_TYPES:
        schema = dict(SCALAR_TYPES[field_type])
    elif field_type in {"google.protobuf.Timestamp", "Timestamp"}:
        schema = {"type": "string", "format": "date-time"}
    else:
        schema = _message_schema(field_type.split(".")[-1], messages, seen)
    if field.get("repeated"):
        return {"type": "array", "items": schema}
    return schema


def _messages(source: str) -> dict[str, dict[str, Any]]:
    messages = {}
    for name, body in _blocks(source, "message"):
        messages[name] = {"name": name, "fields": _fields(body)}
    return messages


def _services(source: str) -> list[dict[str, Any]]:
    services = []
    for name, body in _blocks(source, "service"):
        services.append({"name": name, "rpcs": _rpcs(body)})
    return services


def _fields(body: str) -> list[dict[str, Any]]:
    fields = []
    pattern = re.compile(
        r"\b(?P<repeated>repeated\s+)?(?P<type>[\w.]+)\s+(?P<name>\w+)\s*=\s*(?P<number>\d+)(?:\s*\[[^\]]+\])?\s*;"
    )
    for match in pattern.finditer(body):
        fields.append(
            {
                "name": match.group("name"),
                "type": match.group("type"),
                "number": match.group("number"),
                "repeated": bool(match.group("repeated")),
            }
        )
    return fields


def _rpcs(body: str) -> list[dict[str, Any]]:
    rpcs = []
    pattern = re.compile(
        r"\brpc\s+(?P<name>\w+)\s*\(\s*(?P<client_stream>stream\s+)?(?P<request>[\w.]+)\s*\)\s*returns\s*\(\s*(?P<server_stream>stream\s+)?(?P<response>[\w.]+)\s*\)\s*(?:;|\{[^}]*\})",
        re.DOTALL,
    )
    for match in pattern.finditer(body):
        rpcs.append(
            {
                "name": match.group("name"),
                "request": match.group("request").split(".")[-1],
                "response": match.group("response").split(".")[-1],
                "client_streaming": bool(match.group("client_stream")),
                "server_streaming": bool(match.group("server_stream")),
            }
        )
    return rpcs


def _blocks(source: str, keyword: str) -> list[tuple[str, str]]:
    blocks = []
    pattern = re.compile(rf"\b{keyword}\s+(\w+)\s*\{{")
    for match in pattern.finditer(source):
        start = match.end()
        end = _matching_brace(source, start - 1)
        if end is not None:
            blocks.append((match.group(1), source[start:end]))
    return blocks


def _matching_brace(source: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _strip_comments(source: str) -> str:
    source = re.sub(r"//.*", "", source)
    return re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None
