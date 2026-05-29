from datetime import datetime, timezone
from pathlib import Path

import httpx

from api2agent.capabilities.models import RoutingDecision
from api2agent.control.models import UsageEvent
from api2agent.control.proxy import execute_proxy_call
from api2agent.control.storage import UsageStore


def test_usage_store_summarizes_events(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="github_repos",
            provider_id="github",
            tool_id="list_repos",
            method="GET",
            path="/repos",
            status_code=200,
            success=True,
            latency_ms=100,
            estimated_cost=0.01,
        )
    )
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="github_repos",
            provider_id="github",
            tool_id="list_repos",
            method="GET",
            path="/repos",
            status_code=500,
            success=False,
            latency_ms=300,
            estimated_cost=0.01,
            error_type="http_status",
        )
    )

    summary = store.summarize("local")

    assert summary.total_calls == 2
    assert summary.successful_calls == 1
    assert summary.failed_calls == 1
    assert summary.success_rate == 0.5
    assert summary.average_latency_ms == 200
    assert summary.estimated_cost == 0.02
    assert summary.error_counts == {"http_status": 1}


def test_proxy_call_forwards_and_records_usage(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    captured = {}

    def fake_forwarder(method, url, options):
        captured["method"] = method
        captured["url"] = url
        captured["options"] = options
        return httpx.Response(200, json={"ok": True})

    status, result = execute_proxy_call(
        {
            "project_id": "local",
            "routing_decision_id": "decision_123",
            "capability_id": "github_repos",
            "provider_id": "github",
            "tool_id": "list_repos",
            "estimated_cost": 0.01,
            "request": {
                "method": "GET",
                "url": "https://api.github.com/repos",
                "headers": {"Authorization": "Bearer token"},
                "params": {"visibility": "public"},
            },
        },
        store=store,
        forwarder=fake_forwarder,
    )

    summary = store.summarize("local")
    correlated_events = store.usage_for_routing_decision("decision_123")

    assert status == 200
    assert result["ok"] is True
    assert result["proxied"] is True
    assert captured["method"] == "GET"
    assert captured["url"] == "https://api.github.com/repos"
    assert captured["options"]["headers"]["Authorization"] == "Bearer token"
    assert summary.total_calls == 1
    assert summary.successful_calls == 1
    assert summary.estimated_cost == 0.01
    assert len(correlated_events) == 1
    assert correlated_events[0].routing_decision_id == "decision_123"
    assert correlated_events[0].credential_reference == "header:Authorization"
    assert correlated_events[0].request_metadata["headers"]["Authorization"] == "[REDACTED]"


def test_usage_store_records_routing_decision(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    decision = RoutingDecision(
        id="decision_123",
        project_id="local",
        capability_id="github_repos",
        strategy="lowest_cost",
        selected_provider_id="github",
        ranked_provider_ids=["github"],
        failover_policy={"enabled": True, "max_attempts": 2, "retry_on_status_codes": [500]},
    )

    store.record_routing_decision(decision)
    stored = store.get_routing_decision("decision_123")

    assert stored is not None
    assert stored.id == "decision_123"
    assert stored.capability_id == "github_repos"
    assert stored.selected_provider_id == "github"
    assert stored.failover_policy is not None
    assert stored.failover_policy.max_attempts == 2


def test_usage_store_gets_usage_event_by_id(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            id="event_123",
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            request_metadata={"params": {"q": "demo"}},
            provider_runtime_reference="test:runtime",
        )
    )

    stored = store.get_usage_event("event_123")

    assert stored is not None
    assert stored.id == "event_123"
    assert stored.success is True
    assert stored.request_metadata == {"params": {"q": "demo"}}
    assert stored.provider_runtime_reference == "test:runtime"


def test_usage_store_returns_local_ledger_rows(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            latency_ms=100,
            estimated_cost=0.01,
            created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
    )
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            method="GET",
            path="/",
            status_code=500,
            success=False,
            latency_ms=300,
            estimated_cost=0.02,
            error_type="http_status",
            created_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
        )
    )
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="httpbin",
            tool_id="get_ip",
            method="GET",
            path="/ip",
            status_code=200,
            success=True,
            latency_ms=200,
            estimated_cost=0.04,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
    )

    rows = store.ledger(project_id="local", month="2026-05")

    assert len(rows) == 1
    assert rows[0].provider_id == "ipify"
    assert rows[0].total_calls == 2
    assert rows[0].success_rate == 0.5
    assert rows[0].average_latency_ms == 200
    assert rows[0].estimated_cost == 0.03


def test_usage_store_can_group_ledger_by_execution_mode(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            execution_mode="direct",
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            latency_ms=100,
            estimated_cost=0.01,
        )
    )
    store.record(
        UsageEvent(
            execution_mode="proxy",
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            latency_ms=300,
            estimated_cost=0.02,
        )
    )

    rows = store.ledger(project_id="local", group_by_mode=True)

    assert [(row.execution_mode, row.estimated_cost) for row in rows] == [("direct", 0.01), ("proxy", 0.02)]


def test_usage_store_filters_ledger_by_capability_and_provider(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="ipify",
            tool_id="get",
            method="GET",
            path="/",
            status_code=200,
            success=True,
            estimated_cost=0.01,
        )
    )
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="public_ip_lookup",
            provider_id="httpbin",
            tool_id="get_ip",
            method="GET",
            path="/ip",
            status_code=200,
            success=True,
            estimated_cost=0.02,
        )
    )

    rows = store.ledger(project_id="local", capability_id="public_ip_lookup", provider_id="ipify")

    assert len(rows) == 1
    assert rows[0].provider_id == "ipify"
    assert rows[0].estimated_cost == 0.01


def test_proxy_call_enforces_quota_before_forwarding(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="github_repos",
            provider_id="github",
            tool_id="list_repos",
            method="GET",
            path="/repos",
            status_code=200,
            success=True,
        )
    )
    called = False

    def fake_forwarder(method, url, options):
        nonlocal called
        called = True
        return httpx.Response(200, json={"ok": True})

    status, result = execute_proxy_call(
        {
            "project_id": "local",
            "routing_decision_id": "decision_quota",
            "capability_id": "github_repos",
            "provider_id": "github",
            "tool_id": "list_repos",
            "request": {"method": "GET", "url": "https://api.github.com/repos"},
        },
        store=store,
        quota=1,
        forwarder=fake_forwarder,
    )

    summary = store.summarize("local")

    assert status == 429
    assert result["ok"] is False
    assert result["error"]["type"] == "quota_exceeded"
    assert called is False
    assert summary.total_calls == 2
    assert summary.error_counts == {"quota_exceeded": 1}
    assert store.usage_for_routing_decision("decision_quota")[0].error_type == "quota_exceeded"
