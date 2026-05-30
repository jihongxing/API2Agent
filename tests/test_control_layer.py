import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from api2agent.capabilities.models import RoutingDecision
from api2agent.control.models import UsageEvent
from api2agent.control.proxy import execute_proxy_call
from api2agent.control.storage import UsageStore
from api2agent.credentials.models import CredentialDefinition
from api2agent.credentials.resolver import LocalCredentialResolver


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


def test_proxy_call_resolves_credential_intent_before_forwarding(tmp_path: Path, monkeypatch) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    captured = {}
    monkeypatch.setenv("TEST_API_TOKEN", "secret-token")

    def fake_forwarder(method, url, options):
        captured["method"] = method
        captured["url"] = url
        captured["options"] = options
        return httpx.Response(200, json={"ok": True})

    status, result = execute_proxy_call(
        {
            "project_id": "local",
            "routing_decision_id": "decision_credential",
            "capability_id": "github.repos.list",
            "provider_id": "github",
            "tool_id": "list_repos",
            "estimated_cost": 0.01,
            "credential": {
                "credential_id": "github_TEST_API_TOKEN",
                "owner_type": "project",
                "owner_id": "local",
                "provider_id": "github",
                "auth_type": "bearer",
                "injection_mode": "header",
                "injection_name": "Authorization",
                "source": "env",
                "secret_ref": "TEST_API_TOKEN",
            },
            "request": {
                "method": "GET",
                "url": "https://api.github.com/repos",
                "headers": {"X-Trace-Id": "trace-123"},
                "params": {"visibility": "public"},
            },
        },
        store=store,
        forwarder=fake_forwarder,
    )

    event = store.usage_for_routing_decision("decision_credential")[0]
    metadata_json = json.dumps(event.request_metadata)

    assert status == 200
    assert result["ok"] is True
    assert captured["options"]["headers"]["Authorization"] == "Bearer secret-token"
    assert captured["options"]["headers"]["X-Trace-Id"] == "trace-123"
    assert event.credential_reference == "env:TEST_API_TOKEN"
    assert event.request_metadata["credential"]["secret_ref"] == "TEST_API_TOKEN"
    assert "secret-token" not in metadata_json


def test_proxy_call_records_missing_credential_without_forwarding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    called = False
    monkeypatch.delenv("TEST_API_TOKEN", raising=False)

    def fake_forwarder(method, url, options):
        nonlocal called
        called = True
        return httpx.Response(200, json={"ok": True})

    status, result = execute_proxy_call(
        {
            "project_id": "local",
            "routing_decision_id": "decision_missing_credential",
            "capability_id": "github.repos.list",
            "provider_id": "github",
            "tool_id": "list_repos",
            "credential": {
                "credential_id": "github_TEST_API_TOKEN",
                "provider_id": "github",
                "auth_type": "bearer",
                "injection_mode": "header",
                "source": "env",
                "secret_ref": "TEST_API_TOKEN",
            },
            "request": {
                "method": "GET",
                "url": "https://api.github.com/repos",
            },
        },
        store=store,
        forwarder=fake_forwarder,
    )

    event = store.usage_for_routing_decision("decision_missing_credential")[0]

    assert status == 401
    assert result["ok"] is False
    assert result["error"]["type"] == "missing_credential_secret"
    assert called is False
    assert event.success is False
    assert event.status_code == 401
    assert event.error_type == "missing_credential_secret"
    assert event.credential_reference == "env:TEST_API_TOKEN"


def test_proxy_body_credential_injection_does_not_mutate_usage_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    captured = {}
    monkeypatch.setenv("TEST_API_TOKEN", "secret-token")

    def fake_forwarder(method, url, options):
        captured["options"] = options
        return httpx.Response(200, json={"ok": True})

    status, result = execute_proxy_call(
        {
            "project_id": "local",
            "routing_decision_id": "decision_body_credential",
            "capability_id": "example.items.create",
            "provider_id": "example",
            "tool_id": "create_item",
            "credential": {
                "credential_id": "example_TEST_API_TOKEN",
                "provider_id": "example",
                "auth_type": "api_key",
                "injection_mode": "body",
                "injection_name": "api_key",
                "source": "env",
                "secret_ref": "TEST_API_TOKEN",
            },
            "request": {
                "method": "POST",
                "url": "https://api.example.com/items",
                "json": {"name": "demo"},
            },
        },
        store=store,
        forwarder=fake_forwarder,
    )

    event = store.usage_for_routing_decision("decision_body_credential")[0]
    metadata_json = json.dumps(event.request_metadata)

    assert status == 200
    assert result["ok"] is True
    assert captured["options"]["json"] == {"name": "demo", "api_key": "secret-token"}
    assert event.request_metadata["json"] == {"name": "demo"}
    assert "secret-token" not in metadata_json


def test_proxy_call_uses_config_credential_when_payload_has_no_credential(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    captured = {}
    credential_resolver = LocalCredentialResolver(
        [
            CredentialDefinition(
                credential_id="cred_example",
                provider_id="example",
                auth_type="api_key",
                injection_mode="query",
                injection_name="api_key",
                source="config",
                secret_value="config-secret",
            )
        ]
    )

    def fake_forwarder(method, url, options):
        captured["options"] = options
        return httpx.Response(200, json={"ok": True})

    status, result = execute_proxy_call(
        {
            "project_id": "local",
            "routing_decision_id": "decision_config_credential",
            "capability_id": "example.items.list",
            "provider_id": "example",
            "tool_id": "list_items",
            "request": {
                "method": "GET",
                "url": "https://api.example.com/items",
                "params": {"limit": 10},
            },
        },
        store=store,
        forwarder=fake_forwarder,
        credential_resolver=credential_resolver,
    )

    event = store.usage_for_routing_decision("decision_config_credential")[0]
    metadata_json = json.dumps(event.request_metadata)

    assert status == 200
    assert result["ok"] is True
    assert captured["options"]["params"] == {"limit": 10, "api_key": "config-secret"}
    assert event.credential_reference == "config:cred_example"
    assert event.request_metadata["credential"]["credential_id"] == "cred_example"
    assert "config-secret" not in metadata_json


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


def test_usage_store_persists_region_latency_fields(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            id="event_region",
            project_id="local",
            capability_id="weather.current.get",
            provider_id="weather_cn",
            tool_id="get_current_weather",
            method="GET",
            path="/weather",
            status_code=200,
            success=True,
            latency_ms=42,
            client_region="cn",
            api2agent_region="ap-east",
            provider_region="cn",
            latency_total_ms=42,
            latency_network_ms=10,
            latency_provider_ms=25,
            latency_overhead_ms=7,
        )
    )

    stored = store.get_usage_event("event_region")

    assert stored is not None
    assert stored.client_region == "cn"
    assert stored.api2agent_region == "ap-east"
    assert stored.provider_region == "cn"
    assert stored.latency_total_ms == 42
    assert stored.latency_network_ms == 10
    assert stored.latency_provider_ms == 25
    assert stored.latency_overhead_ms == 7


def test_proxy_call_records_region_latency_contract(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")

    def fake_forwarder(method, url, options):
        return httpx.Response(200, json={"ok": True})

    status, result = execute_proxy_call(
        {
            "project_id": "local",
            "routing_decision_id": "decision_region",
            "capability_id": "weather.current.get",
            "provider_id": "weather_cn",
            "tool_id": "get_current_weather",
            "client_region": "cn",
            "api2agent_region": "ap-east",
            "provider_region": "cn",
            "latency_network_ms": 10,
            "latency_provider_ms": 20,
            "latency_overhead_ms": 5,
            "request": {"method": "GET", "url": "https://api.example.com/weather"},
        },
        store=store,
        forwarder=fake_forwarder,
    )

    event = store.usage_for_routing_decision("decision_region")[0]

    assert status == 200
    assert result["ok"] is True
    assert event.client_region == "cn"
    assert event.api2agent_region == "ap-east"
    assert event.provider_region == "cn"
    assert event.latency_total_ms is not None
    assert event.latency_network_ms == 10
    assert event.latency_provider_ms == 20
    assert event.latency_overhead_ms == 5


def test_usage_store_marks_golden_event(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            id="event_123",
            project_id="local",
            capability_id="weather.get",
            provider_id="open_meteo",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
        )
    )

    marked = store.mark_golden("event_123")
    unmarked = store.mark_golden("event_123", is_golden=False)

    assert marked is not None
    assert marked.is_golden is True
    assert unmarked is not None
    assert unmarked.is_golden is False


def test_usage_store_lists_golden_events_with_filters(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            id="golden_weather",
            execution_mode="shadow",
            project_id="local",
            capability_id="weather.get",
            provider_id="wttr_in",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
            is_golden=True,
        )
    )
    store.record(
        UsageEvent(
            id="ordinary_weather",
            execution_mode="direct",
            project_id="local",
            capability_id="weather.get",
            provider_id="open_meteo",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
        )
    )

    events = store.list_usage_events(capability_id="weather.get", execution_mode="shadow", golden_only=True)

    assert [event.id for event in events] == ["golden_weather"]


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


def test_usage_store_can_filter_ledger_to_golden_events(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="weather.get",
            provider_id="open_meteo",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
            estimated_cost=0.01,
            is_golden=True,
        )
    )
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="weather.get",
            provider_id="wttr_in",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
            estimated_cost=0.02,
        )
    )

    rows = store.ledger(project_id="local", capability_id="weather.get", golden_only=True)

    assert len(rows) == 1
    assert rows[0].provider_id == "open_meteo"
    assert rows[0].estimated_cost == 0.01


def test_usage_store_metrics_exclude_replay_events(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            execution_mode="direct",
            project_id="local",
            capability_id="weather.get",
            provider_id="open_meteo",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
            latency_ms=100,
        )
    )
    store.record(
        UsageEvent(
            execution_mode="replay",
            project_id="local",
            capability_id="weather.get",
            provider_id="open_meteo",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=500,
            success=False,
            latency_ms=900,
        )
    )
    store.record(
        UsageEvent(
            execution_mode="shadow",
            project_id="local",
            capability_id="weather.get",
            provider_id="open_meteo",
            tool_id="get_current_weather",
            method="GET",
            path="weather.get",
            status_code=200,
            success=True,
            latency_ms=300,
        )
    )

    metrics = store.metrics_for_capability("weather.get")
    metrics_without_shadow = store.metrics_for_capability("weather.get", include_shadow=False)

    assert len(metrics) == 1
    assert metrics[0].total_calls == 2
    assert metrics[0].success_rate == 1.0
    assert metrics[0].average_latency_ms == 200
    assert metrics_without_shadow[0].total_calls == 1
    assert metrics_without_shadow[0].average_latency_ms == 100


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
