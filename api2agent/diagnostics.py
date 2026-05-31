from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from api2agent.ir.models import AuthConfig, Capability, RequestBody, SafetyLevel, Tool


DIAGNOSTICS_CONTRACT_VERSION = "api2agent.capability_diagnostics.v0"
LARGE_TOOLSET_THRESHOLD = 50
MANY_REQUIRED_PARAMETERS_THRESHOLD = 6
GENERIC_CAPABILITY_NAMES = {"api", "www", "default", "openapi", "api2agent", "generated"}
GENERIC_TOOL_NAMES = {"get", "post", "put", "patch", "delete", "list", "create", "update", "execute", "call"}


def diagnose_capability(
    capability: Capability,
    *,
    source_kind: str | None = None,
    original_tool_count: int | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    tools = capability.tools
    metrics = _metrics(capability)

    if len(tools) > LARGE_TOOLSET_THRESHOLD:
        findings.append(
            _finding(
                "large_toolset",
                "warning",
                "agent_usability",
                "Package has many tools and may need filtering before Agent use.",
                _capability_location(capability),
                "Regenerate with --include-tag, --include-path, --include-operation, or --max-tools.",
                {"tool_count": len(tools), "threshold": LARGE_TOOLSET_THRESHOLD},
            )
        )

    if tools and metrics["read_tools"] == 0:
        findings.append(
            _finding(
                "no_read_tools",
                "warning",
                "agent_usability",
                "Package has no read-only tools for safe default testing.",
                _capability_location(capability),
                "Add or select a read-only endpoint, or use the manual write-test path deliberately.",
                {"tool_count": len(tools)},
            )
        )
        if metrics["write_tools"] or metrics["delete_tools"]:
            findings.append(
                _finding(
                    "write_only_package",
                    "warning",
                    "safety",
                    "Package has write/delete tools but no safe read-only default path.",
                    _capability_location(capability),
                    "Use api2agent test . --allow-write only against a safe target, or filter to a read endpoint.",
                    {"write_tools": metrics["write_tools"], "delete_tools": metrics["delete_tools"]},
                )
            )

    if _generic_name(capability.name, GENERIC_CAPABILITY_NAMES):
        findings.append(
            _finding(
                "generic_capability_name",
                "warning",
                "agent_usability",
                "Capability name is too generic for reliable Agent tool selection.",
                _capability_location(capability),
                "Regenerate with --name using domain and resource intent, such as github_repos.",
                {"name": capability.name},
            )
        )

    duplicate_names = [name for name, count in Counter(tool.name for tool in tools).items() if count > 1]
    if duplicate_names:
        findings.append(
            _finding(
                "duplicate_tool_names",
                "error",
                "agent_usability",
                "Package contains duplicate tool names.",
                _capability_location(capability),
                "Adjust operation filters or naming before exposing this package to an Agent.",
                {"tool_names": duplicate_names},
            )
        )

    if capability.auth.type == "unknown":
        findings.append(_auth_finding("unknown_auth", capability.name, "capability", capability.auth))
    if _auth_requires_env(capability.auth):
        findings.append(_auth_finding("auth_env_missing", capability.name, "capability", capability.auth))

    if not capability.base_url and not any(tool.base_url for tool in tools):
        findings.append(
            _finding(
                "missing_base_url",
                "error",
                "execution",
                "Capability has no base URL.",
                _capability_location(capability),
                "Set a base URL in the source spec or use runtime base URL overrides deliberately.",
                {},
            )
        )

    if not capability.provider_region:
        findings.append(
            _finding(
                "missing_provider_region",
                "info",
                "observability",
                "Provider region metadata is not configured.",
                _capability_location(capability),
                "Pass --provider-region when generation context is known.",
                {},
            )
        )

    tool_auth_overrides = 0
    for tool in tools:
        findings.extend(_tool_findings(tool))
        if tool.auth is not None:
            tool_auth_overrides += 1

    if tool_auth_overrides:
        findings.append(
            _finding(
                "mixed_auth_summary",
                "info",
                "auth",
                "Package uses endpoint-level auth overrides.",
                _capability_location(capability),
                "Check per-tool auth in README.md and auth.env.example before proxy or Agent wiring.",
                {"tool_auth_overrides": tool_auth_overrides},
            )
        )

    findings.append(
        _finding(
            "proxy_identity_ready",
            "info",
            "observability",
            "Package has stable capability and tool identity for proxy usage.",
            _capability_location(capability),
            "Use API2AGENT_PROXY_URL to route generated calls through the observable proxy path.",
            {"capability_id": capability.name, "tool_count": len(tools)},
        )
    )

    summary = _summary(findings)
    return {
        "contract_version": DIAGNOSTICS_CONTRACT_VERSION,
        "status": _status(summary),
        "score": _score(summary),
        "summary": summary,
        "metrics": metrics,
        "generation_context": {
            "source_kind": source_kind or capability.source,
            "original_tool_count": original_tool_count,
            "filters": filters or {},
        },
        "findings": findings,
    }


def diagnose_capability_file(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    capability = Capability.model_validate(raw)
    return diagnose_capability(capability)


def load_package_diagnostics(package_dir: Path) -> dict[str, Any] | None:
    diagnostics_path = package_dir / "diagnostics.json"
    if not diagnostics_path.exists():
        return None
    return json.loads(diagnostics_path.read_text(encoding="utf-8"))


def diagnostics_summary_line(diagnostics: dict[str, Any]) -> str:
    summary = diagnostics.get("summary") or {}
    return (
        f"Diagnostics: {diagnostics.get('status', 'unknown')} "
        f"score={diagnostics.get('score', 'unknown')} "
        f"errors={summary.get('errors', 0)} "
        f"warnings={summary.get('warnings', 0)} "
        f"info={summary.get('info', 0)}"
    )


def format_diagnostics(diagnostics: dict[str, Any]) -> list[str]:
    lines = [diagnostics_summary_line(diagnostics)]
    findings = diagnostics.get("findings") or []
    if not findings:
        lines.append("No findings.")
        return lines

    for finding in findings:
        severity = finding.get("severity", "info")
        finding_id = finding.get("id", "unknown")
        message = finding.get("message", "")
        lines.append(f"- [{severity}] {finding_id}: {message}")
        recommendation = finding.get("recommendation")
        if recommendation:
            lines.append(f"  recommendation: {recommendation}")
    return lines


def _tool_findings(tool: Tool) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if _generic_name(tool.name, GENERIC_TOOL_NAMES):
        findings.append(
            _finding(
                "generic_tool_name",
                "warning",
                "agent_usability",
                "Tool name is too generic for reliable Agent tool selection.",
                _tool_location(tool),
                "Use a name that includes resource and action intent.",
                {"name": tool.name, "method": tool.method, "path": tool.path},
            )
        )

    if tool.safety == SafetyLevel.UNKNOWN:
        findings.append(
            _finding(
                "unknown_safety",
                "warning",
                "safety",
                "Tool safety classification is unknown.",
                _tool_location(tool),
                "Review the method/path and classify whether this is read, write, or delete.",
                {"method": tool.method, "path": tool.path},
            )
        )
    if tool.safety in {SafetyLevel.WRITE, SafetyLevel.DELETE}:
        findings.append(
            _finding(
                "write_tools_present",
                "warning",
                "safety",
                "Write/delete tool requires explicit manual testing.",
                _tool_location(tool),
                "Use api2agent test . --allow-write only against a safe target.",
                {"safety": str(tool.safety)},
            )
        )

    if _weak_description(tool):
        findings.append(
            _finding(
                "weak_tool_description",
                "warning",
                "agent_usability",
                "Tool description is too weak for Agent tool selection.",
                _tool_location(tool),
                "Improve the source operation summary/description or generated naming context.",
                {"description": tool.description},
            )
        )

    required_parameters = [parameter for parameter in tool.parameters if parameter.required]
    required_count = len(required_parameters) + (1 if tool.request_body and tool.request_body.required else 0)
    if required_count > MANY_REQUIRED_PARAMETERS_THRESHOLD:
        findings.append(
            _finding(
                "many_required_parameters",
                "warning",
                "schema",
                "Tool has many required inputs.",
                _tool_location(tool),
                "Consider filtering to a narrower endpoint or adding examples/defaults in the source API description.",
                {"required_parameter_count": required_count, "threshold": MANY_REQUIRED_PARAMETERS_THRESHOLD},
            )
        )
    missing_descriptions = [parameter.name for parameter in required_parameters if not parameter.description]
    if missing_descriptions:
        findings.append(
            _finding(
                "missing_parameter_descriptions",
                "info",
                "schema",
                "Required parameters are missing descriptions.",
                _tool_location(tool),
                "Add parameter descriptions in the source API description for better Agent prompting.",
                {"parameters": missing_descriptions},
            )
        )

    if tool.request_body is not None:
        findings.extend(_request_body_findings(tool, tool.request_body))

    if tool.auth is not None:
        if tool.auth.type == "unknown":
            findings.append(_auth_finding("unknown_auth", tool.name, "tool", tool.auth))
        if _auth_requires_env(tool.auth):
            findings.append(_auth_finding("auth_env_missing", tool.name, "tool", tool.auth))

    return findings


def _request_body_findings(tool: Tool, request_body: RequestBody) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    schema = request_body.schema_ or {}
    if request_body.required and not schema:
        findings.append(
            _finding(
                "required_body_without_schema",
                "error",
                "schema",
                "Required request body has no schema.",
                _tool_location(tool),
                "Add a request body schema in the source API description.",
                {},
            )
        )
    if schema.get("type") == "object" and not schema.get("properties"):
        findings.append(
            _finding(
                "broad_object_schema",
                "warning",
                "schema",
                "Request body accepts an unconstrained object.",
                _tool_location(tool),
                "Add object properties to the source schema so generated tools expose clearer inputs.",
                {"content_type": request_body.content_type},
            )
        )
    return findings


def _metrics(capability: Capability) -> dict[str, int]:
    tools = capability.tools
    return {
        "tool_count": len(tools),
        "read_tools": sum(1 for tool in tools if tool.safety == SafetyLevel.READ),
        "write_tools": sum(1 for tool in tools if tool.safety == SafetyLevel.WRITE),
        "delete_tools": sum(1 for tool in tools if tool.safety == SafetyLevel.DELETE),
        "unknown_safety_tools": sum(1 for tool in tools if tool.safety == SafetyLevel.UNKNOWN),
        "required_parameter_count": sum(
            len([parameter for parameter in tool.parameters if parameter.required])
            + (1 if tool.request_body and tool.request_body.required else 0)
            for tool in tools
        ),
        "tools_with_auth": sum(1 for tool in tools if tool.auth is not None and tool.auth.type != "none"),
        "tools_with_tool_base_url": sum(1 for tool in tools if tool.base_url),
    }


def _auth_finding(finding_id: str, name: str, kind: str, auth: AuthConfig) -> dict[str, Any]:
    if finding_id == "unknown_auth":
        return _finding(
            "unknown_auth",
            "warning",
            "auth",
            "Auth type is unknown.",
            {"kind": kind, "name": name},
            "Clarify auth in the source spec or curl command before production Agent use.",
            {"auth_type": auth.type},
        )
    return _finding(
        "auth_env_missing",
        "warning",
        "auth",
        "Auth is required but no environment variable name is available.",
        {"kind": kind, "name": name},
        "Regenerate from a source with explicit auth metadata or add a safe env var mapping.",
        {"auth_type": auth.type},
    )


def _auth_requires_env(auth: AuthConfig) -> bool:
    return auth.type in {"api_key", "bearer"} and not auth.env


def _summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    severities = Counter(finding["severity"] for finding in findings)
    return {
        "errors": severities.get("error", 0),
        "warnings": severities.get("warning", 0),
        "info": severities.get("info", 0),
    }


def _status(summary: dict[str, int]) -> str:
    if summary["errors"] > 0:
        return "fail"
    if summary["warnings"] > 0:
        return "warn"
    return "pass"


def _score(summary: dict[str, int]) -> int:
    penalty = summary["errors"] * 35 + summary["warnings"] * 10 + min(summary["info"] * 2, 10)
    return max(0, min(100, 100 - penalty))


def _finding(
    finding_id: str,
    severity: str,
    category: str,
    message: str,
    location: dict[str, str],
    recommendation: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": finding_id,
        "severity": severity,
        "category": category,
        "message": message,
        "location": location,
        "recommendation": recommendation,
        "evidence": evidence,
    }


def _capability_location(capability: Capability) -> dict[str, str]:
    return {"kind": "capability", "name": capability.name}


def _tool_location(tool: Tool) -> dict[str, str]:
    return {"kind": "tool", "name": tool.name}


def _generic_name(name: str, generic_names: set[str]) -> bool:
    normalized = str(name or "").strip().lower().replace("-", "_")
    return normalized in generic_names


def _weak_description(tool: Tool) -> bool:
    description = str(tool.description or "").strip().lower()
    if not description:
        return True
    method_path = f"{tool.method} {tool.path}".strip().lower()
    return description == method_path or description == tool.path.strip().lower()
