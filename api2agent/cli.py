from pathlib import Path
import json
import subprocess
import sys
from typing import Optional

import typer

from api2agent.capabilities.models import ProviderCandidate, RoutingDecision, RoutingPolicy
from api2agent.capabilities.failover import build_failover_policy
from api2agent.capabilities.execution import execute_capability
from api2agent.capabilities.policies import routing_policy_preset
from api2agent.capabilities.registry import capability_naming_warnings, load_provider_registry, provider_package_warnings
from api2agent.capabilities.routing import rank_providers, select_provider
from api2agent.control.models import UsageEvent
from api2agent.control.proxy import run_proxy_server
from api2agent.control.storage import UsageStore
from api2agent.filters import ToolFilter, filter_capability
from api2agent.generators.package import generate_package
from api2agent.parsers.curl import parse_curl
from api2agent.parsers.openapi import parse_openapi_file
from api2agent.replay import can_execute_replay, execute_replay

app = typer.Typer(help="Turn APIs into verified Agent capability packages.")
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
) -> None:
    """Generate an Agent Capability Package."""
    if spec is None and not curl:
        raise typer.BadParameter("Provide an OpenAPI file or --curl command.")

    if spec is not None and curl:
        raise typer.BadParameter("Use either an OpenAPI file or --curl, not both.")

    if max_tools is not None and max_tools < 1:
        raise typer.BadParameter("--max-tools must be greater than 0.")

    capability = parse_curl(curl, name=name) if curl else parse_openapi_file(spec, name=name)
    filters = ToolFilter(
        include_tags=include_tag,
        include_paths=include_path,
        include_operations=include_operation,
        max_tools=max_tools,
    )
    capability = filter_capability(capability, filters)
    if not capability.tools:
        raise typer.BadParameter("No tools matched the selected filters.")

    try:
        result = generate_package(capability, output, force=force)
    except FileExistsError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Generated capability package: {result}")


@app.command()
def test(package_dir: Path = typer.Argument(..., help="Generated package directory.")) -> None:
    """Run the generated smoke test."""
    smoke_test = package_dir / "smoke_test.py"
    if not smoke_test.exists():
        raise typer.BadParameter(f"Smoke test not found: {smoke_test}")

    result = subprocess.run([sys.executable, str(smoke_test.name)], cwd=package_dir)
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
    typer.echo(f"Capability: {capability.get('name', 'unknown')}")
    typer.echo(f"Version: {capability.get('version', 'unknown')}")
    typer.echo(f"Base URL: {capability.get('base_url') or '(none)'}")
    typer.echo(f"Auth: {_format_auth(auth)}")
    typer.echo("")
    typer.echo("Tools:")

    tools = capability.get("tools") or []
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
        typer.echo(
            f"  - {tool.get('name')}: {tool.get('method')} {tool.get('path')} "
            f"[{tool.get('safety', 'unknown')}] required={required_label}{base_label}"
        )
        for detail in _format_tool_details(tool):
            typer.echo(f"    {detail}")


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

    store = UsageStore(db)
    metrics = store.metrics_for_capability(capability_id, include_shadow=not exclude_shadow_metrics)
    selected = select_provider(providers, metrics, policy)
    ranked = rank_providers(providers, metrics, policy)
    decision = RoutingDecision(
        capability_id=capability_id,
        strategy=policy.strategy,
        preset=preset,
        selected_provider_id=selected.provider_id if selected else None,
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

    env = auth.get("env") or "(missing env name)"
    header = auth.get("header") or "(default header)"
    return f"{auth_type} via {header}, env={env}"


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
            details.append(f"{location}: " + ", ".join(_format_parameter(parameter) for parameter in parameters))

    request_body = tool.get("request_body") or {}
    if request_body:
        required = " required" if request_body.get("required") else ""
        details.append(f"body: {_format_schema(request_body.get('schema') or {})}{required}")

    return details


def _format_parameter(parameter: dict) -> str:
    required = " required" if parameter.get("required") else ""
    return f"{parameter.get('name')} {_format_schema(parameter.get('schema') or {})}{required}"


def _format_schema(schema: dict) -> str:
    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties") or {}
        if not properties:
            return "object"
        fields = ", ".join(f"{name}:{_format_schema(value)}" for name, value in properties.items())
        return f"object {{{fields}}}"
    if schema_type == "array":
        return f"array[{_format_schema(schema.get('items') or {})}]"
    if "oneOf" in schema:
        return "oneOf[" + " | ".join(_format_schema(item) for item in schema["oneOf"]) + "]"
    if "anyOf" in schema:
        return "anyOf[" + " | ".join(_format_schema(item) for item in schema["anyOf"]) + "]"

    label = str(schema_type or "unknown")
    if "default" in schema:
        label += f" default={schema['default']}"
    return label


if __name__ == "__main__":
    app()
