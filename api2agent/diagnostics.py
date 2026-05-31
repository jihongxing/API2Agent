from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from api2agent.ir.models import AuthConfig, Capability, RequestBody, ResponseShape, SafetyLevel, Tool
from api2agent.response_docs import is_no_body_status, response_category, response_has_example
from api2agent.schema_shaping import schema_hint_counts, schema_paths_with_hint


DIAGNOSTICS_CONTRACT_VERSION = "api2agent.capability_diagnostics.v0"
SCORING_PROFILE = "api2agent.diagnostics.score_profile.v0"
LARGE_TOOLSET_THRESHOLD = 50
MANY_REQUIRED_PARAMETERS_THRESHOLD = 6
GENERIC_CAPABILITY_NAMES = {"api", "www", "default", "openapi", "api2agent", "generated"}
GENERIC_TOOL_NAMES = {"get", "post", "put", "patch", "delete", "list", "create", "update", "execute", "call"}
SCORE_BASE = 100
METADATA_REVIEW_PENALTY_CAP = 8
ACTION_REQUIRED_FINDING_PENALTY_CAP = 10
IMPACT_ORDER = ("blocking", "action_required", "review_required", "metadata_review", "readiness")
IMPACT_PENALTIES = {
    "blocking": 35,
    "action_required": 10,
    "review_required": 4,
    "metadata_review": 1,
    "readiness": 0,
}
BLOCKING_FINDINGS = {
    "duplicate_tool_names",
    "missing_base_url",
    "required_body_without_schema",
}
ACTION_REQUIRED_FINDINGS = {
    "large_toolset",
    "no_read_tools",
    "write_only_package",
    "generic_capability_name",
    "generic_tool_name",
    "unknown_safety",
    "write_tools_present",
    "weak_tool_description",
    "many_required_parameters",
    "array_without_item_schema",
    "discriminator_missing_property",
    "discriminator_without_polymorphism",
    "discriminator_mapping_unresolved",
    "success_response_without_schema",
    "unsupported_auth_scheme",
    "unknown_auth",
    "auth_env_missing",
    "relative_server_url",
}
REVIEW_REQUIRED_FINDINGS = {
    "broad_object_schema",
    "read_only_request_fields",
    "write_only_response_fields",
    "conditional_schema_present",
    "dependent_schema_present",
}
METADATA_REVIEW_FINDINGS = {
    "missing_provider_region",
    "missing_parameter_descriptions",
    "additional_properties_present",
    "nullable_fields_present",
    "nested_polymorphic_schema",
    "large_object_schema",
    "schema_keywords_present",
    "string_constraints_present",
    "numeric_constraints_present",
    "array_constraints_present",
    "const_schema_present",
    "deprecated_schema_fields",
    "pattern_schema_present",
    "unsupported_schema_keywords_present",
    "discriminator_present",
    "discriminator_mapping_present",
    "discriminator_branch_without_tag",
    "response_schema_present",
    "response_example_present",
    "response_without_schema",
    "error_response_schema_present",
    "default_response_present",
    "multiple_response_content_types",
    "response_polymorphic_schema",
    "auth_alternatives_present",
    "combined_auth_required",
    "query_api_key_auth",
    "cookie_api_key_auth",
    "metadata_only_oauth",
    "multiple_servers_present",
    "ambiguous_server_profiles",
    "server_variables_present",
    "path_server_override",
    "operation_server_override",
    "mixed_auth_summary",
}
READINESS_FINDINGS = {"proxy_identity_ready"}


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
    findings.extend(_security_requirement_findings(capability.name, "capability", capability.security_requirements))

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
    findings.extend(_server_findings(capability.name, "capability", capability.servers))

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
        if tool.server_source != "document":
            findings.extend(_server_findings(tool.name, "tool", tool.servers))
        if tool.server_source == "path":
            findings.append(_server_override_finding("path_server_override", tool))
        if tool.server_source == "operation":
            findings.append(_server_override_finding("operation_server_override", tool))
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
    score_breakdown = _score_breakdown(findings)
    return {
        "contract_version": DIAGNOSTICS_CONTRACT_VERSION,
        "status": _status(summary),
        "score": score_breakdown["score"],
        "scoring_profile": SCORING_PROFILE,
        "score_breakdown": score_breakdown,
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

    for finding, count in _group_findings(findings):
        severity = finding.get("severity", "info")
        finding_id = finding.get("id", "unknown")
        message = finding.get("message", "")
        count_label = f" x{count}" if count > 1 else ""
        lines.append(f"- [{severity}] {finding_id}{count_label}: {message}")
        recommendation = finding.get("recommendation")
        if recommendation:
            lines.append(f"  recommendation: {recommendation}")
    return lines


def _group_findings(findings: list[dict[str, Any]]) -> list[tuple[dict[str, Any], int]]:
    grouped: dict[tuple[str, str, str], tuple[dict[str, Any], int]] = {}
    for finding in findings:
        key = (
            str(finding.get("severity") or "info"),
            str(finding.get("id") or "unknown"),
            str(finding.get("message") or ""),
        )
        representative, count = grouped.get(key, (finding, 0))
        grouped[key] = (representative, count + 1)
    return list(grouped.values())


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
    for response in tool.responses:
        findings.extend(_response_schema_findings(tool, response))
    for parameter in tool.parameters:
        findings.extend(
            _schema_complexity_findings(
                tool,
                parameter.schema_ or {},
                f"parameter:{parameter.name}",
                deprecated_severity="warning" if parameter.required else "info",
            )
        )

    if tool.auth is not None:
        if tool.auth.type == "unknown":
            findings.append(_auth_finding("unknown_auth", tool.name, "tool", tool.auth))
        if _auth_requires_env(tool.auth):
            findings.append(_auth_finding("auth_env_missing", tool.name, "tool", tool.auth))
    findings.extend(_security_requirement_findings(tool.name, "tool", tool.security_requirements))

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
    read_only_paths = schema_paths_with_hint(schema, "read_only")
    if read_only_paths:
        findings.append(
            _finding(
                "read_only_request_fields",
                "info",
                "schema",
                "Request body schema includes read-only fields that should not be requested from users.",
                _tool_location(tool),
                "Use request-direction schema shaping so generated Agent inputs omit server-generated fields.",
                {"content_type": request_body.content_type, "paths": read_only_paths},
            )
        )
    findings.extend(
        _schema_complexity_findings(
            tool,
            schema,
            "request_body",
            request_schema=True,
            deprecated_severity="warning" if _has_required_deprecated_property(schema) else "info",
        )
    )
    return findings


def _response_schema_findings(tool: Tool, response: ResponseShape) -> list[dict[str, Any]]:
    schema = response.schema_ or {}
    findings: list[dict[str, Any]] = []
    status_code = response.status_code
    category = response_category(status_code)
    evidence = {
        "status_code": status_code,
        "category": category,
        "content_type": response.content_type,
    }

    if schema:
        findings.append(
            _finding(
                "response_schema_present",
                "info",
                "schema",
                "Response includes a documented schema.",
                _tool_location(tool),
                "Review generated response summaries before wiring this package into an Agent.",
                evidence,
            )
        )
    else:
        findings.append(
            _finding(
                "response_without_schema",
                "info",
                "schema",
                "Response has no documented schema.",
                _tool_location(tool),
                "Add a response schema in the source OpenAPI document when callers need to understand returned data.",
                evidence,
            )
        )
        if category == "success" and not is_no_body_status(status_code):
            findings.append(
                _finding(
                    "success_response_without_schema",
                    "warning",
                    "schema",
                    "Success response has no documented schema.",
                    _tool_location(tool),
                    "Add a success response schema so generated docs can show Agents what a successful call returns.",
                    evidence,
                )
            )

    if response_has_example(response):
        findings.append(
            _finding(
                "response_example_present",
                "info",
                "schema",
                "Response includes source examples.",
                _tool_location(tool),
                "Use response examples to verify generated docs explain returned payloads clearly.",
                {**evidence, "example_count": len(response.examples) + (1 if response.example is not None else 0)},
            )
        )
    if category in {"client_error", "server_error"} and schema:
        findings.append(
            _finding(
                "error_response_schema_present",
                "info",
                "schema",
                "Error response includes a structured schema.",
                _tool_location(tool),
                "Expose structured error bodies in generated docs so Agents can interpret failures.",
                evidence,
            )
        )
    if category == "default":
        findings.append(
            _finding(
                "default_response_present",
                "info",
                "schema",
                "OpenAPI source includes a default response.",
                _tool_location(tool),
                "Document default responses as catch-all outcomes for Agent planning.",
                evidence,
            )
        )
    if len(response.content_types) > 1:
        findings.append(
            _finding(
                "multiple_response_content_types",
                "info",
                "schema",
                "Response offers multiple content types; generation selected one deterministically.",
                _tool_location(tool),
                "Review selected response content type before relying on generated response docs.",
                {**evidence, "content_types": response.content_types},
            )
        )

    if not schema:
        return findings

    if any(key in schema for key in ("oneOf", "anyOf")):
        findings.append(
            _finding(
                "response_polymorphic_schema",
                "info",
                "schema",
                "Response schema contains oneOf/anyOf polymorphism.",
                _tool_location(tool),
                "Review response summaries and discriminator diagnostics for polymorphic outputs.",
                evidence,
            )
        )

    write_only_paths = schema_paths_with_hint(schema, "write_only")
    if write_only_paths:
        findings.append(
            _finding(
                "write_only_response_fields",
                "info",
                "schema",
                "Response schema includes write-only fields that should not be shown as returned values.",
                _tool_location(tool),
                "Use response-direction schema shaping so response summaries do not imply secrets are returned.",
                {"status_code": response.status_code, "paths": write_only_paths},
            )
        )
    findings.extend(_schema_complexity_findings(tool, schema, f"response:{response.status_code}"))
    return findings


def _schema_complexity_findings(
    tool: Tool,
    schema: dict[str, Any],
    label: str,
    *,
    request_schema: bool = False,
    deprecated_severity: str = "info",
) -> list[dict[str, Any]]:
    if not schema:
        return []

    counts = schema_hint_counts(schema)
    findings: list[dict[str, Any]] = []
    hint_specs = [
        (
            "nullable",
            "nullable_fields_present",
            "info",
            "Schema includes nullable fields.",
            "Review generated examples and docs so Agent prompts handle nullability deliberately.",
        ),
        (
            "maps",
            "additional_properties_present",
            "info",
            "Schema uses additionalProperties map/object semantics.",
            "Review map-shaped inputs and outputs before exposing this package to an Agent.",
        ),
        (
            "nested_polymorphic",
            "nested_polymorphic_schema",
            "info",
            "Schema contains nested oneOf/anyOf branches.",
            "Keep generated summaries bounded and add source examples for polymorphic shapes when possible.",
        ),
        (
            "arrays_without_items",
            "array_without_item_schema",
            "warning",
            "Schema contains an array without an item schema.",
            "Add items to the source schema so generated examples and tools know the array element shape.",
        ),
        (
            "large_objects",
            "large_object_schema",
            "info",
            "Schema contains a large object shape.",
            "Consider examples/defaults or endpoint filtering if Agent input selection becomes noisy.",
        ),
        (
            "schema_keywords",
            "schema_keywords_present",
            "info",
            "Schema includes JSON Schema keyword constraints.",
            "Review generated summaries and examples so Agent prompts preserve these constraints.",
        ),
        (
            "string_constraints",
            "string_constraints_present",
            "info",
            "Schema includes string constraints such as format, pattern, or length bounds.",
            "Review generated examples and docs for format and length-sensitive inputs.",
        ),
        (
            "numeric_constraints",
            "numeric_constraints_present",
            "info",
            "Schema includes numeric bounds.",
            "Review generated examples for in-range numeric values.",
        ),
        (
            "array_constraints",
            "array_constraints_present",
            "info",
            "Schema includes array cardinality or uniqueness constraints.",
            "Review generated examples for representative array sizes.",
        ),
        (
            "const_schema",
            "const_schema_present",
            "info",
            "Schema includes const values.",
            "Use const-aware examples to verify fixed discriminator or status-like values.",
        ),
        (
            "deprecated_schema_fields",
            "deprecated_schema_fields",
            deprecated_severity,
            "Schema includes deprecated fields.",
            "Avoid relying on deprecated request fields unless the API requires them.",
        ),
        (
            "pattern_schema",
            "pattern_schema_present",
            "info",
            "Schema includes regex pattern constraints.",
            "Review pattern constraints manually; v0 examples do not synthesize regex-matching values.",
        ),
        (
            "unsupported_schema_keywords",
            "unsupported_schema_keywords_present",
            "info",
            "Schema includes advanced JSON Schema keywords preserved as metadata only.",
            "Review source schema semantics before relying on generated examples as full validation samples.",
        ),
        (
            "conditional_schema",
            "conditional_schema_present",
            "warning" if request_schema else "info",
            "Schema includes conditional keywords.",
            "Add source examples for conditional request bodies because generated examples do not validate full branches.",
        ),
        (
            "dependent_schema",
            "dependent_schema_present",
            "warning" if request_schema else "info",
            "Schema includes dependent schema keywords.",
            "Add source examples for dependent request bodies because generated examples do not validate full dependencies.",
        ),
    ]

    for hint, finding_id, severity, message, recommendation in hint_specs:
        if not counts.get(hint):
            continue
        findings.append(
            _finding(
                finding_id,
                severity,
                "schema",
                message,
                _tool_location(tool),
                recommendation,
                {
                    "schema": label,
                    "count": counts[hint],
                    "paths": schema_paths_with_hint(schema, hint)[:10],
                },
            )
        )
    findings.extend(_discriminator_findings(tool, schema, label))
    return findings


def _has_required_deprecated_property(schema: dict[str, Any]) -> bool:
    if not isinstance(schema, dict):
        return False

    required = {str(item) for item in schema.get("required") or []}
    properties = schema.get("properties") or {}
    if isinstance(properties, dict):
        for name, child in properties.items():
            if str(name) in required and isinstance(child, dict) and child.get("deprecated") is True:
                return True
            if isinstance(child, dict) and _has_required_deprecated_property(child):
                return True

    items = schema.get("items")
    if isinstance(items, dict) and _has_required_deprecated_property(items):
        return True

    for key in ("oneOf", "anyOf", "allOf"):
        branches = schema.get(key)
        if isinstance(branches, list) and any(
            _has_required_deprecated_property(branch) for branch in branches if isinstance(branch, dict)
        ):
            return True

    additional = schema.get("additionalProperties")
    return isinstance(additional, dict) and _has_required_deprecated_property(additional)


def _discriminator_findings(tool: Tool, schema: dict[str, Any], label: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    discriminator_paths = schema_paths_with_hint(schema, "discriminators")
    if not discriminator_paths:
        return findings

    findings.append(
        _finding(
            "discriminator_present",
            "info",
            "schema",
            "Schema includes OpenAPI discriminator metadata.",
            _tool_location(tool),
            "Review discriminator-aware summaries and examples for polymorphic Agent inputs.",
            {"schema": label, "paths": discriminator_paths[:10]},
        )
    )

    mapping_paths = schema_paths_with_hint(schema, "discriminator_mappings")
    if mapping_paths:
        findings.append(
            _finding(
                "discriminator_mapping_present",
                "info",
                "schema",
                "Schema discriminator includes explicit mapping values.",
                _tool_location(tool),
                "Use mapping keys to verify generated examples select the intended branch.",
                {"schema": label, "paths": mapping_paths[:10]},
            )
        )

    quality_specs = [
        (
            "discriminator_missing_property",
            "discriminator_missing_property",
            "warning",
            "Schema discriminator is missing propertyName.",
            "Add discriminator.propertyName so generated summaries can explain branch selection.",
        ),
        (
            "discriminator_without_polymorphism",
            "discriminator_without_polymorphism",
            "warning",
            "Schema has a discriminator without sibling oneOf/anyOf branches.",
            "Place discriminator metadata next to the polymorphic oneOf/anyOf schema.",
        ),
        (
            "discriminator_mapping_unresolved",
            "discriminator_mapping_unresolved",
            "warning",
            "Schema discriminator mapping references targets that do not match known branch labels.",
            "Check mapping targets and branch schema titles or refs in the source OpenAPI document.",
        ),
        (
            "discriminator_branch_without_tag",
            "discriminator_branch_without_tag",
            "info",
            "A discriminator branch does not declare an obvious tag value.",
            "Add const, enum, default, or example on the discriminator property for clearer generated examples.",
        ),
    ]
    for hint, finding_id, severity, message, recommendation in quality_specs:
        paths = schema_paths_with_hint(schema, hint)
        if not paths:
            continue
        findings.append(
            _finding(
                finding_id,
                severity,
                "schema",
                message,
                _tool_location(tool),
                recommendation,
                {"schema": label, "paths": paths[:10]},
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
        "server_count": len(capability.servers) + sum(len(tool.servers) for tool in tools if tool.server_source != "document"),
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
            {"auth_type": auth.type, "unsupported_reason": auth.unsupported_reason},
        )
    return _finding(
        "auth_env_missing",
        "warning",
        "auth",
        "Auth is required but no environment variable name is available.",
        {"kind": kind, "name": name},
        "Regenerate from a source with explicit auth metadata or add a safe env var mapping.",
        {"auth_type": auth.type, "envs": _missing_auth_envs(auth)},
    )


def _auth_requires_env(auth: AuthConfig) -> bool:
    return bool(_missing_auth_envs(auth))


def _missing_auth_envs(auth: AuthConfig) -> list[str]:
    credentials = auth.credentials or [auth.model_dump(mode="json", by_alias=True)]
    missing: list[str] = []
    for credential in credentials:
        if credential.get("type") in {"api_key", "bearer"} and not credential.get("env"):
            label = credential.get("scheme_name") or credential.get("name") or credential.get("type")
            missing.append(str(label))
    return missing


def _security_requirement_findings(name: str, kind: str, requirements) -> list[dict[str, Any]]:
    if requirements is None:
        return []

    findings: list[dict[str, Any]] = []
    alternatives = requirements.alternatives
    if len(alternatives) > 1:
        findings.append(
            _finding(
                "auth_alternatives_present",
                "info",
                "auth",
                "OpenAPI security has alternative auth requirements.",
                {"kind": kind, "name": name},
                "Check generated README auth summaries before choosing credentials for Agent or proxy wiring.",
                {"alternatives": len(alternatives)},
            )
        )

    for alternative in alternatives:
        if len(alternative.schemes) > 1:
            findings.append(
                _finding(
                    "combined_auth_required",
                    "info",
                    "auth",
                    "OpenAPI security requires multiple credentials for one alternative.",
                    {"kind": kind, "name": name},
                    "Set every listed auth environment variable before direct execution.",
                    {"scheme_names": [scheme.scheme_name for scheme in alternative.schemes]},
                )
            )
        for scheme in alternative.schemes:
            if scheme.location == "query":
                findings.append(_auth_location_finding("query_api_key_auth", name, kind, scheme))
            if scheme.location == "cookie":
                findings.append(_auth_location_finding("cookie_api_key_auth", name, kind, scheme))
            if scheme.type == "unknown":
                finding_id = "metadata_only_oauth" if scheme.scopes else "unsupported_auth_scheme"
                findings.append(
                    _finding(
                        finding_id,
                        "warning" if finding_id == "unsupported_auth_scheme" else "info",
                        "auth",
                        "Security scheme is preserved as metadata only."
                        if finding_id == "metadata_only_oauth"
                        else "Security scheme is not directly executable.",
                        {"kind": kind, "name": name},
                        "Use a supported bearer/header/query/cookie API key scheme for generated direct execution.",
                        {
                            "scheme_name": scheme.scheme_name,
                            "scopes": scheme.scopes,
                            "unsupported_reason": scheme.unsupported_reason,
                        },
                    )
                )
    return findings


def _auth_location_finding(finding_id: str, name: str, kind: str, auth: AuthConfig) -> dict[str, Any]:
    return _finding(
        finding_id,
        "info",
        "auth",
        "Security scheme uses a non-header API key location.",
        {"kind": kind, "name": name},
        "Verify generated runner and proxy credential injection before production Agent use.",
        {"scheme_name": auth.scheme_name, "location": auth.location, "name": auth.name},
    )


def _server_findings(name: str, kind: str, servers: list[Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if len(servers) > 1:
        findings.append(
            _finding(
                "multiple_servers_present",
                "info",
                "execution",
                "OpenAPI source defines multiple server choices.",
                {"kind": kind, "name": name},
                "Review README server choices and use API2AGENT_BASE_URL when targeting a non-default environment.",
                {"server_count": len(servers), "servers": [server.resolved_url for server in servers]},
            )
        )

    profile_sets = [set(server.profile_hints) for server in servers if server.profile_hints]
    distinct_profiles = sorted({hint for hints in profile_sets for hint in hints if hint != "production"})
    if len(distinct_profiles) > 1:
        findings.append(
            _finding(
                "ambiguous_server_profiles",
                "info",
                "execution",
                "OpenAPI servers include multiple environment/profile hints.",
                {"kind": kind, "name": name},
                "Choose the intended runtime target explicitly with API2AGENT_BASE_URL or a tool-specific override.",
                {"profile_hints": distinct_profiles},
            )
        )

    for server in servers:
        if server.is_relative:
            findings.append(
                _finding(
                    "relative_server_url",
                    "warning",
                    "execution",
                    "OpenAPI server URL is relative and needs a runtime origin.",
                    {"kind": kind, "name": name},
                    "Set API2AGENT_BASE_URL to the real provider origin before execution.",
                    {"url": server.url, "resolved_url": server.resolved_url},
                )
            )
        if server.variables:
            findings.append(
                _finding(
                    "server_variables_present",
                    "info",
                    "execution",
                    "OpenAPI server URL uses variables.",
                    {"kind": kind, "name": name},
                    "Review resolved server defaults and override the base URL at runtime when needed.",
                    {"variables": sorted(server.variables), "resolved_url": server.resolved_url},
                )
            )
    return findings


def _server_override_finding(finding_id: str, tool: Tool) -> dict[str, Any]:
    source = "path-level" if finding_id == "path_server_override" else "operation-level"
    return _finding(
        finding_id,
        "info",
        "execution",
        f"Tool uses an OpenAPI {source} server override.",
        _tool_location(tool),
        "Review tool base URL before runtime execution or proxy wiring.",
        {"base_url": tool.base_url, "server_source": tool.server_source},
    )


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


def _score_breakdown(findings: list[dict[str, Any]]) -> dict[str, Any]:
    impact_counts = {impact: 0 for impact in IMPACT_ORDER}
    finding_ids_by_impact = {impact: set() for impact in IMPACT_ORDER}
    finding_impacts: dict[str, str] = {}
    for finding in findings:
        finding_id = str(finding.get("id") or "unknown")
        impact = _finding_impact(finding)
        impact_counts[impact] += 1
        finding_ids_by_impact[impact].add(finding_id)
        current = finding_impacts.get(finding_id)
        if current is None or _impact_rank(impact) < _impact_rank(current):
            finding_impacts[finding_id] = impact

    penalties = {
        impact: impact_counts[impact] * IMPACT_PENALTIES[impact]
        for impact in IMPACT_ORDER
    }
    penalties["action_required"] = min(
        penalties["action_required"],
        len(finding_ids_by_impact["action_required"]) * ACTION_REQUIRED_FINDING_PENALTY_CAP,
    )
    penalties["metadata_review"] = min(penalties["metadata_review"], METADATA_REVIEW_PENALTY_CAP)
    penalty = sum(penalties.values())
    score = max(0, min(SCORE_BASE, SCORE_BASE - penalty))
    return {
        "base": SCORE_BASE,
        "penalty": penalty,
        "score": score,
        "impact_counts": impact_counts,
        "penalties": penalties,
        "finding_impacts": dict(sorted(finding_impacts.items())),
    }


def _finding_impact(finding: dict[str, Any]) -> str:
    finding_id = str(finding.get("id") or "unknown")
    severity = str(finding.get("severity") or "info")
    if finding_id in READINESS_FINDINGS:
        return "readiness"
    if finding_id in BLOCKING_FINDINGS:
        return "blocking"
    if finding_id in ACTION_REQUIRED_FINDINGS:
        return "action_required"
    if finding_id == "deprecated_schema_fields" and severity == "warning":
        return "review_required"
    if finding_id in REVIEW_REQUIRED_FINDINGS:
        return "review_required"
    if finding_id in METADATA_REVIEW_FINDINGS:
        return "metadata_review"
    if severity in {"warning", "error"}:
        return "review_required"
    return "metadata_review"


def _impact_rank(impact: str) -> int:
    try:
        return IMPACT_ORDER.index(impact)
    except ValueError:
        return len(IMPACT_ORDER)


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
