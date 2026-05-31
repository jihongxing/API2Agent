from api2agent.ir.models import Capability


def render_runner(capability: Capability) -> str:
    capability_data = repr(capability.model_dump(mode="json", by_alias=True))
    return f'''"""Generated API runner."""

import os
import json

import httpx
from dotenv import load_dotenv

CAPABILITY = {capability_data}


def execute_tool(name: str, params: dict | None = None) -> dict:
    load_dotenv()
    params = params or {{}}
    tool = _find_tool(name)
    if tool is None:
        return {{"ok": False, "error": {{"type": "unknown_tool", "message": f"Unknown tool: {{name}}"}}}}

    missing = [p["name"] for p in tool.get("parameters", []) if p.get("required") and p["name"] not in params]
    if tool.get("request_body") and tool["request_body"].get("required") and "body" not in params:
        missing.append("body")
    if missing:
        return {{"ok": False, "error": {{"type": "missing_parameters", "parameters": missing}}}}

    url_result = _build_url(tool, params)
    if isinstance(url_result, dict) and "error" in url_result:
        return {{"ok": False, "error": url_result["error"]}}
    url = url_result
    proxy_url = os.getenv("API2AGENT_PROXY_URL")
    use_proxy = bool(proxy_url and proxy_url.startswith(("http://", "https://")))
    auth_result = {{}} if use_proxy else _auth_headers(tool)
    if "error" in auth_result:
        return {{"ok": False, "error": auth_result["error"]}}

    headers = auth_result
    query = {{
        p["name"]: value
        for p in tool.get("parameters", [])
        if p.get("location") == "query"
        for value in [_parameter_value(p, params)]
        if value is not None
    }}
    for parameter in tool.get("parameters", []):
        if parameter.get("location") == "header":
            value = _parameter_value(parameter, params)
            if value is not None:
                headers[parameter["name"]] = str(value)

    request_kwargs = {{"headers": headers, "params": query, "timeout": 20}}
    if tool.get("request_body") and "body" in params:
        request_kwargs["json"] = params["body"]
    if use_proxy:
        return _proxy_call(tool, url, request_kwargs, proxy_url, _proxy_credential_intent(tool))

    _apply_credential_injection(request_kwargs)

    try:
        response = httpx.request(tool["method"], url, **request_kwargs)
    except httpx.HTTPError as exc:
        return {{"ok": False, "error": {{"type": "http_error", "message": str(exc)}}}}

    try:
        body = response.json()
    except ValueError:
        body = response.text

    result = {{
        "ok": response.is_success,
        "status_code": response.status_code,
        "body": body,
    }}
    if not response.is_success:
        result["error"] = {{
            "type": "http_status",
            "message": f"HTTP {{response.status_code}}",
        }}
    return result


def _proxy_call(
    tool: dict,
    url: str,
    request_kwargs: dict,
    proxy_url: str,
    credential: dict | None = None,
) -> dict:
    proxy_headers = {{}}
    proxy_key = os.getenv("API2AGENT_PROXY_KEY")
    if proxy_key:
        proxy_headers["Authorization"] = f"Bearer {{proxy_key}}"

    project_id = os.getenv("API2AGENT_PROJECT_ID") or "local"
    capability_id = os.getenv("API2AGENT_CAPABILITY_ID") or CAPABILITY.get("name", "unknown")
    provider_id = os.getenv("API2AGENT_PROVIDER_ID") or CAPABILITY.get("name", "unknown")
    payload = {{
        "project_id": project_id,
        "routing_decision_id": os.getenv("API2AGENT_ROUTING_DECISION_ID"),
        "capability_id": capability_id,
        "provider_id": provider_id,
        "provider_region": _provider_region(),
        "tool_id": tool["name"],
        "estimated_cost": _estimated_cost(),
        "request": {{
            "method": tool["method"],
            "url": url,
            "headers": request_kwargs.get("headers") or {{}},
            "params": request_kwargs.get("params") or {{}},
            "json": request_kwargs.get("json"),
            "timeout": request_kwargs.get("timeout") or 20,
        }},
    }}
    if credential:
        credential.setdefault("owner_id", project_id)
        credential.setdefault("provider_id", provider_id)
        payload["credential"] = credential

    try:
        response = httpx.post(
            proxy_url.rstrip("/") + "/v1/proxy/call",
            json=payload,
            headers=proxy_headers,
            timeout=25,
        )
    except httpx.HTTPError as exc:
        return {{"ok": False, "error": {{"type": "proxy_error", "message": str(exc)}}}}

    try:
        body = response.json()
    except ValueError:
        return {{
            "ok": False,
            "status_code": response.status_code,
            "error": {{"type": "proxy_error", "message": response.text}},
        }}

    if isinstance(body, dict):
        return body
    return {{"ok": response.is_success, "status_code": response.status_code, "body": body}}


def _estimated_cost() -> float:
    raw = os.getenv("API2AGENT_ESTIMATED_COST")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _provider_region() -> str | None:
    return os.getenv("API2AGENT_PROVIDER_REGION") or CAPABILITY.get("provider_region")


def _proxy_credential_intent(tool: dict) -> dict | None:
    auth = _tool_auth(tool)
    auth_type = auth.get("type")
    if auth_type not in {{"api_key", "bearer"}}:
        return None

    env_name = auth.get("env")
    if not env_name:
        return None

    provider_id = os.getenv("API2AGENT_PROVIDER_ID") or CAPABILITY.get("name", "unknown")
    injection_name = auth.get("header") or ("Authorization" if auth_type == "bearer" else "X-API-Key")
    return {{
        "credential_id": os.getenv("API2AGENT_CREDENTIAL_ID") or f"{{provider_id}}_{{env_name}}",
        "owner_type": os.getenv("API2AGENT_CREDENTIAL_OWNER_TYPE") or "project",
        "owner_id": os.getenv("API2AGENT_CREDENTIAL_OWNER_ID") or os.getenv("API2AGENT_PROJECT_ID") or "local",
        "provider_id": provider_id,
        "auth_type": auth_type,
        "injection_mode": "header",
        "injection_name": injection_name,
        "source": "env",
        "secret_ref": env_name,
    }}


def _apply_credential_injection(request_kwargs: dict) -> None:
    headers = _json_env("API2AGENT_CREDENTIAL_HEADERS")
    query = _json_env("API2AGENT_CREDENTIAL_QUERY")
    body = _json_env("API2AGENT_CREDENTIAL_BODY")
    if headers:
        request_kwargs.setdefault("headers", {{}}).update(headers)
    if query:
        request_kwargs.setdefault("params", {{}}).update(query)
    if body:
        existing = request_kwargs.get("json")
        if isinstance(existing, dict):
            existing.update(body)
        else:
            request_kwargs["json"] = body


def _json_env(name: str) -> dict:
    raw = os.getenv(name)
    if not raw:
        return {{}}
    try:
        value = json.loads(raw)
    except ValueError:
        return {{}}
    return value if isinstance(value, dict) else {{}}


def _find_tool(name: str) -> dict | None:
    for tool in CAPABILITY["tools"]:
        if tool["name"] == name:
            return tool
    return None


def _build_url(tool: dict, params: dict) -> str | dict:
    path = tool["path"]
    for parameter in tool.get("parameters", []):
        if parameter.get("location") == "path":
            value = _parameter_value(parameter, params)
            if value is not None:
                path = path.replace("{{" + parameter["name"] + "}}", str(value))
    base_url_result = _base_url(tool)
    if isinstance(base_url_result, dict) and "error" in base_url_result:
        return base_url_result
    base_url = base_url_result
    return _join_url(base_url, path)


def _join_url(base_url: str, path: str) -> str:
    if not base_url:
        return path
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _base_url(tool: dict) -> str | dict:
    tool_env = _tool_base_url_env(tool)
    for env_name in [tool_env, "API2AGENT_BASE_URL"]:
        raw = os.getenv(env_name)
        if not raw:
            continue
        if not raw.startswith(("http://", "https://")):
            return {{
                "error": {{
                    "type": "invalid_base_url_override",
                    "message": f"Invalid base URL override in {{env_name}}. Expected http:// or https:// URL.",
                    "env": env_name,
                }}
            }}
        return raw
    return tool.get("base_url") or CAPABILITY.get("base_url", "")


def _tool_base_url_env(tool: dict) -> str:
    suffix = "".join(
        char.upper() if char.isalnum() else "_"
        for char in str(tool.get("name") or "TOOL")
    ).strip("_")
    return f"API2AGENT_TOOL_BASE_URL_{{suffix or 'TOOL'}}"


def _parameter_value(parameter: dict, params: dict):
    name = parameter["name"]
    if name in params:
        return params[name]
    schema = parameter.get("schema") or {{}}
    if "default" in schema:
        return schema["default"]
    return None


def _tool_auth(tool: dict) -> dict:
    tool_auth = tool.get("auth")
    if tool_auth is not None:
        return tool_auth
    return CAPABILITY.get("auth") or {{}}


def _auth_headers(tool: dict) -> dict:
    auth = _tool_auth(tool)
    if auth.get("type") in {"none", "unknown"}:
        return {{}}
    if _has_credential_injection():
        return {{}}

    env_name = auth.get("env")
    token = os.getenv(env_name) if env_name else None
    if not token:
        return {{
            "error": {{
                "type": "missing_auth",
                "message": f"Missing auth environment variable: {{env_name}}",
                "env": env_name,
            }}
        }}

    if auth.get("type") == "bearer":
        return {{"Authorization": f"Bearer {{token}}"}}

    header = auth.get("header") or "X-API-Key"
    return {{header: token}}


def _has_credential_injection() -> bool:
    return bool(
        os.getenv("API2AGENT_CREDENTIAL_HEADERS")
        or os.getenv("API2AGENT_CREDENTIAL_QUERY")
        or os.getenv("API2AGENT_CREDENTIAL_BODY")
    )
'''
