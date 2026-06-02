from pathlib import Path
import json
import os
import subprocess
import sys
from typing import Optional

import typer

from api2agent.capabilities.models import ProviderCandidate, RoutingDecision, RoutingPolicy
from api2agent.capabilities.failover import build_failover_policy
from api2agent.capabilities.execution import execute_capability
from api2agent.capabilities.policies import routing_policy_preset
from api2agent.capabilities.registry import capability_naming_warnings, load_provider_registry, provider_package_warnings
from api2agent.capabilities.routing import rank_providers, select_provider, select_provider_region
from api2agent.benchmark import run_generated_package_latency_benchmark
from api2agent.control.models import UsageEvent
from api2agent.control.proxy import run_proxy_server
from api2agent.control.storage import UsageStore
from api2agent.diagnostics import (
    diagnose_capability_file,
    diagnostics_summary_line,
    format_diagnostics,
    load_package_diagnostics,
)
from api2agent.filters import ToolFilter, filter_capability
from api2agent.generators.package import generate_package
from api2agent.parsers.curl import parse_curl
from api2agent.parsers.openapi import parse_openapi_file
from api2agent.parsers.postman import parse_postman_file
from api2agent.replay import can_execute_replay, execute_replay
from api2agent.response_docs import format_response_summary, response_category_counts
from api2agent.schema_shaping import SchemaDirection, merge_schema_hint_counts, schema_hint_counts, summarize_schema

app = typer.Typer(help="Turn APIs into verified Agent capability packages.")
LARGE_PACKAGE_TOOL_WARNING_THRESHOLD = 50
SUMMARY_LIST_LIMIT = 5
TOOL_RESPONSE_SUMMARY_LIMIT = 2
SUMMARY_DETAIL_MAX_CHARS = 180
SCHEMA_HINT_PRIORITY = [
    "conditional_schema",
    "dependent_schema",
    "unsupported_schema_keywords",
    "deprecated_schema_fields",
    "schema_keywords",
    "string_constraints",
    "numeric_constraints",
    "array_constraints",
    "discriminators",
    "discriminator_mappings",
]
DECISION_USAGE_CONTRACT_VERSION = "decision_usage.v0.1"
REPLAY_CONTRACT_VERSION = "replay.v0.1"
GOLDEN_TRACE_CONTRACT_VERSION = "golden_trace.v0.1"
CREDENTIAL_AUDIT_CONTRACT_VERSION = "credential_audit.v0.1"
CREDENTIAL_METADATA_AUDIT_FIELDS = {
    "credential_id",
    "owner_type",
    "owner_id",
    "provider_id",
    "auth_type",
    "injection_mode",
    "injection_name",
    "source",
    "secret_ref",
    "scope",
    "status",
    "expires_at",
    "rotation_hint",
}
CREDENTIAL_ERROR_TYPES = {
    "credential_disabled",
    "credential_expired",
    "credential_resolution_failed",
    "credential_scope_denied",
    "invalid_credential",
    "missing_credential",
    "missing_credential_secret",
}


@app.command()
def generate(
    spec: Optional[Path] = typer.Argument(
        None,
        help="OpenAPI JSON/YAML file to convert.",
    ),
    curl: Optional[str] = typer.Option(
        None,
        "--curl",
        help="curl command to convert into a one-tool package.",
    ),
    postman: Optional[Path] = typer.Option(
        None,
        "--postman",
        help="Postman Collection JSON file to convert.",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Override generated capability name.",
    ),
    output: Path = typer.Option(
        Path("api2agent-output"),
        "--output",
        "-o",
        help="Output directory.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite generated files in a non-empty output directory.",
    ),
    include_tag: list[str] = typer.Option(
        [],
        "--include-tag",
        help="Only include OpenAPI operations with this tag. Can be used multiple times.",
    ),
    include_path: list[str] = typer.Option(
        [],
        "--include-path",
        help="Only include paths matching this exact path, substring, or glob. Can be used multiple times.",
    ),
    include_operation: list[str] = typer.Option(
        [],
        "--include-operation",
        help="Only include operations matching this operationId or generated tool name. Can be used multiple times.",
    ),
    max_tools: Optional[int] = typer.Option(
        None,
        "--max-tools",
        help="Keep at most this many tools after other filters.",
    ),
    provider_region: Optional[str] = typer.Option(
        None,
        "--provider-region",
        help="Optional provider region metadata for generated packages, e.g. us-east or cn.",
    ),
) -> None:
    """Generate an Agent Capability Package."""
    source_count = sum(1 for source in [spec, curl, postman] if source is not None)
    if source_count == 0:
        raise typer.BadParameter("Provide an OpenAPI file, --curl command, or --postman collection.")

    if source_count > 1:
        raise typer.BadParameter("Use exactly one input source: OpenAPI file, --curl, or --postman.")

    if max_tools is not None and max_tools < 1:
        raise typer.BadParameter("--max-tools must be greater than 0.")

    filters = ToolFilter(
        include_tags=include_tag,
        include_paths=include_path,
        include_operations=include_operation,
        max_tools=max_tools,
    )
    source_kind = "curl" if curl else "postman" if postman else "openapi"
    if curl:
        capability = parse_curl(curl, name=name)
        original_tool_count = len(capability.tools)
        capability = filter_capability(capability, filters)
    elif postman:
        capability = parse_postman_file(postman, name=name)
        original_tool_count = len(capability.tools)
        capability = filter_capability(capability, filters)
    else:
        capability = parse_openapi_file(spec, name=name, filters=filters)
        original_tool_count = _openapi_original_tool_count_for_warning(spec, capability, filters)
    if provider_region:
        capability = capability.model_copy(
            update={
                "provider_region": provider_region,
                "provider_regions": [provider_region],
            }
        )
    if not capability.tools:
        raise typer.BadParameter("No tools matched the selected filters.")

    try:
        result = generate_package(capability, output, force=force)
    except FileExistsError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Generated capability package: {result}")
    diagnostics = load_package_diagnostics(result)
    if diagnostics is not None:
        typer.echo(diagnostics_summary_line(diagnostics))
    for warning in _generation_warnings(source_kind, original_tool_count, len(capability.tools), filters):
        typer.echo(warning)


@app.command()
def test(
    package_dir: Path = typer.Argument(..., help="Generated package directory."),
    allow_write: bool = typer.Option(
        False,
        "--allow-write",
        help="Explicitly run the generated manual write/delete test instead of the read-only smoke test.",
    ),
    tool_name: Optional[str] = typer.Option(
        None,
        "--tool",
        help="Run a specific generated tool instead of the default smoke/manual test.",
    ),
    params: str = typer.Option("{}", "--params", help="JSON object with params for --tool."),
) -> None:
    """Run the generated smoke test, or an explicit manual write test."""
    if tool_name is not None:
        _run_specific_package_tool(package_dir, tool_name=tool_name, params=params, allow_write=allow_write)
        return

    test_file = package_dir / ("manual_write_test.py" if allow_write else "smoke_test.py")
    if not test_file.exists():
        raise typer.BadParameter(f"Test file not found: {test_file}")

    env = None
    if allow_write:
        env = dict(os.environ)
        env["API2AGENT_ALLOW_WRITE_TEST"] = "1"

    result = subprocess.run([sys.executable, str(test_file.name)], cwd=package_dir, env=env)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


def _run_specific_package_tool(
    package_dir: Path,
    *,
    tool_name: str,
    params: str,
    allow_write: bool,
) -> None:
    capability_path = package_dir / "capability.json"
    runner_path = package_dir / "runner.py"
    if not capability_path.exists():
        raise typer.BadParameter(f"Capability file not found: {capability_path}")
    if not runner_path.exists():
        raise typer.BadParameter(f"Runner file not found: {runner_path}")

    try:
        parsed_params = json.loads(params)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("--params must be valid JSON.") from exc
    if not isinstance(parsed_params, dict):
        raise typer.BadParameter("--params must be a JSON object.")

    capability = json.loads(capability_path.read_text(encoding="utf-8"))
    tool = next((item for item in capability.get("tools") or [] if item.get("name") == tool_name), None)
    if tool is None:
        raise typer.BadParameter(f"Tool not found: {tool_name}")

    safety = tool.get("safety")
    if safety in {"write", "delete"} and not allow_write:
        raise typer.BadParameter("Write/delete tools require --allow-write.")

    env = None
    if allow_write:
        env = dict(os.environ)
        env["API2AGENT_ALLOW_WRITE_TEST"] = "1"

    code = (
        "import json, sys\n"
        "from runner import execute_tool\n"
        "result = execute_tool(sys.argv[1], json.loads(sys.argv[2]))\n"
        "print(result)\n"
        "raise SystemExit(0 if result.get('ok') else 1)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, tool_name, json.dumps(parsed_params)],
        cwd=package_dir,
        env=env,
    )
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command()
def inspect(
    package_dir: Path = typer.Argument(..., help="Generated package directory."),
    json_output: bool = typer.Option(False, "--json", help="Print raw capability JSON."),
    all_tools: bool = typer.Option(False, "--all", help="Print all tools, even for large packages."),
    limit: int = typer.Option(50, "--limit", help="Maximum tools to print before truncating inspect output."),
) -> None:
    """Inspect a generated capability package."""
    capability_path = package_dir / "capability.json"
    if not capability_path.exists():
        raise typer.BadParameter(f"Capability file not found: {capability_path}")

    capability = json.loads(capability_path.read_text(encoding="utf-8"))
    if json_output:
        typer.echo(json.dumps(capability, indent=2, ensure_ascii=False))
        return

    if limit < 1:
        raise typer.BadParameter("--limit must be greater than 0.")

    auth = capability.get("auth") or {}
    servers = capability.get("servers") or []
    typer.echo(f"Capability: {capability.get('name', 'unknown')}")
    typer.echo(f"Version: {capability.get('version', 'unknown')}")
    typer.echo(f"Base URL: {capability.get('base_url') or '(none)'}")
    typer.echo(f"Auth: {_format_auth(auth)}")
    if servers:
        typer.echo(
            "Servers: "
            + f"{len(servers)}"
            + _format_server_hints(servers)
        )
    tools = capability.get("tools") or []
    if tools:
        summary = _tool_summary(tools)
        typer.echo(f"Tool count: {len(tools)}")
        typer.echo(
            "Safety: "
            + ", ".join(f"{key}={value}" for key, value in summary["safety_counts"].items())
        )
        if summary["top_tags"]:
            typer.echo(
                "Top tags: "
                + _format_ranked_items(summary["top_tags"], label_key="tag")
            )
        if summary["top_path_prefixes"]:
            typer.echo(
                "Top path prefixes: "
                + _format_ranked_items(summary["top_path_prefixes"], label_key="prefix")
            )
        if summary["schema_hints"]:
            typer.echo(
                "Schema hints: "
                + _format_counts(summary["schema_hints"], priority=SCHEMA_HINT_PRIORITY)
            )
        if summary["response_categories"]:
            typer.echo(
                "Response categories: "
                + _format_counts(summary["response_categories"])
            )
        if len(tools) > LARGE_PACKAGE_TOOL_WARNING_THRESHOLD:
            typer.echo(
                "Large package hint: regenerate with --include-tag, --include-path, "
                "--include-operation, or --max-tools before wiring this into an Agent."
            )
    diagnostics = load_package_diagnostics(package_dir)
    if diagnostics is not None:
        typer.echo(diagnostics_summary_line(diagnostics))
    typer.echo("")
    typer.echo("Tools:")

    if not tools:
        typer.echo("  (none)")
        return

    visible_tools = tools if all_tools else tools[:limit]
    if len(tools) > len(visible_tools):
        typer.echo(f"  showing {len(visible_tools)} of {len(tools)} tools; use --all to print every tool")

    for tool in visible_tools:
        params = tool.get("parameters") or []
        required = [param["name"] for param in params if param.get("required")]
        request_body = tool.get("request_body") or {}
        if request_body.get("required"):
            required.append("body")

        required_label = ", ".join(required) if required else "none"
        base_label = f" base={tool.get('base_url')}" if tool.get("base_url") else ""
        server_label = f" server={tool.get('server_source')}" if tool.get("server_source") in {"path", "operation"} else ""
        typer.echo(
            f"  - {tool.get('name')}: {tool.get('method')} {tool.get('path')} "
            f"[{tool.get('safety', 'unknown')}] required={required_label}{base_label}{server_label}"
        )
        for detail in _format_tool_details(tool):
            typer.echo(f"    {detail}")


@app.command()
def diagnose(
    package_dir: Path = typer.Argument(..., help="Generated package directory."),
    json_output: bool = typer.Option(False, "--json", help="Print raw diagnostics JSON."),
) -> None:
    """Diagnose generated capability package quality."""
    capability_path = package_dir / "capability.json"
    if not capability_path.exists():
        raise typer.BadParameter(f"Capability file not found: {capability_path}")

    diagnostics = load_package_diagnostics(package_dir)
    if diagnostics is None:
        diagnostics = diagnose_capability_file(capability_path)

    if json_output:
        typer.echo(json.dumps(diagnostics, indent=2, ensure_ascii=False))
        return

    for line in format_diagnostics(diagnostics):
        typer.echo(line)


@app.command()
def run(package_dir: Path = typer.Argument(..., help="Generated package directory.")) -> None:
    """Run the generated MCP stdio server."""
    server = package_dir / "mcp_server.py"
    if not server.exists():
        raise typer.BadParameter(f"MCP server not found: {server}")

    result = subprocess.run([sys.executable, str(server.name)], cwd=package_dir)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command()
def proxy(
    host: str = typer.Option("127.0.0.1", "--host", help="Proxy host."),
    port: int = typer.Option(8765, "--port", help="Proxy port."),
    db: Path = typer.Option(Path("api2agent-usage.sqlite"), "--db", help="SQLite database for usage events."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Optional Bearer token required by the proxy."),
    quota: Optional[int] = typer.Option(None, "--quota", help="Optional max calls per project."),
    credential_config: Optional[Path] = typer.Option(
        None,
        "--credential-config",
        help="JSON/YAML file containing project-level credentials for proxy injection.",
    ),
) -> None:
    """Run the local API2Agent proxy for controllable execution."""
    if quota is not None and quota < 1:
        raise typer.BadParameter("--quota must be greater than 0.")

    typer.echo(f"API2Agent proxy listening on http://{host}:{port}")
    typer.echo(f"Usage database: {db}")
    if credential_config is not None:
        typer.echo(f"Credential config: {credential_config}")
    if quota is not None:
        typer.echo(f"Project quota: {quota} calls")

    try:
        run_proxy_server(
            host=host,
            port=port,
            db_path=db,
            api_key=api_key,
            quota=quota,
            credential_config=credential_config,
        )
    except KeyboardInterrupt:
        typer.echo("Proxy stopped.")


@app.command()
def usage(
    db: Path = typer.Option(Path("api2agent-usage.sqlite"), "--db", help="SQLite database for usage events."),
    project_id: Optional[str] = typer.Option(None, "--project-id", help="Filter usage by project id."),
    credential_audit: bool = typer.Option(False, "--credential-audit", help="Print credential audit events."),
    limit: int = typer.Option(50, "--limit", help="Maximum credential audit events to print."),
    json_output: bool = typer.Option(False, "--json", help="Print raw usage summary JSON."),
) -> None:
    """Print usage metrics recorded by the local proxy."""
    if limit < 1:
        raise typer.BadParameter("--limit must be greater than 0.")

    store = UsageStore(db)
    if credential_audit:
        payload = _credential_audit_payload(store, project_id=project_id, limit=limit)
        if json_output:
            typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
            return
        _print_credential_audit(payload)
        return

    summary = store.summarize(project_id)
    payload = summary.model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    typer.echo(f"Project: {payload.get('project_id') or '(all)'}")
    typer.echo(f"Total calls: {payload['total_calls']}")
    typer.echo(f"Successful calls: {payload['successful_calls']}")
    typer.echo(f"Failed calls: {payload['failed_calls']}")
    typer.echo(f"Success rate: {payload['success_rate']:.2%}")
    typer.echo(f"Average latency: {payload['average_latency_ms']:.2f} ms")
    typer.echo(f"Estimated cost: {payload['estimated_cost']:.4f}")
    if payload["error_counts"]:
        typer.echo("Errors:")
        for error_type, count in payload["error_counts"].items():
            typer.echo(f"  - {error_type}: {count}")


def _credential_audit_payload(store: UsageStore, project_id: str | None, limit: int) -> dict:
    events = [
        event
        for event in store.list_usage_events(project_id=project_id, limit=limit)
        if _is_credential_audit_event(event)
    ]
    failure_counts: dict[str, int] = {}
    for event in events:
        if event.error_type in CREDENTIAL_ERROR_TYPES:
            failure_counts[event.error_type] = failure_counts.get(event.error_type, 0) + 1

    return {
        "contract_version": CREDENTIAL_AUDIT_CONTRACT_VERSION,
        "project_id": project_id,
        "count": len(events),
        "credential_failure_counts": failure_counts,
        "events": [_credential_audit_event(event) for event in events],
    }


def _generation_warnings(
    source_kind: str,
    original_tool_count: int,
    generated_tool_count: int,
    filters: ToolFilter,
) -> list[str]:
    if source_kind not in {"openapi", "postman"} or generated_tool_count <= LARGE_PACKAGE_TOOL_WARNING_THRESHOLD:
        return []

    hint = (
        "Warning: generated package contains "
        f"{generated_tool_count} tools, which is likely too many for Agent tool selection. "
        "Narrow the package with --include-tag, --include-path, --include-operation, or --max-tools."
    )
    if filters.is_empty:
        return [hint]
    return [
        hint
        + f" Filters reduced the source from {original_tool_count} to {generated_tool_count} tools; "
        "consider narrowing further."
    ]


def _openapi_original_tool_count_for_warning(spec: Path, capability, filters: ToolFilter) -> int:
    if filters.max_tools is not None and len(capability.tools) <= LARGE_PACKAGE_TOOL_WARNING_THRESHOLD:
        return len(capability.tools)

    from api2agent.parsers.openapi import count_openapi_operations_file

    return count_openapi_operations_file(spec)


def _is_credential_audit_event(event: UsageEvent) -> bool:
    return bool(event.credential_reference or event.error_type in CREDENTIAL_ERROR_TYPES)


def _credential_audit_event(event: UsageEvent) -> dict:
    credential_metadata = None
    if event.request_metadata and isinstance(event.request_metadata.get("credential"), dict):
        credential_metadata = {
            key: value
            for key, value in event.request_metadata["credential"].items()
            if key in CREDENTIAL_METADATA_AUDIT_FIELDS
        }

    return {
        "id": event.id,
        "created_at": event.created_at.isoformat(),
        "project_id": event.project_id,
        "capability_id": event.capability_id,
        "provider_id": event.provider_id,
        "tool_id": event.tool_id,
        "execution_mode": event.execution_mode,
        "success": event.success,
        "error_type": event.error_type,
        "credential_reference": event.credential_reference,
        "credential_metadata": credential_metadata,
    }


def _print_credential_audit(payload: dict) -> None:
    typer.echo(f"Credential audit events: {payload['count']}")
    if payload["credential_failure_counts"]:
        typer.echo("Credential failures:")
        for error_type, count in payload["credential_failure_counts"].items():
            typer.echo(f"  - {error_type}: {count}")
    if not payload["events"]:
        return
    for event in payload["events"]:
        typer.echo(
            f"{event['id']} / {event['project_id']} / {event['capability_id']} / "
            f"{event['provider_id']} / {event['tool_id']}"
        )
        typer.echo(f"  Reference: {event['credential_reference'] or '(none)'}")
        typer.echo(f"  Success: {event['success']}")
        if event["error_type"]:
            typer.echo(f"  Error: {event['error_type']}")
        metadata = event.get("credential_metadata") or {}
        if metadata:
            label_parts = []
            if metadata.get("credential_id"):
                label_parts.append(f"id={metadata['credential_id']}")
            if metadata.get("owner_type") or metadata.get("owner_id"):
                label_parts.append(f"owner={metadata.get('owner_type')}:{metadata.get('owner_id')}")
            if metadata.get("status"):
                label_parts.append(f"status={metadata['status']}")
            if metadata.get("expires_at"):
                label_parts.append(f"expires_at={metadata['expires_at']}")
            if label_parts:
                typer.echo("  Metadata: " + ", ".join(label_parts))


@app.command("benchmark-package")
def benchmark_package(
    package_dir: Path = typer.Argument(..., help="Generated package directory containing runner.py and capability.json."),
    tool_name: str = typer.Option(..., "--tool", help="Generated tool name to benchmark."),
    params: str = typer.Option("{}", "--params", help="JSON object with tool params."),
    iterations: int = typer.Option(3, "--iterations", help="Number of runs per enabled execution mode."),
    proxy_url: Optional[str] = typer.Option(None, "--proxy-url", help="Optional API2Agent proxy URL for proxy-mode timing."),
    direct: bool = typer.Option(True, "--direct/--no-direct", help="Run direct generated-package timing."),
    project_id: Optional[str] = typer.Option(None, "--project-id", help="Project id used for proxy benchmark payloads."),
    provider_id: Optional[str] = typer.Option(None, "--provider-id", help="Provider id used for proxy benchmark payloads."),
    capability_id: Optional[str] = typer.Option(None, "--capability-id", help="Capability id used for proxy benchmark payloads."),
    provider_region: Optional[str] = typer.Option(None, "--provider-region", help="Provider region override for proxy benchmark payloads."),
    json_output: bool = typer.Option(False, "--json", help="Print raw benchmark JSON."),
) -> None:
    """Benchmark a generated package tool in direct and/or proxy mode."""
    if iterations < 1:
        raise typer.BadParameter("--iterations must be greater than 0.")
    try:
        parsed_params = json.loads(params)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("--params must be valid JSON.") from exc
    if not isinstance(parsed_params, dict):
        raise typer.BadParameter("--params must be a JSON object.")

    env = {}
    if project_id:
        env["API2AGENT_PROJECT_ID"] = project_id
    if provider_id:
        env["API2AGENT_PROVIDER_ID"] = provider_id
    if capability_id:
        env["API2AGENT_CAPABILITY_ID"] = capability_id
    if provider_region:
        env["API2AGENT_PROVIDER_REGION"] = provider_region

    try:
        payload = run_generated_package_latency_benchmark(
            package_dir=package_dir,
            tool_name=tool_name,
            params=parsed_params,
            iterations=iterations,
            direct=direct,
            proxy_url=proxy_url,
            env=env,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    capability = payload["capability"]
    typer.echo(f"Package: {payload['package_dir']}")
    typer.echo(f"Capability: {capability.get('name')}")
    typer.echo(f"Provider region: {capability.get('provider_region') or '(none)'}")
    typer.echo(f"Tool: {payload['tool']['name']}")
    typer.echo(f"Iterations: {payload['iterations']}")
    for mode, stats in payload["runs"].items():
        typer.echo(f"{mode}:")
        typer.echo(f"  Runs: {stats['runs']}")
        typer.echo(f"  Success rate: {stats['success_rate']:.2%}")
        typer.echo(f"  p50 latency: {_format_optional_ms(stats['p50_latency_ms'])}")
        typer.echo(f"  p95 latency: {_format_optional_ms(stats['p95_latency_ms'])}")


@app.command()
def ledger(
    db: Path = typer.Option(Path("api2agent-usage.sqlite"), "--db", help="SQLite database for usage events."),
    project_id: Optional[str] = typer.Option(None, "--project-id", help="Filter ledger by project id."),
    capability_id: Optional[str] = typer.Option(None, "--capability-id", help="Filter ledger by capability id."),
    provider_id: Optional[str] = typer.Option(None, "--provider-id", help="Filter ledger by provider id."),
    month: Optional[str] = typer.Option(None, "--month", help="Filter ledger by YYYY-MM month."),
    group_by_mode: bool = typer.Option(False, "--group-by-mode", help="Group ledger rows by execution mode."),
    golden_only: bool = typer.Option(False, "--golden-only", help="Only include usage events marked as golden traces."),
    json_output: bool = typer.Option(False, "--json", help="Print raw ledger JSON."),
) -> None:
    """Print a billing-ready local usage ledger without charging money."""
    if month is not None:
        parts = month.split("-")
        if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
            raise typer.BadParameter("--month must use YYYY-MM format.")

    rows = UsageStore(db).ledger(
        project_id=project_id,
        capability_id=capability_id,
        provider_id=provider_id,
        month=month,
        group_by_mode=group_by_mode,
        golden_only=golden_only,
    )
    payload = [row.model_dump(mode="json") for row in rows]
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if not rows:
        typer.echo("No usage ledger rows.")
        return

    for row in rows:
        label = f"{row.project_id} / {row.capability_id} / {row.provider_id}"
        if row.execution_mode:
            label += f" / {row.execution_mode}"
        typer.echo(label)
        typer.echo(f"  Calls: {row.total_calls}")
        typer.echo(f"  Success rate: {row.success_rate:.2%}")
        typer.echo(f"  Average latency: {row.average_latency_ms:.2f} ms")
        typer.echo(f"  Estimated cost: {row.estimated_cost:.4f}")


@app.command("decision")
def inspect_decision(
    decision_id: str = typer.Argument(..., help="Routing decision id to inspect."),
    db: Path = typer.Option(Path("api2agent-usage.sqlite"), "--db", help="SQLite database for usage events."),
    json_output: bool = typer.Option(False, "--json", help="Print raw decision audit JSON."),
) -> None:
    """Inspect one routing decision and its correlated usage events."""
    store = UsageStore(db)
    decision = store.get_routing_decision(decision_id)
    if decision is None:
        raise typer.BadParameter(f"Routing decision not found: {decision_id}")

    usage_events = store.usage_for_routing_decision(decision_id)
    payload = {
        "contract_version": DECISION_USAGE_CONTRACT_VERSION,
        "decision": decision.model_dump(mode="json"),
        "usage_events": [event.model_dump(mode="json") for event in usage_events],
        "usage_event_count": len(usage_events),
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    typer.echo(f"Decision: {decision.id}")
    typer.echo(f"Project: {decision.project_id}")
    typer.echo(f"Capability: {decision.capability_id}")
    typer.echo(f"Strategy: {decision.strategy}")
    if decision.preset:
        typer.echo(f"Preset: {decision.preset}")
    typer.echo(f"Selected provider: {decision.selected_provider_id or '(none)'}")
    if decision.ranked_provider_ids:
        typer.echo("Ranked providers: " + ", ".join(decision.ranked_provider_ids))
    if decision.failover_policy:
        typer.echo("Failover policy:")
        typer.echo(json.dumps(decision.failover_policy.model_dump(mode="json"), indent=2, ensure_ascii=False))
    typer.echo(f"Usage events: {len(usage_events)}")
    for event in usage_events:
        status = event.status_code if event.status_code is not None else "(none)"
        typer.echo(
            f"  - {event.provider_id}/{event.tool_id}: success={event.success} "
            f"status={status} latency={event.latency_ms:.2f}ms cost={event.estimated_cost:.4f}"
        )


@app.command("replay")
def replay_usage_event(
    usage_event_id: str = typer.Argument(..., help="Usage event id to prepare for replay."),
    db: Path = typer.Option(Path("api2agent-usage.sqlite"), "--db", help="SQLite database for usage events."),
    execute: bool = typer.Option(False, "--execute", help="Re-run the provider call when exact replay is supported."),
    record: bool = typer.Option(False, "--record", help="Record replay execution as a replay usage event."),
    json_output: bool = typer.Option(False, "--json", help="Print raw replay preflight JSON."),
) -> None:
    """Inspect a usage event and report whether it can be deterministically replayed."""
    if record and not execute:
        raise typer.BadParameter("--record requires --execute.")

    store = UsageStore(db)
    event = store.get_usage_event(usage_event_id)
    if event is None:
        raise typer.BadParameter(f"Usage event not found: {usage_event_id}")

    decision = store.get_routing_decision(event.routing_decision_id) if event.routing_decision_id else None
    missing_for_exact_replay = _missing_replay_fields(event)
    replayable = can_execute_replay(event)
    warnings = []
    if missing_for_exact_replay:
        warnings.append("Exact replay metadata is incomplete for this usage event.")
    if not replayable:
        warnings.append("Replay execution is not available for this usage event.")
    replay_result = execute_replay(event) if execute else None
    recorded_event = _record_replay_event(store, event, replay_result) if record and replay_result is not None else None
    payload = {
        "contract_version": REPLAY_CONTRACT_VERSION,
        "usage_event": event.model_dump(mode="json"),
        "routing_decision": decision.model_dump(mode="json") if decision else None,
        "replayable": replayable,
        "exact_replay_metadata_ready": not missing_for_exact_replay,
        "executed": execute,
        "replay_result": replay_result,
        "recorded_usage_event_id": recorded_event.id if recorded_event else None,
        "warnings": warnings,
        "missing_for_exact_replay": missing_for_exact_replay,
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    typer.echo(f"Usage event: {event.id}")
    typer.echo(f"Replayable: {payload['replayable']}")
    typer.echo(f"Executed: {payload['executed']}")
    if payload["recorded_usage_event_id"]:
        typer.echo(f"Recorded usage event: {payload['recorded_usage_event_id']}")
    typer.echo(f"Project: {event.project_id}")
    typer.echo(f"Capability: {event.capability_id}")
    typer.echo(f"Provider: {event.provider_id}")
    typer.echo(f"Tool: {event.tool_id}")
    typer.echo(f"Success: {event.success}")
    if decision:
        typer.echo(f"Routing decision: {decision.id}")
        typer.echo(f"Strategy: {decision.strategy}")
        if decision.ranked_provider_ids:
            typer.echo("Ranked providers: " + ", ".join(decision.ranked_provider_ids))
    typer.echo("Warnings:")
    for warning in warnings:
        typer.echo(f"  - {warning}")
    if replay_result is not None:
        typer.echo("Replay result:")
        typer.echo(json.dumps(replay_result, indent=2, ensure_ascii=False))


@app.command("golden")
def mark_golden_event(
    usage_event_id: Optional[str] = typer.Argument(None, help="Usage event id to mark as a golden trace."),
    db: Path = typer.Option(Path("api2agent-usage.sqlite"), "--db", help="SQLite database for usage events."),
    unset: bool = typer.Option(False, "--unset", help="Remove the golden marker from this usage event."),
    list_traces: bool = typer.Option(False, "--list", help="List golden traces instead of marking one event."),
    project_id: Optional[str] = typer.Option(None, "--project-id", help="Filter golden traces by project id."),
    capability_id: Optional[str] = typer.Option(None, "--capability-id", help="Filter golden traces by capability id."),
    provider_id: Optional[str] = typer.Option(None, "--provider-id", help="Filter golden traces by provider id."),
    execution_mode: Optional[str] = typer.Option(None, "--execution-mode", help="Filter golden traces by execution mode."),
    limit: int = typer.Option(50, "--limit", help="Maximum golden traces to return."),
    json_output: bool = typer.Option(False, "--json", help="Print raw golden trace JSON."),
) -> None:
    """Mark or unmark a usage event as a golden trace."""
    store = UsageStore(db)
    if limit < 1:
        raise typer.BadParameter("--limit must be greater than 0.")
    if list_traces:
        if usage_event_id is not None:
            raise typer.BadParameter("Do not pass a usage event id with --list.")
        if unset:
            raise typer.BadParameter("--unset cannot be used with --list.")
        events = store.list_usage_events(
            project_id=project_id,
            capability_id=capability_id,
            provider_id=provider_id,
            execution_mode=execution_mode,
            golden_only=True,
            limit=limit,
        )
        payload = {
            "contract_version": GOLDEN_TRACE_CONTRACT_VERSION,
            "count": len(events),
            "golden_traces": [event.model_dump(mode="json") for event in events],
        }
        if json_output:
            typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
            return

        if not events:
            typer.echo("No golden traces.")
            return
        for event in events:
            typer.echo(f"{event.id} / {event.project_id} / {event.capability_id} / {event.provider_id}")
            typer.echo(f"  Mode: {event.execution_mode}")
            typer.echo(f"  Success: {event.success}")
            typer.echo(f"  Created: {event.created_at.isoformat()}")
        return

    if usage_event_id is None:
        raise typer.BadParameter("Provide a usage event id, or use --list.")

    event = store.mark_golden(usage_event_id, is_golden=not unset)
    if event is None:
        raise typer.BadParameter(f"Usage event not found: {usage_event_id}")

    payload = {
        "contract_version": GOLDEN_TRACE_CONTRACT_VERSION,
        "usage_event": event.model_dump(mode="json"),
        "is_golden": event.is_golden,
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    typer.echo(f"Usage event: {event.id}")
    typer.echo(f"Golden: {event.is_golden}")


@app.command("registry")
def inspect_registry(
    registry: Path = typer.Argument(..., help="JSON file containing provider candidates."),
    json_output: bool = typer.Option(False, "--json", help="Print raw registry inspection JSON."),
) -> None:
    """Inspect a provider registry contract and provider summary."""
    try:
        provider_registry = load_provider_registry(registry)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    capability_counts: dict[str, int] = {}
    for provider in provider_registry.providers:
        capability_counts[provider.capability_id] = capability_counts.get(provider.capability_id, 0) + 1

    payload = {
        "contract_version": provider_registry.contract_version,
        "provider_count": len(provider_registry.providers),
        "capability_counts": capability_counts,
        "warnings": [warning.model_dump(mode="json") for warning in provider_package_warnings(provider_registry.providers)],
        "naming_warnings": [
            warning.model_dump(mode="json") for warning in capability_naming_warnings(provider_registry.providers)
        ],
        "providers": [provider.model_dump(mode="json") for provider in provider_registry.providers],
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    typer.echo(f"Contract version: {provider_registry.contract_version}")
    typer.echo(f"Providers: {len(provider_registry.providers)}")
    if capability_counts:
        typer.echo("Capabilities:")
        for capability_id, count in sorted(capability_counts.items()):
            typer.echo(f"  - {capability_id}: {count}")
    if payload["warnings"]:
        typer.echo("Warnings:")
        for warning in payload["warnings"]:
            typer.echo(f"  - [{warning['severity']}] {warning['provider_id']}: {warning['message']}")
    if payload["naming_warnings"]:
        typer.echo("Naming warnings:")
        for warning in payload["naming_warnings"]:
            typer.echo(f"  - [{warning['severity']}] {warning['provider_id']}: {warning['message']}")


@app.command()
def route(
    registry: Path = typer.Argument(..., help="JSON file containing provider candidates."),
    capability_id: str = typer.Option(..., "--capability-id", help="Capability to route."),
    db: Path = typer.Option(Path("api2agent-usage.sqlite"), "--db", help="SQLite database for usage events."),
    strategy: str = typer.Option("balanced", "--strategy", help="Routing strategy."),
    preset: Optional[str] = typer.Option(
        None,
        "--preset",
        help="Named routing policy preset: balanced, reliability_first, cost_first, latency_first.",
    ),
    exclude_shadow_metrics: bool = typer.Option(
        False,
        "--exclude-shadow-metrics",
        help="Exclude shadow execution events from routing metrics.",
    ),
    client_region: Optional[str] = typer.Option(None, "--client-region", help="Client region for region-aware routing."),
    json_output: bool = typer.Option(False, "--json", help="Print raw routing result JSON."),
) -> None:
    """Select a provider candidate for a capability using observed metrics."""
    try:
        provider_registry = load_provider_registry(registry)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    providers = [provider for provider in provider_registry.providers if provider.capability_id == capability_id]
    if not providers:
        raise typer.BadParameter(f"No providers found for capability: {capability_id}")

    try:
        policy = routing_policy_preset(preset) if preset else RoutingPolicy(strategy=strategy)
    except Exception as exc:
        label = preset or strategy
        raise typer.BadParameter(f"Invalid routing policy: {label}") from exc
    if client_region:
        policy.client_region = client_region

    store = UsageStore(db)
    metrics = store.metrics_for_capability(
        capability_id,
        include_shadow=not exclude_shadow_metrics,
        client_region=policy.client_region if policy.strategy == "region_aware_latency" else None,
    )
    selected = select_provider(providers, metrics, policy)
    ranked = rank_providers(providers, metrics, policy)
    decision = RoutingDecision(
        capability_id=capability_id,
        strategy=policy.strategy,
        preset=preset,
        client_region=policy.client_region,
        selected_provider_id=selected.provider_id if selected else None,
        selected_provider_region=select_provider_region(selected, policy.client_region) if selected else None,
        ranked_provider_ids=[provider.provider_id for provider in ranked],
        metrics=metrics,
    )
    store.record_routing_decision(decision)
    result = {
        "registry_contract_version": provider_registry.contract_version,
        "decision": decision.model_dump(mode="json"),
        "capability_id": capability_id,
        "strategy": policy.strategy,
        "preset": preset,
        "client_region": policy.client_region,
        "weights": policy.weights,
        "selected": selected.model_dump(mode="json") if selected else None,
        "ranked_provider_ids": [provider.provider_id for provider in ranked],
        "metrics": [item.model_dump(mode="json") for item in metrics],
    }

    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if selected is None:
        typer.echo("No provider selected.")
        return

    typer.echo(f"Capability: {capability_id}")
    typer.echo(f"Strategy: {policy.strategy}")
    if preset:
        typer.echo(f"Preset: {preset}")
    if policy.client_region:
        typer.echo(f"Client region: {policy.client_region}")
    typer.echo(f"Selected provider: {selected.provider_id}")
    typer.echo(f"Tool: {selected.tool_id}")
    if result["ranked_provider_ids"]:
        typer.echo("Ranked providers: " + ", ".join(result["ranked_provider_ids"]))


@app.command()
def call(
    registry: Path = typer.Argument(..., help="JSON file containing provider candidates."),
    capability_id: str = typer.Option(..., "--capability-id", help="Capability to execute."),
    params: str = typer.Option("{}", "--params", help="JSON object with capability input params."),
    db: Path = typer.Option(Path("api2agent-usage.sqlite"), "--db", help="SQLite database for usage events."),
    strategy: str = typer.Option("balanced", "--strategy", help="Routing strategy."),
    preset: Optional[str] = typer.Option(
        None,
        "--preset",
        help="Named routing policy preset: balanced, reliability_first, cost_first, latency_first.",
    ),
    proxy_url: Optional[str] = typer.Option(None, "--proxy-url", help="Proxy URL to use during provider execution."),
    failover: bool = typer.Option(False, "--failover", help="Try ranked fallback providers after a failed attempt."),
    shadow: bool = typer.Option(False, "--shadow", help="Run non-selected providers as shadow benchmark attempts."),
    shadow_provider: list[str] = typer.Option(
        [],
        "--shadow-provider",
        help="Provider id to run in shadow mode. Can be used multiple times.",
    ),
    max_attempts: Optional[int] = typer.Option(
        None,
        "--max-attempts",
        help="Maximum provider attempts when failover is enabled.",
    ),
    retry_on_status: list[int] = typer.Option(
        [],
        "--retry-on-status",
        help="HTTP status code eligible for failover. Can be used multiple times.",
    ),
    exclude_shadow_metrics: bool = typer.Option(
        False,
        "--exclude-shadow-metrics",
        help="Exclude shadow execution events from routing metrics.",
    ),
    client_region: Optional[str] = typer.Option(None, "--client-region", help="Client region for region-aware routing."),
    json_output: bool = typer.Option(False, "--json", help="Print raw call result JSON."),
) -> None:
    """Route and execute a capability through a local generated provider package."""
    try:
        provider_registry = load_provider_registry(registry)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    try:
        parsed_params = json.loads(params)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("--params must be valid JSON.") from exc
    if not isinstance(parsed_params, dict):
        raise typer.BadParameter("--params must be a JSON object.")
    if max_attempts is not None and max_attempts < 1:
        raise typer.BadParameter("--max-attempts must be greater than 0.")

    providers = provider_registry.providers
    candidate_providers = [provider for provider in providers if provider.capability_id == capability_id]
    package_warnings = provider_package_warnings(candidate_providers)
    package_errors = [warning for warning in package_warnings if warning.severity == "error"]
    if package_errors:
        detail = "; ".join(f"{warning.provider_id}: {warning.message}" for warning in package_errors)
        raise typer.BadParameter("Invalid provider package metadata: " + detail)
    try:
        policy = routing_policy_preset(preset) if preset else RoutingPolicy(strategy=strategy)
    except Exception as exc:
        label = preset or strategy
        raise typer.BadParameter(f"Invalid routing policy: {label}") from exc
    if client_region:
        policy.client_region = client_region

    result = execute_capability(
        providers=providers,
        capability_id=capability_id,
        params=parsed_params,
        store=UsageStore(db),
        policy=policy,
        preset=preset,
        proxy_url=proxy_url,
        failover=failover,
        shadow=shadow,
        shadow_provider_ids=shadow_provider or None,
        include_shadow_metrics=not exclude_shadow_metrics,
        failover_policy=build_failover_policy(
            enabled=failover,
            candidate_count=len(candidate_providers),
            max_attempts=max_attempts,
            retry_on_status_codes=retry_on_status,
        ),
    )
    result["registry_contract_version"] = provider_registry.contract_version

    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return

    typer.echo(f"Capability: {capability_id}")
    typer.echo(f"OK: {result.get('ok')}")
    decision = result.get("routing_decision") or {}
    if decision.get("selected_provider_id"):
        typer.echo(f"Selected provider: {decision['selected_provider_id']}")
    if result.get("normalized_body") is not None:
        typer.echo("Normalized result:")
        typer.echo(json.dumps(result["normalized_body"], indent=2, ensure_ascii=False))
    elif result.get("error"):
        typer.echo("Error:")
        typer.echo(json.dumps(result["error"], indent=2, ensure_ascii=False))


def _format_auth(auth: dict) -> str:
    auth_type = auth.get("type") or "none"
    if auth_type == "none":
        return "none"

    credentials = auth.get("credentials") or []
    if len(credentials) > 1:
        return "combined " + " + ".join(_format_auth_credential(credential) for credential in credentials)
    return _format_auth_credential(auth)


def _format_auth_credential(auth: dict) -> str:
    auth_type = auth.get("type") or "none"
    if auth_type == "none":
        return "none"
    env = auth.get("env") or "(missing env name)"
    if auth_type == "bearer":
        return f"bearer via Authorization, env={env}"
    location = auth.get("location")
    name = auth.get("name") or auth.get("header") or "(default name)"
    if location:
        return f"{auth_type} via {location}:{name}, env={env}"
    header = auth.get("header") or "(default header)"
    return f"{auth_type} via {header}, env={env}"


def _tool_summary(tools: list[dict]) -> dict:
    safety_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    prefix_counts: dict[str, int] = {}
    schema_hints: dict[str, int] = {}
    response_categories: dict[str, int] = {}
    for tool in tools:
        safety = str(tool.get("safety") or "unknown")
        safety_counts[safety] = safety_counts.get(safety, 0) + 1

        for tag in tool.get("tags") or []:
            tag_label = str(tag)
            tag_counts[tag_label] = tag_counts.get(tag_label, 0) + 1

        prefix = _path_prefix(str(tool.get("path") or ""))
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
        schema_counts = _tool_schema_hint_counts(tool)
        for key, value in schema_counts.items():
            schema_hints[key] = schema_hints.get(key, 0) + value
        for key, value in response_category_counts(tool.get("responses") or []).items():
            response_categories[key] = response_categories.get(key, 0) + value

    return {
        "safety_counts": _ordered_counts(safety_counts),
        "top_tags": _top_counts(tag_counts, label_key="tag"),
        "top_path_prefixes": _top_counts(prefix_counts, label_key="prefix"),
        "schema_hints": dict(sorted(schema_hints.items())),
        "response_categories": dict(sorted(response_categories.items())),
    }


def _format_server_hints(servers: list[dict]) -> str:
    hints = sorted({
        hint
        for server in servers
        for hint in (server.get("profile_hints") or [])
    })
    if not hints:
        return ""
    return " hints=" + ",".join(hints)


def _path_prefix(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "/"
    return "/" + parts[0]


def _ordered_counts(counts: dict[str, int]) -> dict[str, int]:
    order = ["read", "write", "delete", "unknown"]
    ordered = {key: counts[key] for key in order if key in counts}
    for key in sorted(counts):
        if key not in ordered:
            ordered[key] = counts[key]
    return ordered


def _top_counts(counts: dict[str, int], *, label_key: str, limit: int = 5) -> list[dict]:
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{label_key: key, "count": value} for key, value in ranked[:limit]]


def _format_ranked_items(items: list[dict], *, label_key: str, limit: int = SUMMARY_LIST_LIMIT) -> str:
    visible = items[:limit]
    rendered = [f"{item[label_key]}({item['count']})" for item in visible]
    omitted = len(items) - len(visible)
    if omitted > 0:
        rendered.append(f"+{omitted} more")
    return ", ".join(rendered)


def _format_counts(counts: dict[str, int], *, priority: list[str] | None = None, limit: int = SUMMARY_LIST_LIMIT) -> str:
    priority = priority or []
    priority_index = {key: index for index, key in enumerate(priority)}
    ranked = sorted(
        counts.items(),
        key=lambda item: (
            priority_index.get(item[0], len(priority)),
            -item[1],
            item[0],
        ),
    )
    visible = ranked[:limit]
    rendered = [f"{key}={value}" for key, value in visible]
    omitted = len(ranked) - len(visible)
    if omitted > 0:
        rendered.append(f"+{omitted} more")
    return ", ".join(rendered)


def _missing_replay_fields(event: UsageEvent) -> list[str]:
    missing = []
    if not event.request_metadata:
        missing.append("request_metadata")
    if not event.provider_runtime_reference:
        missing.append("provider_runtime_reference")
    if event.credential_reference and not can_execute_replay(event):
        missing.append("credential")
    return missing


def _record_replay_event(store: UsageStore, source_event: UsageEvent, replay_result: dict) -> UsageEvent:
    result_error = replay_result.get("error") if isinstance(replay_result.get("error"), dict) else {}
    event = UsageEvent(
        routing_decision_id=source_event.routing_decision_id,
        execution_mode="replay",
        project_id=source_event.project_id,
        capability_id=source_event.capability_id,
        provider_id=source_event.provider_id,
        tool_id=source_event.tool_id,
        method=source_event.method,
        path=source_event.path,
        status_code=replay_result.get("status_code"),
        success=bool(replay_result.get("ok")),
        latency_ms=float(replay_result.get("latency_ms") or 0.0),
        estimated_cost=source_event.estimated_cost,
        error_type=replay_result.get("error_type") or result_error.get("type"),
        request_metadata={
            "replay_source_event_id": source_event.id,
            "source_request_metadata": source_event.request_metadata,
        },
        credential_reference=source_event.credential_reference,
        provider_runtime_reference=source_event.provider_runtime_reference,
    )
    return store.record(event)


def _format_tool_details(tool: dict) -> list[str]:
    details: list[str] = []
    by_location: dict[str, list[dict]] = {"path": [], "query": [], "header": []}
    for parameter in tool.get("parameters") or []:
        location = parameter.get("location")
        if location in by_location:
            by_location[location].append(parameter)

    for location, parameters in by_location.items():
        if parameters:
            details.append(_clip_detail(f"{location}: " + ", ".join(_format_parameter(parameter) for parameter in parameters)))

    request_body = tool.get("request_body") or {}
    if request_body:
        required = " required" if request_body.get("required") else ""
        details.append(_clip_detail(f"body: {_format_schema(request_body.get('schema') or {}, direction='request')}{required}"))

    responses = tool.get("responses") or []
    if responses:
        response_summaries = _select_response_summaries(responses, limit=TOOL_RESPONSE_SUMMARY_LIMIT)
        omitted = len(responses) - len(response_summaries)
        suffix = f"; +{omitted} more responses" if omitted > 0 else ""
        details.append(
            _clip_detail(
                "responses: "
                + "; ".join(
                    format_response_summary(response, include_description=False, include_example=False)
                    for response in response_summaries
                )
                + suffix
            )
        )

    return details


def _clip_detail(text: str, *, max_chars: int = SUMMARY_DETAIL_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 4].rstrip() + " ..."


def _select_response_summaries(responses: list[dict], *, limit: int) -> list[dict]:
    if len(responses) <= limit:
        return responses

    selected: list[dict] = []
    selected_ids: set[int] = set()
    categories = response_category_counts(responses)
    priority = ["success", "client_error", "default", "server_error", "redirect", "unknown"]
    for category in priority:
        if category not in categories:
            continue
        for index, response in enumerate(responses):
            if index in selected_ids:
                continue
            if response_category_counts([response]).get(category):
                selected.append(response)
                selected_ids.add(index)
                break
        if len(selected) >= limit:
            return selected

    for index, response in enumerate(responses):
        if index in selected_ids:
            continue
        selected.append(response)
        if len(selected) >= limit:
            break
    return selected


def _format_parameter(parameter: dict) -> str:
    required = " required" if parameter.get("required") else ""
    return f"{parameter.get('name')} {_format_schema(parameter.get('schema') or {})}{required}"


def _format_schema(schema: dict, *, direction: SchemaDirection = "neutral") -> str:
    return summarize_schema(schema, direction=direction)


def _tool_schema_hint_counts(tool: dict) -> dict[str, int]:
    counts: list[dict[str, int]] = []
    for parameter in tool.get("parameters") or []:
        counts.append(schema_hint_counts(parameter.get("schema") or {}))
    request_body = tool.get("request_body") or {}
    if request_body:
        counts.append(schema_hint_counts(request_body.get("schema") or {}))
    for response in tool.get("responses") or []:
        counts.append(schema_hint_counts(response.get("schema") or {}))
    return merge_schema_hint_counts(*counts)


def _format_optional_ms(value: object) -> str:
    if value is None:
        return "(none)"
    return f"{float(value):.2f} ms"


if __name__ == "__main__":
    app()
