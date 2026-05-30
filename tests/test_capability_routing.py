import json
from pathlib import Path

from typer.testing import CliRunner

from api2agent.capabilities.models import DecisionDatasetRecord, MetricsSnapshot, ProviderCandidate, RoutingPolicy
from api2agent.capabilities.policies import routing_policy_preset
from api2agent.capabilities.naming import is_alpha_capability_id
from api2agent.capabilities.registry import PROVIDER_REGISTRY_CONTRACT_VERSION, load_provider_registry
from api2agent.capabilities.routing import rank_providers, select_provider
from api2agent.cli import app
from api2agent.control.models import UsageEvent
from api2agent.control.storage import UsageStore


runner = CliRunner()


def test_route_selects_lowest_cost_without_metrics() -> None:
    providers = [
        ProviderCandidate(id="a", capability_id="image_generation", provider_id="a", tool_id="generate", estimated_cost=0.05),
        ProviderCandidate(id="b", capability_id="image_generation", provider_id="b", tool_id="generate", estimated_cost=0.01),
    ]

    selected = select_provider(providers, [], RoutingPolicy(strategy="lowest_cost"))

    assert selected is not None
    assert selected.provider_id == "b"


def test_route_selects_highest_success_rate_from_metrics() -> None:
    providers = [
        ProviderCandidate(id="a", capability_id="image_generation", provider_id="a", tool_id="generate"),
        ProviderCandidate(id="b", capability_id="image_generation", provider_id="b", tool_id="generate"),
    ]
    metrics = [
        MetricsSnapshot(capability_id="image_generation", provider_id="a", total_calls=10, success_rate=0.8),
        MetricsSnapshot(capability_id="image_generation", provider_id="b", total_calls=10, success_rate=0.95),
    ]

    ranked = rank_providers(providers, metrics, RoutingPolicy(strategy="highest_success_rate"))

    assert [provider.provider_id for provider in ranked] == ["b", "a"]


def test_reliability_first_preset_prefers_success_rate() -> None:
    providers = [
        ProviderCandidate(id="fast", capability_id="image_generation", provider_id="fast", tool_id="generate", estimated_cost=0.01),
        ProviderCandidate(id="reliable", capability_id="image_generation", provider_id="reliable", tool_id="generate", estimated_cost=0.04),
    ]
    metrics = [
        MetricsSnapshot(
            capability_id="image_generation",
            provider_id="fast",
            total_calls=5,
            success_rate=0.6,
            average_latency_ms=740,
            estimated_cost_per_call=0.01,
        ),
        MetricsSnapshot(
            capability_id="image_generation",
            provider_id="reliable",
            total_calls=5,
            success_rate=1.0,
            average_latency_ms=1560,
            estimated_cost_per_call=0.04,
        ),
    ]

    selected = select_provider(providers, metrics, routing_policy_preset("reliability_first"))

    assert selected is not None
    assert selected.provider_id == "reliable"


def test_usage_store_returns_provider_metrics(tmp_path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="image_generation",
            provider_id="a",
            tool_id="generate",
            method="POST",
            path="/generate",
            status_code=200,
            success=True,
            latency_ms=100,
            estimated_cost=0.02,
        )
    )
    store.record(
        UsageEvent(
            project_id="local",
            capability_id="image_generation",
            provider_id="a",
            tool_id="generate",
            method="POST",
            path="/generate",
            status_code=500,
            success=False,
            latency_ms=300,
            estimated_cost=0.04,
            error_type="http_status",
        )
    )

    metrics = store.metrics_for_capability("image_generation")

    assert len(metrics) == 1
    assert metrics[0].provider_id == "a"
    assert metrics[0].total_calls == 2
    assert metrics[0].successful_calls == 1
    assert metrics[0].success_rate == 0.5
    assert metrics[0].average_latency_ms == 200
    assert metrics[0].estimated_cost_per_call == 0.03


def test_route_command_selects_provider(tmp_path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "provider_a",
                        "capability_id": "image_generation",
                        "provider_id": "a",
                        "tool_id": "generate",
                        "estimated_cost": 0.05,
                    },
                    {
                        "id": "provider_b",
                        "capability_id": "image_generation",
                        "provider_id": "b",
                        "tool_id": "generate",
                        "estimated_cost": 0.01,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "route",
            str(registry),
            "--capability-id",
            "image_generation",
            "--strategy",
            "lowest_cost",
            "--db",
            str(tmp_path / "usage.sqlite"),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    stored_decision = UsageStore(tmp_path / "usage.sqlite").get_routing_decision(payload["decision"]["id"])

    assert result.exit_code == 0
    assert payload["selected"]["provider_id"] == "b"
    assert payload["ranked_provider_ids"] == ["b", "a"]
    assert payload["registry_contract_version"] == "provider_registry.v0.1"
    assert payload["decision"]["selected_provider_id"] == "b"
    assert stored_decision is not None
    assert stored_decision.selected_provider_id == "b"


def test_route_command_supports_policy_preset(tmp_path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "provider_a",
                        "capability_id": "image_generation",
                        "provider_id": "fast",
                        "tool_id": "generate",
                        "estimated_cost": 0.01,
                    },
                    {
                        "id": "provider_b",
                        "capability_id": "image_generation",
                        "provider_id": "reliable",
                        "tool_id": "generate",
                        "estimated_cost": 0.04,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    store = UsageStore(tmp_path / "usage.sqlite")
    store.record(
        UsageEvent(
            project_id="routing-dogfood",
            capability_id="image_generation",
            provider_id="fast",
            tool_id="generate",
            method="POST",
            path="/generate",
            status_code=500,
            success=False,
            latency_ms=700,
            estimated_cost=0.01,
            error_type="http_status",
        )
    )
    store.record(
        UsageEvent(
            project_id="routing-dogfood",
            capability_id="image_generation",
            provider_id="reliable",
            tool_id="generate",
            method="POST",
            path="/generate",
            status_code=200,
            success=True,
            latency_ms=1500,
            estimated_cost=0.04,
        )
    )

    result = runner.invoke(
        app,
        [
            "route",
            str(registry),
            "--capability-id",
            "image_generation",
            "--preset",
            "reliability_first",
            "--db",
            str(tmp_path / "usage.sqlite"),
            "--json",
        ],
    )

    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["preset"] == "reliability_first"
    assert payload["selected"]["provider_id"] == "reliable"
    assert payload["decision"]["preset"] == "reliability_first"


def test_route_command_rejects_invalid_registry_schema(tmp_path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"providers": [{"id": "missing_required_fields"}]}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "route",
            str(registry),
            "--capability-id",
            "image_generation",
            "--db",
            str(tmp_path / "usage.sqlite"),
        ],
    )

    assert result.exit_code != 0
    assert "Registry schema is invalid" in result.output


def test_route_command_rejects_missing_registry_file(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "route",
            str(tmp_path / "missing.json"),
            "--capability-id",
            "image_generation",
            "--db",
            str(tmp_path / "usage.sqlite"),
        ],
    )

    assert result.exit_code != 0
    assert "Registry file cannot be read" in result.output


def test_provider_registry_fixture_uses_stable_contract() -> None:
    registry = load_provider_registry(Path("tests/fixtures/provider_registry/public_ip_lookup.json"))

    assert registry.contract_version == PROVIDER_REGISTRY_CONTRACT_VERSION
    assert [provider.provider_id for provider in registry.providers] == ["ipify", "httpbin"]
    assert registry.providers[0].metadata["package_dir"] == ".dogfood/ipify"


def test_provider_candidate_supports_region_metadata() -> None:
    provider = ProviderCandidate(
        id="weather_cn",
        capability_id="weather.current.get",
        provider_id="weather_cn",
        tool_id="get_current_weather",
        regions=["cn"],
        geo_affinity="regional",
    )

    assert provider.regions == ["cn"]
    assert provider.geo_affinity == "regional"


def test_decision_dataset_record_contract() -> None:
    record = DecisionDatasetRecord(
        request_id="req_123",
        routing_decision_id="decision_123",
        project_id="local",
        capability_id="weather.current.get",
        client_region="cn",
        api2agent_region="ap-east",
        candidate_provider_ids=["weather_us", "weather_cn"],
        selected_provider_id="weather_cn",
        routing_strategy="balanced",
        success=True,
        latency_total_ms=40,
        estimated_cost=0.001,
    )

    payload = record.model_dump(mode="json")

    assert payload["client_region"] == "cn"
    assert payload["api2agent_region"] == "ap-east"
    assert payload["candidate_provider_ids"] == ["weather_us", "weather_cn"]
    assert payload["selected_provider_id"] == "weather_cn"
    assert payload["latency_total_ms"] == 40


def test_registry_command_inspects_provider_registry_fixture() -> None:
    result = runner.invoke(app, ["registry", "tests/fixtures/provider_registry/public_ip_lookup.json", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["contract_version"] == PROVIDER_REGISTRY_CONTRACT_VERSION
    assert payload["provider_count"] == 2
    assert payload["capability_counts"] == {"public_ip_lookup": 2}
    assert "warnings" in payload
    assert payload["naming_warnings"][0]["code"] == "non_alpha_capability_id"
    assert [provider["provider_id"] for provider in payload["providers"]] == ["ipify", "httpbin"]


def test_alpha_capability_id_rule() -> None:
    assert is_alpha_capability_id("weather.current.get") is True
    assert is_alpha_capability_id("github.repo.list") is True
    assert is_alpha_capability_id("weather.get") is False
    assert is_alpha_capability_id("public_ip_lookup") is False


def test_registry_command_warns_about_missing_package_dir(tmp_path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "contract_version": PROVIDER_REGISTRY_CONTRACT_VERSION,
                "providers": [
                    {
                        "id": "provider_a",
                        "capability_id": "image_generation",
                        "provider_id": "a",
                        "tool_id": "generate",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["registry", str(registry), "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["warnings"] == [
        {
            "severity": "error",
            "code": "missing_package_dir",
            "provider_id": "a",
            "message": "missing metadata.package_dir",
        }
    ]


def test_route_command_rejects_unsupported_registry_contract_version(tmp_path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "contract_version": "provider_registry.v9",
                "providers": [
                    {
                        "id": "provider_a",
                        "capability_id": "image_generation",
                        "provider_id": "a",
                        "tool_id": "generate",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "route",
            str(registry),
            "--capability-id",
            "image_generation",
            "--db",
            str(tmp_path / "usage.sqlite"),
        ],
    )

    assert result.exit_code != 0
    assert "Unsupported provider registry contract_version" in result.output
