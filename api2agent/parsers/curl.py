import json
import shlex
from urllib.parse import parse_qsl, urlparse

from api2agent.ir.models import AuthConfig, Capability, Parameter, RequestBody, Tool
from api2agent.safety import classify_method
from api2agent.utils.naming import env_name, snake_name


def parse_curl(command: str | None, name: str | None = None) -> Capability:
    if not command:
        raise ValueError("curl command is required")

    # MVP parser: enough for URL + method detection. A full shell parser comes later.
    tokens = shlex.split(command.replace("\\\n", " "))
    method = "GET"
    url = ""
    headers: list[str] = []
    body: object | None = None
    has_body = False

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"-X", "--request"} and index + 1 < len(tokens):
            method = tokens[index + 1].upper()
            index += 2
            continue
        if token in {"-H", "--header"} and index + 1 < len(tokens):
            headers.append(tokens[index + 1].strip("'\""))
            index += 2
            continue
        if token in {"-d", "--data", "--data-raw", "--data-binary", "--json"} and index + 1 < len(tokens):
            body = _parse_body(tokens[index + 1])
            has_body = True
            if method == "GET":
                method = "POST"
            index += 2
            continue
        if token.startswith("http://") or token.startswith("https://"):
            url = token.strip("'\"")
        index += 1

    if not url:
        raise ValueError("curl command must include an http(s) URL")

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    capability_name = snake_name(name or _capability_name_from_host(parsed.netloc) or "curl_api")
    auth = _auth_from_headers(headers, capability_name)
    parameters = _parameters_from_url(parsed.query) + _parameters_from_headers(headers)
    request_body = RequestBody(required=True, schema=_infer_schema(body)) if has_body else None

    tool = Tool(
        name=_tool_name(method, path, capability_name),
        method=method,
        path=path,
        description=f"{method} {path}",
        parameters=parameters,
        request_body=request_body,
        safety=classify_method(method),
    )

    return Capability(
        name=capability_name,
        base_url=base_url,
        auth=auth,
        tools=[tool],
        source="curl",
    )


def _tool_name(method: str, path: str, capability_name: str) -> str:
    normalized_path = path.strip("/")
    if not normalized_path:
        return snake_name(f"{method}_{capability_name}")
    return snake_name(f"{method}_{path}")


def _capability_name_from_host(host: str) -> str:
    labels = [label for label in host.split(".") if label]
    if not labels:
        return "curl_api"
    if labels[0].lower() in {"api", "www"} and len(labels) > 1:
        return f"{labels[1]}_{labels[0]}"
    return labels[0]


def _parameters_from_url(query: str) -> list[Parameter]:
    parameters: list[Parameter] = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        parameters.append(
            Parameter(
                name=key,
                location="query",
                required=False,
                schema=_infer_schema(value, include_default=True),
            )
        )
    return parameters


def _parameters_from_headers(headers: list[str]) -> list[Parameter]:
    parameters: list[Parameter] = []
    for header in headers:
        name, value = _split_header(header)
        if not name or _is_auth_header(name, value) or name.lower() == "content-type":
            continue
        parameters.append(
            Parameter(
                name=name,
                location="header",
                required=False,
                schema=_infer_schema(value, include_default=True),
            )
        )
    return parameters


def _auth_from_headers(headers: list[str], capability_name: str) -> AuthConfig:
    for header in headers:
        name, value = _split_header(header)
        if _is_auth_header(name, value):
            return AuthConfig(
                type="bearer",
                env=env_name(f"{capability_name}_token"),
                header="Authorization",
            )
        if name.lower() == "x-api-key":
            return AuthConfig(
                type="api_key",
                env=env_name(f"{capability_name}_api_key"),
                header="X-API-Key",
            )
    return AuthConfig(type="none")


def _split_header(header: str) -> tuple[str, str]:
    if ":" not in header:
        return header.strip(), ""
    name, value = header.split(":", 1)
    return name.strip(), value.strip()


def _is_auth_header(name: str, value: str) -> bool:
    return name.lower() == "authorization" and value.lower().startswith("bearer ")


def _parse_body(raw_body: str) -> object:
    unescaped = raw_body
    for _ in range(3):
        unescaped = unescaped.replace('\\"', '"')

    candidates = [
        raw_body,
        raw_body.strip("'\""),
        unescaped,
        unescaped.strip("'\""),
    ]
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return raw_body


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
