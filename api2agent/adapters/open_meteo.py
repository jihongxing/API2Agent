from time import perf_counter
from typing import Any

import httpx

from api2agent.adapters.models import AdapterResult, CostEstimate
from api2agent.errors import StandardErrorType, error_type_for_status


class OpenMeteoWeatherAdapter:
    capability_id = "weather.get"
    provider_id = "open_meteo"
    tool_id = "get_current_weather"

    def __init__(self, client: Any | None = None) -> None:
        self.client = client or httpx.Client(timeout=20)

    def estimate_cost(self, input: dict[str, Any]) -> CostEstimate:
        return CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared")

    def call(self, input: dict[str, Any]) -> AdapterResult:
        start = perf_counter()
        city = str(input.get("city") or "").strip()
        if not city:
            return self._error(StandardErrorType.INVALID_REQUEST, "Missing required input: city", start)

        try:
            location = self._geocode(city)
            if location is None:
                return self._error(StandardErrorType.NOT_FOUND, f"City not found: {city}", start, status_code=404)
            weather = self._forecast(location, input)
        except httpx.TimeoutException as exc:
            return self._error(StandardErrorType.TIMEOUT, str(exc), start)
        except httpx.HTTPStatusError as exc:
            return self._error(error_type_for_status(exc.response.status_code), str(exc), start, exc.response.status_code)
        except httpx.HTTPError as exc:
            return self._error(StandardErrorType.PROVIDER_ERROR, str(exc), start)

        if not weather.is_success:
            return self._error(error_type_for_status(weather.status_code), f"HTTP {weather.status_code}", start, weather.status_code)

        try:
            output = self._normalize(location, weather.json())
        except (KeyError, TypeError, ValueError) as exc:
            return self._error(StandardErrorType.NORMALIZATION_ERROR, str(exc), start, weather.status_code)

        return AdapterResult(
            ok=True,
            capability_id=self.capability_id,
            provider_id=self.provider_id,
            output=output,
            status_code=weather.status_code,
            latency_ms=(perf_counter() - start) * 1000,
            cost=self.estimate_cost(input),
        )

    def _geocode(self, city: str) -> dict[str, Any] | None:
        response = self.client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
        )
        if not response.is_success:
            raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
        results = response.json().get("results") or []
        return results[0] if results else None

    def _forecast(self, location: dict[str, Any], input: dict[str, Any]):
        return self.client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": "temperature_2m,wind_speed_10m,weather_code",
                "temperature_unit": input.get("temperature_unit") or "celsius",
            },
        )

    def _normalize(self, location: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        current = body["current"]
        units = body.get("current_units") or {}
        return {
            "city": location.get("name"),
            "country": location.get("country"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "time": current.get("time"),
            "temperature_2m": current.get("temperature_2m"),
            "temperature_unit": units.get("temperature_2m"),
            "wind_speed_10m": current.get("wind_speed_10m"),
            "wind_speed_unit": units.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
        }

    def _error(
        self,
        error_type: StandardErrorType,
        message: str,
        start: float,
        status_code: int | None = None,
    ) -> AdapterResult:
        return AdapterResult(
            ok=False,
            capability_id=self.capability_id,
            provider_id=self.provider_id,
            status_code=status_code,
            latency_ms=(perf_counter() - start) * 1000,
            cost=CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared"),
            error_type=error_type.value,
            error_message=message,
        )
