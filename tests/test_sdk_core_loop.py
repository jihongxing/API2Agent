from pathlib import Path

from api2agent.adapters.models import AdapterResult, CostEstimate
from api2agent.adapters.open_meteo import OpenMeteoWeatherAdapter
from api2agent.adapters.wttr_in import WttrInWeatherAdapter
from api2agent.benchmark import run_weather_benchmark
from api2agent.control.storage import UsageStore
from api2agent.sdk import call


class FakeResponse:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body
        self.is_success = 200 <= status_code < 300
        self.request = None

    def json(self):
        return self._body


class FakeWeatherClient:
    def __init__(self) -> None:
        self.urls = []

    def get(self, url, params=None):
        self.urls.append((url, params))
        if "geocoding-api" in url:
            return FakeResponse(
                200,
                {
                    "results": [
                        {
                            "name": "San Francisco",
                            "country": "United States",
                            "latitude": 37.7749,
                            "longitude": -122.4194,
                        }
                    ]
                },
            )
        return FakeResponse(
            200,
            {
                "current": {
                    "time": "2026-05-30T00:00",
                    "temperature_2m": 16.2,
                    "wind_speed_10m": 12.4,
                    "weather_code": 1,
                },
                "current_units": {
                    "temperature_2m": "°C",
                    "wind_speed_10m": "km/h",
                },
            },
        )


def test_open_meteo_adapter_normalizes_weather_output() -> None:
    adapter = OpenMeteoWeatherAdapter(client=FakeWeatherClient())

    result = adapter.call({"city": "San Francisco"})

    assert result.ok is True
    assert result.provider_id == "open_meteo"
    assert result.output["city"] == "San Francisco"
    assert result.output["temperature_2m"] == 16.2
    assert result.cost.cost_source == "provider_declared"


def test_open_meteo_adapter_maps_missing_city_to_invalid_request() -> None:
    adapter = OpenMeteoWeatherAdapter(client=FakeWeatherClient())

    result = adapter.call({})

    assert result.ok is False
    assert result.error_type == "INVALID_REQUEST"


def test_wttr_in_adapter_normalizes_weather_output() -> None:
    class FakeWttrClient:
        def get(self, url, params=None):
            return FakeResponse(
                200,
                {
                    "nearest_area": [
                        {
                            "areaName": [{"value": "San Francisco"}],
                            "country": [{"value": "United States"}],
                            "latitude": "37.7749",
                            "longitude": "-122.4194",
                        }
                    ],
                    "current_condition": [
                        {
                            "localObsDateTime": "2026-05-30 00:00",
                            "temp_C": "16",
                            "windspeedKmph": "12",
                            "weatherCode": "113",
                        }
                    ],
                },
            )

    adapter = WttrInWeatherAdapter(client=FakeWttrClient())

    result = adapter.call({"city": "San Francisco"})

    assert result.ok is True
    assert result.provider_id == "wttr_in"
    assert result.output["city"] == "San Francisco"
    assert result.output["temperature_2m"] == 16.0


def test_sdk_call_records_routing_usage_and_ledger(tmp_path: Path, monkeypatch) -> None:
    class FakeAdapter:
        capability_id = "weather.get"
        provider_id = "open_meteo"
        tool_id = "get_current_weather"

        def call(self, input):
            return AdapterResult(
                ok=True,
                capability_id=self.capability_id,
                provider_id=self.provider_id,
                output={"city": input["city"], "temperature_2m": 16.2},
                status_code=200,
                latency_ms=25,
                cost=CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared"),
            )

        def estimate_cost(self, input):
            return CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared")

    monkeypatch.setattr("api2agent.sdk.OpenMeteoWeatherAdapter", FakeAdapter)
    db = tmp_path / "usage.sqlite"

    result = call("weather.get", {"city": "San Francisco"}, agent_id="agent_123", db=db)
    store = UsageStore(db)
    events = store.usage_for_routing_decision(result["routing_decision"]["id"])
    ledger = store.ledger(project_id="local", capability_id="weather.get", provider_id="open_meteo", group_by_mode=True)

    assert result["ok"] is True
    assert result["agent_id"] == "agent_123"
    assert result["output"]["temperature_2m"] == 16.2
    assert len(events) == 1
    assert events[0].execution_mode == "direct"
    assert events[0].provider_id == "open_meteo"
    assert ledger[0].total_calls == 1


def test_sdk_call_can_route_to_named_weather_provider(tmp_path: Path, monkeypatch) -> None:
    class FakeWttrAdapter:
        capability_id = "weather.get"
        provider_id = "wttr_in"
        tool_id = "get_current_weather"

        def call(self, input):
            return AdapterResult(
                ok=True,
                capability_id=self.capability_id,
                provider_id=self.provider_id,
                output={"city": input["city"], "temperature_2m": 15.0},
                status_code=200,
                latency_ms=30,
                cost=CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared"),
            )

        def estimate_cost(self, input):
            return CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared")

    monkeypatch.setattr("api2agent.sdk.WttrInWeatherAdapter", FakeWttrAdapter)

    result = call("weather.get", {"city": "San Francisco"}, provider_id="wttr_in", db=tmp_path / "usage.sqlite")

    assert result["ok"] is True
    assert result["provider_id"] == "wttr_in"


def test_sdk_default_route_uses_lowest_observed_latency(tmp_path: Path, monkeypatch) -> None:
    class FakeOpenMeteoAdapter:
        capability_id = "weather.get"
        provider_id = "open_meteo"
        tool_id = "get_current_weather"

        def call(self, input):
            return AdapterResult(ok=True, capability_id=self.capability_id, provider_id=self.provider_id, output={}, status_code=200, latency_ms=500)

        def estimate_cost(self, input):
            return CostEstimate()

    class FakeWttrAdapter:
        capability_id = "weather.get"
        provider_id = "wttr_in"
        tool_id = "get_current_weather"

        def call(self, input):
            return AdapterResult(ok=True, capability_id=self.capability_id, provider_id=self.provider_id, output={}, status_code=200, latency_ms=50)

        def estimate_cost(self, input):
            return CostEstimate()

    monkeypatch.setattr("api2agent.sdk.OpenMeteoWeatherAdapter", FakeOpenMeteoAdapter)
    monkeypatch.setattr("api2agent.sdk.WttrInWeatherAdapter", FakeWttrAdapter)
    db = tmp_path / "usage.sqlite"

    call("weather.get", {"city": "San Francisco"}, provider_id="open_meteo", db=db)
    call("weather.get", {"city": "San Francisco"}, provider_id="wttr_in", db=db)
    routed = call("weather.get", {"city": "San Francisco"}, db=db)

    assert routed["provider_id"] == "wttr_in"
    assert routed["routing_decision"]["strategy"] == "lowest_latency"
    assert routed["routing_decision"]["ranked_provider_ids"] == ["wttr_in", "open_meteo"]


def test_sdk_call_supports_explicit_routing_strategy(tmp_path: Path, monkeypatch) -> None:
    class FakeOpenMeteoAdapter:
        capability_id = "weather.get"
        provider_id = "open_meteo"
        tool_id = "get_current_weather"

        def call(self, input):
            return AdapterResult(ok=True, capability_id=self.capability_id, provider_id=self.provider_id, output={}, status_code=200, latency_ms=500)

        def estimate_cost(self, input):
            return CostEstimate()

    class FakeWttrAdapter:
        capability_id = "weather.get"
        provider_id = "wttr_in"
        tool_id = "get_current_weather"

        def call(self, input):
            return AdapterResult(ok=True, capability_id=self.capability_id, provider_id=self.provider_id, output={}, status_code=200, latency_ms=50)

        def estimate_cost(self, input):
            return CostEstimate()

    monkeypatch.setattr("api2agent.sdk.OpenMeteoWeatherAdapter", FakeOpenMeteoAdapter)
    monkeypatch.setattr("api2agent.sdk.WttrInWeatherAdapter", FakeWttrAdapter)
    db = tmp_path / "usage.sqlite"

    call("weather.get", {"city": "San Francisco"}, provider_id="open_meteo", db=db)
    call("weather.get", {"city": "San Francisco"}, provider_id="wttr_in", db=db)
    routed = call("weather.get", {"city": "San Francisco"}, strategy="first", db=db)

    assert routed["provider_id"] == "open_meteo"
    assert routed["routing_decision"]["strategy"] == "first"
    assert routed["routing_decision"]["ranked_provider_ids"] == ["open_meteo", "wttr_in"]


def test_sdk_call_failover_records_failed_and_successful_attempts(tmp_path: Path, monkeypatch) -> None:
    class FailingOpenMeteoAdapter:
        capability_id = "weather.get"
        provider_id = "open_meteo"
        tool_id = "get_current_weather"

        def call(self, input):
            return AdapterResult(
                ok=False,
                capability_id=self.capability_id,
                provider_id=self.provider_id,
                status_code=500,
                latency_ms=20,
                error_type="PROVIDER_ERROR",
                error_message="upstream failed",
            )

        def estimate_cost(self, input):
            return CostEstimate()

    class SuccessfulWttrAdapter:
        capability_id = "weather.get"
        provider_id = "wttr_in"
        tool_id = "get_current_weather"

        def call(self, input):
            return AdapterResult(
                ok=True,
                capability_id=self.capability_id,
                provider_id=self.provider_id,
                output={"city": input["city"], "temperature_2m": 15.0},
                status_code=200,
                latency_ms=30,
            )

        def estimate_cost(self, input):
            return CostEstimate()

    monkeypatch.setattr("api2agent.sdk.OpenMeteoWeatherAdapter", FailingOpenMeteoAdapter)
    monkeypatch.setattr("api2agent.sdk.WttrInWeatherAdapter", SuccessfulWttrAdapter)
    db = tmp_path / "usage.sqlite"

    result = call("weather.get", {"city": "San Francisco"}, strategy="first", failover=True, max_attempts=2, db=db)
    store = UsageStore(db)
    events = store.usage_for_routing_decision(result["routing_decision"]["id"])

    assert result["ok"] is True
    assert result["provider_id"] == "wttr_in"
    assert [attempt["provider_id"] for attempt in result["attempts"]] == ["open_meteo", "wttr_in"]
    assert [event.provider_id for event in events] == ["open_meteo", "wttr_in"]
    assert events[0].success is False
    assert events[0].error_type == "PROVIDER_ERROR"
    assert events[1].success is True


def test_sdk_call_failover_stops_on_non_retriable_error(tmp_path: Path, monkeypatch) -> None:
    class InvalidRequestOpenMeteoAdapter:
        capability_id = "weather.get"
        provider_id = "open_meteo"
        tool_id = "get_current_weather"

        def call(self, input):
            return AdapterResult(
                ok=False,
                capability_id=self.capability_id,
                provider_id=self.provider_id,
                status_code=400,
                latency_ms=20,
                error_type="INVALID_REQUEST",
                error_message="bad request",
            )

        def estimate_cost(self, input):
            return CostEstimate()

    class UnexpectedWttrAdapter:
        capability_id = "weather.get"
        provider_id = "wttr_in"
        tool_id = "get_current_weather"

        def call(self, input):
            raise AssertionError("non-retriable errors must not fail over")

        def estimate_cost(self, input):
            return CostEstimate()

    monkeypatch.setattr("api2agent.sdk.OpenMeteoWeatherAdapter", InvalidRequestOpenMeteoAdapter)
    monkeypatch.setattr("api2agent.sdk.WttrInWeatherAdapter", UnexpectedWttrAdapter)
    db = tmp_path / "usage.sqlite"

    result = call("weather.get", {"city": "San Francisco"}, strategy="first", failover=True, max_attempts=2, db=db)
    store = UsageStore(db)
    events = store.usage_for_routing_decision(result["routing_decision"]["id"])

    assert result["ok"] is False
    assert result["provider_id"] == "open_meteo"
    assert len(result["attempts"]) == 1
    assert len(events) == 1
    assert events[0].error_type == "INVALID_REQUEST"


def test_weather_benchmark_returns_provider_latency_stats(tmp_path: Path, monkeypatch) -> None:
    calls = {"open_meteo": 0, "wttr_in": 0}

    def fake_call(capability, input, provider_id=None, agent_id=None, db=None):
        calls[provider_id] += 1
        latency = 100 if provider_id == "open_meteo" else 50
        return {
            "ok": True,
            "latency_ms": latency,
            "cost": {"estimated_cost": 0.0, "observed_cost": 0.0},
        }

    monkeypatch.setattr("api2agent.benchmark.call", fake_call)

    result = run_weather_benchmark(city="San Francisco", iterations=2, db=tmp_path / "usage.sqlite")

    assert calls == {"open_meteo": 2, "wttr_in": 2}
    assert result["providers"][0]["p50_latency_ms"] == 100
    assert result["providers"][1]["p95_latency_ms"] == 50
